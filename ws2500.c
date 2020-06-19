/*

   ws2500 -- Weather Data Extraction utility (ws2500 model)

   Copyright (C) 2003,
   Rainer Krienke, krienke@uni-koblenz.de
   This software is partly based on the program from
   Friedrich Zabel (fredz@mail.telepac.pt) for the wx2000 station.

   This program is free software; you can redistribute it and/or modify
   it under the terms of the GNU General Public License as published by
   the Free Software Foundation; either version 2 of the License, or
   (at your option) any later version.

   This program is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
   GNU General Public License for more details.

   You should have received a copy of the GNU General Public License
   along with this program; if not, write to the Free Software
   Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

*/

#include "ws2500.h"
#include <sys/time.h>

void signal_handler_IO (int status);  /* definition of signal handler  */
struct termios oldtio,newtio;
static u_char buffer[BUFLEN+1];
static char errBuffer[512];	      /* for error Messages */
static char outBuffer[OUTPUTBUFFERSIZE]; /* Buffer cache for printf etc */
					 /* see call of setvbuf         */
static int doDebug=0;
static char Version[]="$Revision: 0.155 $";
CONFIG config;  		      /* Program configuration */


/* some debug macros                                                         */
/* to enable debugging set doDebug to 1; Best use cmdline option -D for this */
#define DEBUG1(x)   if( doDebug ) fprintf(stderr, x);

#define DEBUG2(x,y) if( doDebug ) fprintf(stderr, x, y);
#define DEBUG3(x,y,z) if( doDebug ) fprintf(stderr, x, y, z);
#define FOR(x)  for(x)


/* *********************************** */
/* print out an error string to stderr */
/* *********************************** */
void printError(char *err, int doFlush){
	if( doFlush ) fflush(stdout);
	fputs(err, stderr);
}


/* ******************************************************************* */
/* Check if there is a valid lock file for the serial port in question */
/* ******************************************************************* */
BOOL checkLock(char *lck_file, pid_t * pid)
{
	char pid_str[PIDLEN];
	int lck_fd, n;

	memset(pid_str, '\0', PIDLEN);
	lck_fd = open(lck_file, O_RDONLY, 0);	/* see if a lock file exists */
	if (!lck_fd)
		return FALSE;

	n = read(lck_fd, &pid_str, PIDLEN - 1);	/* read pid from file */
	close(lck_fd);
	if (n < 0)
		return FALSE;

	sscanf(pid_str, " %d", pid);	/* see if process exists */
	if (pid == 0 || (kill(*pid, 0) == -1 && errno == ESRCH))
		return FALSE;	/* no */
	else
		return TRUE;	/* yes */
}


/* ******************************** */
/* create lock file fpr serial Port */
/* ******************************** */
BOOL lockPort(char * bname)
{
	int lock_fd;
	int i;
	char lock_file[PATHLEN];
	char serialCopy[PATHLEN];
	pid_t pid;
	char pid_str[PIDLEN];
	char *serial_port;


	strcpy(serialCopy, bname);
	serial_port=basename(serialCopy);
	memset(pid_str, '\0', PIDLEN);
	sprintf(lock_file, "%s%s", LOCK_PREFIX, serial_port);
	for (i=0;i<10;i++) {
		if ((lock_fd =
		     open(lock_file, O_RDWR | O_EXCL | O_CREAT,
			  0644)) < 0) {
			if (errno == EEXIST) {
				if (checkLock(lock_file, &pid)) {
					DEBUG3("%s : has PID -> %d\n",
						  serial_port, pid);
					printError("*** Serial port is locked. Exit.\n", 1);
					exit(1);
				} else {
					unlink(lock_file);
					DEBUG3
					    ("%s : removed lock file for PID -> %d\n",
					     serial_port, pid);
					continue;
				}
			} else {
				DEBUG2("%s : created lock file\n",
					  serial_port);
				return TRUE;
			}
		}

		pid = getpid();	/* get pid of process and write to lock file */
		sprintf(pid_str, "%010d\n", pid);
		write(lock_fd, pid_str, PIDLEN - 1);
		close(lock_fd);

		return FALSE;
	}
	return FALSE;
}


/* ******************************** */
/* delete lock file for serial port */
/* ******************************** */
void unlockPort(char *bname)
{
	char lock_file[PATHLEN];
	char *serial_port;
	char serialCopy[PATHLEN];
	
	strcpy(serialCopy, bname);
	serial_port=basename(serialCopy);

	sprintf(lock_file, "%s%s", LOCK_PREFIX, serial_port);
	unlink(lock_file);
	DEBUG2("%s : removed lock file\n", serial_port);
}


/* ************************* */
/* Set dtr modem status line */
/* ************************* */
void setDtr(int fd)
{
        int temp;

        ioctl(fd, TIOCMGET, &temp);
        temp |= TIOCM_DTR;
        ioctl(fd, TIOCMSET, &temp);
}


/* *************************** */
/* clear dtr modem status line */
/* *************************** */
void clearDtr(int fd)
{
        int temp;

        ioctl(fd, TIOCMGET, &temp);
        temp &= ~TIOCM_DTR;
        ioctl(fd, TIOCMSET, &temp);
}


/* **************************** */
/* return dtr modem status line */
/* **************************** */
int getDtr(int fd)
{
        int temp;

        ioctl(fd, TIOCMGET, &temp);
        temp &= TIOCM_DTR;
	return temp;	
}


/* ************************* */
/* Set rts modem status line */
/* ************************* */
void setRts(int fd)
{
        int temp;

        ioctl(fd, TIOCMGET, &temp);
        temp |= TIOCM_RTS;
        ioctl(fd, TIOCMSET, &temp);
}

/* **************************** */
/* return dtr modem status line */
/* **************************** */
int getRts(int fd)
{
        int temp;

        ioctl(fd, TIOCMGET, &temp);
        temp &= TIOCM_RTS;
	return(temp);
}

/* *************************** */
/* clear dtr modem status line */
/* *************************** */
void clearRts(int fd)
{
        int temp;

        ioctl(fd, TIOCMGET, &temp);
        temp &= ~TIOCM_RTS;
        ioctl(fd, TIOCMSET, &temp);
}


/* ******************************* */
/* open serial port                */
/* ******************************* */
int openSerial(char * port)
{
   int fd;
   struct termios options;

   lockPort(port);
   
   /* open the device to be non-blocking (read will return immediatly) */
   fd = open(port, O_RDWR | O_NOCTTY | O_NONBLOCK);
   if (fd <0) { perror(port); return(fd); }

   tcgetattr(fd,&oldtio); /* save current port settings */

   /* set new port settings for input processing */
   //bzero(&newtio, sizeof(newtio)); /* clear struct for new port settings */
   tcgetattr(fd, &newtio); /* get current port settings */
   
   newtio.c_cflag = BAUDRATE | CS8 | CLOCAL | CREAD | PARENB | CSTOPB;
   newtio.c_iflag = IGNPAR | BRKINT;
   newtio.c_oflag = 0;
   newtio.c_cc[VMIN]=0;
   newtio.c_cc[VTIME]=1;   /*  * 0.1 sec */
   newtio.c_lflag &= ~(ICANON | ECHO | ECHOE | ISIG);

   tcflush(fd, TCIFLUSH);
   tcsetattr(fd,TCSANOW, &newtio);

   tcgetattr(fd, &options);
   cfsetispeed(&options, config.speed);
   cfsetospeed(&options, config.speed);
   tcsetattr(fd, TCSANOW, &options);

   return(fd);
}


/* ******************************* */
/* close serial port                */
/* ******************************* */
void closeSerial(int fd, char *port){
   tcsetattr(fd,TCSANOW,&oldtio);
   close(fd);
   unlockPort(port);
}

/* ************************ */
/* Shut down Communications */
/* ************************ */
void stopCom(int fd, char *port)
{
   clearDtr(fd);
   setRts(fd);
   closeSerial(fd, port);
}


/* ********************************************************** */
/* send a command to serial interface                         */
/* if paris used it has to have a length of !exactly! 4 chars */
/* ********************************************************** */
int sendCommand(int fd, COMMAND cmd, u_char *par)
{
	static u_char *command[]={ (u_char*)"\x01\x30\xd0\x04", 
			(u_char*)"\x01\x31\xcf\x04",
			(u_char*)"\x01\x32\xce\x04", 
			(u_char*)"\x01\x33\xcd\x04",
			(u_char*)"\x01\x34\xcc\x04", 
			(u_char*)"\x01\x35\xcb\x04",
			(u_char*)"\x01\x44\x00\x00\x00\x00\x00\x04"
			};
        int res,i;
        u_char com[10];

   	DEBUG1("Start-send\n");
        if (par) {
		/* Make a temp copy of command */
                memcpy(com, command[cmd], 8);
		/* Insert 4 command parameters into command */
                memcpy(com+2, par, 4);
		/* calculate checksum */
                com[6] = 256 - ((com[1] + com[2] +
				com[3] + com[4] + com[5] )&255);
		com[6]|=0x80;  /* Set bit 7 */
                res = write(fd, com, 8);
		FOR(i=0; i<8; i++){
            		DEBUG2("-> %x ", com[i]);
		}
        } else{
                res = write(fd, command[cmd], 4);
		FOR(i=0; i<4; i++){
            		DEBUG2("-> %x ", command[cmd][i]);
		}
        }
        DEBUG1("\n");



   	DEBUG1("End-send\n");

        return res;
}


/* ********************************************************************** */
/* Read some data from serial line. max is the maximal number to read     */
/* if max is 0 then as much as possible chars will be read. The value     */
/* doWait says if we should wait some time for chars or possibly just return */
/* without  any chars read, if there is nothing available                  */
/* ********************************************************************** */
int readData(int fd, int doWait)
{
        int i, n, res;
	int minorFault;
	int bytes;
	struct timespec ts;

	DEBUG1("begin readData\n");
	minorFault=120;
        n = 0;
	buffer[0]='\0';

	ioctl(fd, FIONREAD, &bytes);
	DEBUG2("waitFlag vor while: %d\n", bytes);
	if( ! bytes ){/* If no data wait a while for data to come */
            ts.tv_sec=0;
   	    ts.tv_nsec=2L;
	    nanosleep(&ts, NULL);
	}
	/* Wait for input until timeout or ETX is found */
        while (buffer[n?n-1:0] != ETX && minorFault > 0) {
		DEBUG2("waitFlag hinter while: %d\n", bytes);
		minorFault--;
		if(minorFault <= 0 ){
			printError( "+ Warning: timeout waiting for more data...\n", 1);
		}
	        ioctl(fd, FIONREAD, &bytes);
		DEBUG2("waitFlag in while: %d\n", bytes);
                if ( bytes ) {
                   /* input available */
                   if ((res = read(fd, buffer+n, BUFLEN-n)) > 0) {
			   n+=res;
 	           }
		   DEBUG2("<- (%d) ", res);
        	   FOR(i = 0; i < n; i++)
            		   DEBUG2("%x ", buffer[i]);
                   bytes=0; 
		}else{
		   if( doWait ){
                   	ts.tv_sec=0;
		   	ts.tv_nsec=1E6L; /* wait up to 1 millisec */
		   	nanosleep(&ts, NULL);
		   }
		}
		if( ! doWait /*&& wait_flag*/ )
			break;
        }

	DEBUG3("minorFault: %d;  n=%d\n", minorFault, n)
	DEBUG1("end readData\n");

	return(n);
}


/* **************************************** */
/* Setup Communication with Weather station */
/* **************************************** */
int startCom(char * port) {
   int fd, trycount, rdstat, i;
   struct timespec ts;

   DEBUG1("begin startCom\n");

   fd=openSerial(port);
   if( fd < 0 )
   	return(fd);


   clearDtr(fd);
   setRts(fd);       /* This will stop up the station */

   ts.tv_sec=0;
   ts.tv_nsec=9E7L;  /* wait 0.09 sec for weatherst to come up */
   nanosleep(&ts, NULL);

   setDtr(fd);
   clearRts(fd);       /* This will start up the station */

   ts.tv_sec=0;
   ts.tv_nsec=4E7L;   /* wait 0.04 sec for weatherst to come up */
   nanosleep(&ts, NULL);

   /* Write START command to interface until it finally will answer */
   for(trycount=400; trycount > 0; trycount--){
        sendCommand(fd, STARTCOM, 0);
	// Interface need 30 ms to stablize, let's give it 40ms
        ts.tv_sec=0;
        ts.tv_nsec=4E7L;   /* wait 0.04 sec for weatherst to come up */
        nanosleep(&ts, NULL);

	rdstat=readData(fd, 0);

        if( rdstat == 5 && buffer[0] == STX &&
            buffer[1] == 1 &&
            buffer[2] == ACK &&  buffer[3] == (u_char)0xf7 &&
            buffer[4] == ETX ){ break; }
	 else{
            FOR (i=0; i<rdstat; i++){
                  DEBUG2("%x ", buffer[i]);
            }
            DEBUG2("%d \n", rdstat);
	 }
   }

   if( trycount == 0 ){ /* did we receive an answer or timeout */
           printError("*** Error: DTR not acknowledged. No answer from weather station.\n", 1);
           return E_ERROR;
   }else {
        //printf("*** Successfully connected to station...\n");
   }
   ts.tv_sec=0;
   ts.tv_nsec=1E5L;
   nanosleep(&ts, NULL);
   // Willem Eradus 19-06-2003
   // ordering the flushing co first, drain, and flush the input
   tcflush(fd, TCOFLUSH);
   tcdrain(fd);
   tcflush(fd, TCIFLUSH);

   DEBUG1("end startCom\n");

   return(fd);
}



/* utility functions --------------------------------------------------- */
/* Taken from Friedrich Zabels wx2000 -- Weather Data Logger             */
/* isolates one bit from byte */
u_char getBit(u_char byte, u_char bit)
{
        return byte >> bit & 0x01;
}

/* isolates 2 bits from byte */
u_char get2bits(u_char byte, u_char bit)
{
        return byte >> bit & 0x03;
}

/* isolates 3 bits from byte */
u_char get3bits(u_char byte, u_char bit)
{
        return byte >> bit & 0x07;
}


/* isolates high nibble from byte */
u_char getHiNibble(u_char byte)
{
        return byte >> 4 & 0x0f;
}

/* isolates low nibble from byte */
u_char getLoNibble(u_char byte)
{
        return byte & 0x0f;
}


/* Convert time_t type (sec since 1.1.1970) to human redable date format */
char *timeToDate(time_t *t, int timeMode){
   static char timeascbuf[64];
   char *p;
   
   /* Convert time-value to readable calendar format */
   timeascbuf[0]='\0';
   if( timeMode == LOCALTIME ){
	   asctime_r(localtime(t), (char *)timeascbuf);
   }else{
	   asctime_r(gmtime(t), (char *)timeascbuf);
   }	   
   p=rindex((char*)timeascbuf, (int)'\n');
   if( p != NULL )
   	*p='\0';
   
   return((char *)timeascbuf);	
}


/* convert <ENQ><DC2> to <STX>, <ENQ><DC3> to <ETX>, <ENQ><NAK> to <ENQ> */
/* Taken from Friedrich Zabels wx2000 software                           */
int cleanData(int len)
{
        int a;

   	DEBUG1("begin cleanData\n");

        DEBUG2("Dirty: (%d) ", len);
        FOR(a = 0; a < len; ++a)
            DEBUG2("%x ", buffer[a]&255);
        DEBUG1("\n");

        for (a = 0; a < len - 1; ++a) {
                char c = '\0';
                if (buffer[a] == ENQ && buffer[a + 1] == DC2)
                        c = STX;
                else if (buffer[a] == ENQ && buffer[a + 1] == DC3)
                        c = ETX;
                else if (buffer[a] == ENQ && buffer[a + 1] == NAK)
                        c = ENQ;
                if (c) {
                        buffer[a] = c;
                        memmove(buffer + a + 1, buffer + a + 2,
                                len - a - 2);
                        --len;
                }
        }

        DEBUG2("Clean: (%d) ", len);
        FOR(a = 0; a < len; a++)
            DEBUG2("%x ", buffer[a]&255);
        DEBUG1("\n");
   	DEBUG1("end cleanData\n");

        return len;
}


/* chops off first and last two bytes; checks length and checksum */
/* Taken from Friedrich Zabels wx2000 software                           */
int trimData(int len)
{
        u_char length, checksum, sum;
        int a;

   	DEBUG1("begin trimData\n");

        DEBUG2("No trim: (%d) ", len);
        FOR(a = 0; a < len; a++)
            DEBUG2("%x ", buffer[a]&255);
        DEBUG1("\n");

        if (buffer[0] != STX || buffer[len - 1] != ETX) {
                printError("*** Error trimData: Invalid dataformat detected \n", 1);
		return -1;
        }

        length = buffer[1];
        if (length != len - 4) {
                return -1;
        }

        checksum = buffer[len - 2];
        sum = 0;
        for (a = 0; a < len - 2; ++a)
                sum += buffer[a];
        sum += checksum;
        if (sum != 0) {
                return -1;
        }

        /* remove <STX> & length */
        memmove(buffer, buffer + 2, len - 2);
        /* 'remove' checksum & <ETX> */

        DEBUG2("Trimmed: (%d) ", length);
        FOR(a = 0; a < length; a++)
            DEBUG2("%x ", buffer[a]&255);
        DEBUG1("\n");

        if (length == 1 && buffer[0] == NAK) {
                length = -1;
        }

   	DEBUG1("end trimData\n");

        return length;
}


/* ****************************** */
/* Read DCF time from buffer data */
/* ****************************** */
void readDcf(DCF_INFO *dcfInfo, BOOL useSystemTime)
{
   DEBUG1("begin getDcf\n");


   if( useSystemTime ){ 
      dcfInfo->dcfStatus=0;
      printError("+ Warning: \"DCF OK\" set to \"No\" due to user given option -S \n", 0);
   }else{  
      dcfInfo->dcfStatus = getBit(buffer[4], 7);
      dcfInfo->hour = getHiNibble(buffer[0]) * 10 + getLoNibble(buffer[0]);
      dcfInfo->min = getHiNibble(buffer[1]) * 10 + getLoNibble(buffer[1]);
      dcfInfo->sec = buffer[2];

      dcfInfo->day = getHiNibble(buffer[3]) * 10 + getLoNibble(buffer[3]);
      dcfInfo->month = getLoNibble(buffer[4]);
      dcfInfo->weekday = get3bits(buffer[4], 4);
      dcfInfo->year	   = 2000 + (getLoNibble(buffer[5]) +
   				      10* getHiNibble(buffer[5]) );

      /* Avoid trouble in leap years in the time from Feb 28 00:00 */
      /* to Feb 29 02:59 when the station does a resync with DCF   */
      /* (it does so each day at 03:00)                            */
      /* In this time simply fake that there is no valid DCF time  */
      /* so the linux system time will be used  instead            */
      if( dcfInfo->dcfStatus && (dcfInfo->month == 3) && (dcfInfo->day == 1) ){
	  if( dcfInfo->hour < 3 ){
	    dcfInfo->dcfStatus=0; 
	    printError("+ Warning: \"DCF OK\" set to \"No\" due to possible leap year problem.\n", 0);

	  }
      }
   }   


   DEBUG1("end getDcf\n");
}


/* ****************** */
/* print out DCF time */
/* ****************** */
void printDcf(DCF_INFO dcfInfo)
{
   struct tm t;
   time_t theTime;
   int timeMode=LOCALTIME;  	/* May be LOCALTIME or GMTIME */
   char timeascbuf[64];
   static const char *weekday[] = {
                "sunday",
		"monday", "tuesday", "wednesday", "thursday",
                "friday", "saturday"
        };

        DEBUG1("begin printDcf\n");
   if( ! config.printTimeOnly ){
        printf("\n");
	
        printf("DCF OK   : %s\n", dcfInfo.dcfStatus ? "YES" : "NO");
	printf("Weekday  : %s\n", weekday[dcfInfo.weekday]);
        printf("Time     : %02d:%02d:%02d\n", dcfInfo.hour,
			               		dcfInfo.min, dcfInfo.sec);
        printf("Day      : %02d\n", dcfInfo.day);
        printf("Month    : %02d\n", dcfInfo.month);
        printf("Year     : %04d\n", dcfInfo.year);
	printf("Unix date: %02d%02d%02d%02d%4d.%02d\n", 
				dcfInfo.month, dcfInfo.day,
				dcfInfo.hour, dcfInfo.min,
				dcfInfo.year, dcfInfo.sec	);
        printf("\n");

   }else{ 
   	   /* Possibly convert DCF time to GMTIME */
   	   t.tm_sec=  dcfInfo.sec;
	   t.tm_min=  dcfInfo.min;
	   t.tm_hour= dcfInfo.hour;
	   t.tm_mday= dcfInfo.day;
	   t.tm_wday= dcfInfo.weekday;
	   t.tm_mon=  dcfInfo.month-1;
	   t.tm_year= dcfInfo.year-1900;
	   t.tm_isdst=-1; /* Ignore daylight saving time */

   	   if( (theTime=mktime(&t)) < 0 ){
   		printError( "*** Error: Cannot convert DCF time to unix time_t\n", 1);
		return;
	   }
	   if( timeMode == LOCALTIME ){
	   	localtime_r(&theTime, &t);
	   }else{
	   	gmtime_r(&theTime, &t);
	   }
      
      if( config.printTimeOnly== 1){ /* We could identify different formats */
	   printf("%02d%02d%02d%02d%4d.%02d\n",
				   t.tm_mon+1, t.tm_mday,
				   t.tm_hour, t.tm_min,
				   t.tm_year+1900, t.tm_sec	);

      }else if(config.printTimeOnly== 2 ){
           asctime_r(&t, (char *)timeascbuf);
	   printf("%s\n", timeascbuf);
      }
   }
	

        DEBUG1("end printDcf\n");
}


/* ***************************************************
* Read the status ofthe weatherstation        
* **************************************************** */
void readStatus(WS2500_STATUS *ws2500Stat, int numBytes)
{
   int i, lo, hi;

   DEBUG1("start readStatus\n");

   /* Status of MAXTHSENS temperature sensors */
   for(i=0; i<MAXTHSENS; i++){
   	ws2500Stat->tempSens[i]=(u_char)buffer[i];
   }

   /* Depending on the type of station the reply is either 16 or 17 bytes long */
   if( numBytes == 16 ){
	   /* Other data */
	   ws2500Stat->version		=10; /* version 1.0 */
	   ws2500Stat->rainSens		=(u_char)buffer[8];
	   ws2500Stat->windSens		=(u_char)buffer[9];
	   ws2500Stat->lightSens	=(u_char)buffer[10];
	   ws2500Stat->pyranSens	=(short)buffer[11];
	   ws2500Stat->insideSens	=(u_char)buffer[12];
	   ws2500Stat->interval	 	=buffer[13];

	   ws2500Stat->ws2500Lang	=getBit(buffer[14], 0);
	   ws2500Stat->dcfInSync	=getBit(buffer[14], 1);
	   ws2500Stat->hasDcf		=getBit(buffer[14], 2);
	   ws2500Stat->protocol		=getBit(buffer[14], 3);
	   ws2500Stat->ws2500Type	=getBit(buffer[14], 4);
	   ws2500Stat->addrSensInside	=get3bits(buffer[14], 5);

	   /* Firmware version of station */
	   lo				=getLoNibble(buffer[15]);
	   hi				=getHiNibble(buffer[15]);

	   if( lo !=  0 || hi != 1 ){
	      sprintf(errBuffer, "+ Warning: Station firmware version mismatch. Contact author\n");
	      sprintf(errBuffer+strlen(errBuffer), "             should be 1.0 but is %d.%d\n", hi, lo);
	      printError(errBuffer, 0);
	   }
	   ws2500Stat->version=hi*10+lo;

	   ws2500Stat->addrSensRain	=-1;
	   ws2500Stat->addrSensWind	=-1;
	   ws2500Stat->addrSensPyran	=-1;
           ws2500Stat->addrSensLight	=-1;

   }else if( numBytes == 17 ){
	   /* Other data */
	   ws2500Stat->version		=31;  /* version 3.1 */
	   ws2500Stat->rainSens		=(u_char)buffer[8];
	   ws2500Stat->windSens		=(u_char)buffer[9];
	   ws2500Stat->lightSens	=(u_char)buffer[10];
	   ws2500Stat->insideSens	=(u_char)buffer[11];
	   ws2500Stat->interval	 	=buffer[12];

	   ws2500Stat->pyranSens	=-1;

	   ws2500Stat->ws2500Lang	=getBit(buffer[13], 0);
	   ws2500Stat->dcfInSync	=getBit(buffer[13], 1);
	   ws2500Stat->hasDcf		=getBit(buffer[13], 2);
	   ws2500Stat->protocol		=getBit(buffer[13], 3);
	   ws2500Stat->ws2500Type	=getBit(buffer[13], 4);

	   /* Firmware version of station */
	   lo				=getLoNibble(buffer[14]);
	   hi				=getHiNibble(buffer[14]);
            
           if( (hi != 1 && hi != 3 ) || 
	       (hi==1 && (lo >3 || lo <= 0)) || (hi==3 && (lo > 1 || lo <= 0)) ){
	      sprintf(errBuffer,"+ Warning: Station firmware version mismatch. Contact author\n");
	      sprintf(errBuffer+strlen(errBuffer),"             should be one of 3.1, 1.1, 1.2, 1.3 but is %d.%d\n", hi, lo);
	      printError(errBuffer, 0);
	   }
	   ws2500Stat->version=hi*10+lo;

	   ws2500Stat->addrSensRain	=get3bits(buffer[15], 0);
	   ws2500Stat->addrSensWind	=get3bits(buffer[15], 4);
	   ws2500Stat->addrSensLight	=get3bits(buffer[16], 0);
	   ws2500Stat->addrSensInside	=get3bits(buffer[16], 4);
   }else{
   	printError("+ Warning: Reply to status request has unknown length\n", 0);
   }

   DEBUG1("end readStatus\n");
}


/* ****************************************************************************** */
/* Map the status of sensors to the tolerance status. This is used to disable     */
/* tolerance check for a sensor that was present last time the lastvalue file     */
/* was written but is no longer (eg sensor defect). In this case we may no longer */
/* do any tolerance checks for this sensor.                                       */
/* ****************************************************************************** */
void ws2500Status2tolStatus(WS2500_STATUS *ws2500Stat)
{
   int i;

   for(i=0; i<MAXTHSENS; i++){
   	if( ws2500Stat->tempSens[i] < 16 ){		/* TH sensor does not exist */
	   	ws2500Stat->tolStat.t_currErr[i]=-1;	/* disable tolcheck 	    */
	   	ws2500Stat->tolStat.h_currErr[i]=-1;
	}	
   }
   if( ws2500Stat->insideSens < 16 ){	      /* Inside sensor does not exist */
   	ws2500Stat->tolStat.inside_h_currErr=-1;
   	ws2500Stat->tolStat.inside_t_currErr=-1;
   }	
   
   /* Disable tolcheck for other sensors if they do NOT exist */
   if( ws2500Stat->rainSens < 16 )    ws2500Stat->tolStat.r_currErr=-1;
   if( ws2500Stat->windSens < 16 )    ws2500Stat->tolStat.ws_currErr=-1;
   if( ws2500Stat->insideSens < 16 )  ws2500Stat->tolStat.p_currErr=-1;
   if( ws2500Stat->lightSens < 16 )   ws2500Stat->tolStat.lux_currErr=-1 ;
   if( ws2500Stat->pyranSens < 16 )   ws2500Stat->tolStat.energy_currErr=-1;
}


/* ************************************* */
/* decode and print status of one sensor */
/* ************************************* */
void printOneSensStat(int status){
   if( status <16 )   	  printf("not available\n");
   else if( status == 16) printf("is OK \n");
   else if( status > 16 ) printf("had %d drop outs\n", status-16);
}


/* ******************************************* */
/* Print out status values from weatherstation */
/* ******************************************* */
void printStatus(WS2500_STATUS *ws2500Stat)
{
   int i;

   DEBUG1("start printStatus\n");


   printf("Sensor address information:\n");
   printf("\tAddress of inside sensor: %d\n", ws2500Stat->addrSensInside);


   if( ws2500Stat->ws2500Type == 1 || ws2500Stat->version >= 13  ){ /* 2500 PC | ws2500+Firmware >= 1.3*/
      printf("\tAddress of rain sensor:   %d\n", ws2500Stat->addrSensRain);
      printf("\tAddress of wind sensor:   %d\n", ws2500Stat->addrSensWind);
      printf("\tAddress of light sensor:  %d\n", ws2500Stat->addrSensLight);
      /* According to the docs I have neither WS2500 nor WS2500 PC return the
          sensor address of the pyranometer Sensor
       	  
      printf("\tAddress of pyranometer sensor: %d\n", ws2500Stat->addrSensPyran);
      */
   }else{
      printf("\tAddress of rain sensor:   addr not available\n");
      printf("\tAddress of wind sensor:   addr not available\n");
      printf("\tAddress of light sensor:  addr not available\n");
   }   
   

   printf("\nSensor status information of WS2500 station:\n");
   
   printf("\tStatus of temperature sensors:\n");
   for(i=0; i< MAXTHSENS; i++){
   	printf("\t\tSensor %d: ",i+1);
	printOneSensStat(ws2500Stat->tempSens[i]);
   }
   
   printf("\tStatus of rain sensor:        ");
   printOneSensStat(ws2500Stat->rainSens);
   
   printf("\tStatus of wind sensor:        ");
   printOneSensStat(ws2500Stat->windSens);

   printf("\tStatus of light sensor:       ");
   printOneSensStat(ws2500Stat->lightSens);

   printf("\tStatus of pyranometer sensor: ");
   printOneSensStat(ws2500Stat->pyranSens);
   
   printf("\tStatus of inside sensor:      ");
   printOneSensStat(ws2500Stat->insideSens);
   
   
   printf("\nGeneral Information:\n");
   printf("\tInterval time:    %d min (=> recording time: %3.1f days)\n", ws2500Stat->interval,
   					(ws2500Stat->interval *1024.0)/60/24
					); 
   printf("\tVersion Number:   %d.%d\n", ws2500Stat->version/10,
   					 ws2500Stat->version%10);
   printf("\tWS2500 language:  %s\n", ws2500Stat->ws2500Lang==1?"English":"German");
   printf("\tDcf availavility: %s\n", ws2500Stat->hasDcf==1?"Yes": "No");
   printf("\tDcf is in sync:   %s\n", ws2500Stat->dcfInSync==1?"Yes": "No");
   printf("\tProtocol version: %s\n", ws2500Stat->protocol==0?"1.2": "1.1");
   printf("\tWS2500 type:      %s\n", 
   			ws2500Stat->ws2500Type==1?"WS2500 PC": "WS2500");

   DEBUG1("end printStatus\n");
}


/* **************************************************** */
/* check if humidity value is correct and return value  */
/* calculated from low and high digits, eg 45%          */
/* bcdLow is low digit (5), bcdHigh is high digit (4)   */
/* for hum                                              */
/* **************************************************** */
u_char calcCheckHum( short bcdLow, short bcdHigh, u_char *new, u_char sensId  )
{
   /* According to ELV low low digit of humidity is > 9 only if the 
    * value  could not be measured or its too large or to low
    */ 
   if( bcdLow > 9 ){
   	*new=DSETSTAT_HUMIDITY_LOW;
	if(sensId > 0 )
	   sprintf(errBuffer, "+ Warning: Hum value from TH sensor %d is invalid. Set to minimum: %d \n", 
	                      sensId, LOWEST_HUMIDITY );
	else
	   sprintf(errBuffer, "+ Warning: Hum value from inside sensor is invalid. Set to minimum: %d \n",
	                      LOWEST_HUMIDITY );
	
        printError(errBuffer, 0);

	return(LOWEST_HUMIDITY);   
   }else{
        /* the switch() below is actually not needed its here just for clarity */
	/* the functionality could also be done by formatNewFlag()             */
   	switch(*new){
	    case 1:  *new=DSETSTAT_OK;      break;
	    case 0:  *new=DSETSTAT_DROPOUT; break;
	}
	
	/* The humidity calculated from low and high is real_hum-20%. So add 20% */
	return(20+ (10*bcdHigh+bcdLow)); /* return humidity value */
   }
}



/* **************************************************** */
/* Decode rain sensor data received from station        */
/* buf points to the first byte with this data          */
/* mode tells if only 7 bit rain and a new bit or       */
/* 8 bit rain data should be fetched (WS2500<->WS2500PC */
/* **************************************************** */
void decodeRainData(u_char *buf, WS2500_RAIN *rainSens, u_char mode)
{
    /* Get data for rain sensor:                                  */
    if( ! mode ){ /* Bios Version 1.0 */
      rainSens->count=buf[0] & 0x7f;
      rainSens->new=getBit(buf[0], 7);
    }else{	/* Bios 1.1 or 3.1 */
      rainSens->count= ((u_char *)buf)[0] + ((int) get3bits(buf[1], 0) <<8);
      rainSens->new=getBit(buf[1], 3);
    }
}


/* **************************************************** */
/* Decode wind sensor data received from station        */
/* buf points to the first byte with this data          */
/* **************************************************** */
void decodeWindData(u_char *buf, WS2500_WIND *windSens)
{
    u_char tmp;

    windSens->speed=(getLoNibble(buf[0]) / 10.0) +
   			       (getHiNibble(buf[0])  )         +
			       (getLoNibble(buf[1]) *10.0) ;

    windSens->direction= (getHiNibble(buf[1]) *10)   +
   				    (get2bits(buf[2], 0) * 100) +
				    (getBit(buf[2], 4) * 5);
    tmp=get2bits(buf[2], 2);
    switch(tmp){
   	 case 0: windSens->variance=0.0;  break;
   	 case 1: windSens->variance=22.5; break;
   	 case 2: windSens->variance=45;   break;
   	 case 3: windSens->variance=67.5; break;
	 default:
	   printError("+ Warning: Unknown wind variance coding. Skipped\n", 0);
	 break;
    }
    windSens->new=getBit(buf[2], 7);
}


/* **************************************************** */
/* Decode inside sensor data received from station      */
/* buf points to the first byte with this data          */
/* **************************************************** */
void  decodeInsideData(u_char *buf, WS2500_INSIDE *insideSens)
{
   insideSens->th.temp=(getHiNibble(buf[1]) / 10.0) +
   			 	  getLoNibble(buf[2])          +
				  (get3bits(buf[2], 4) * 10.0);
   
   /* Since the inside sensor has both a temp/hum value and a pressure value
    * and since the hum value might have an error that is not signalled in 
    * the new flag (but checked in calcCheckHum() ) we artificially introduce
    * a new flag for the pressure and a seperate one for temp/hum. Initially
    * both get the value from the station, however the temp/hum new flag
    * might be set to 'h' in calcCheckHum() to signal an error in the 
    * humidity value. Without
    * this seperation the pressure would also carry the error flag in this
    * situation alltough it is correct.
   */
   insideSens->newTh=insideSens->newP=getBit(buf[3], 7);
   if( getBit(buf[2],7) )
   	insideSens->th.temp*=-1.0;
   
   insideSens->th.hum=
	           calcCheckHum( getLoNibble(buf[3]), get3bits(buf[3], 4), 
	                         &(insideSens->newTh), 0 );		      

   insideSens->pressure=getLoNibble(buf[0])        +
   				   (getHiNibble(buf[0]) *10) +
				   (getLoNibble(buf[1]) *100);
}


/* **************************************************** */
/* Decode light sensor data received from station       */
/* buf points to the first byte with this data          */
/* **************************************************** */
void decodeLightData(u_char *buf, WS2500_LIGHT *lightSens)
{
   u_char tmp;
   
   lightSens->lux=	getLoNibble(buf[0])      +
   				(getHiNibble(buf[0]) *10) +
				(getLoNibble(buf[1]) * 100) ;
   tmp=get2bits(buf[1], 4);
   switch(tmp){
   	case 0: lightSens->factor=1;    break;
   	case 1: lightSens->factor=10;   break;
   	case 2: lightSens->factor=100;  break;
   	case 3: lightSens->factor=1000; break;
	default: 
	  printError("+ Warning: Unknown light factor coding. Skipped\n", 0);
	break;
   }	

   lightSens->sunshine=getBit(buf[1], 6);
   lightSens->new=getBit(buf[1], 7);
}


/* **************************************************** */
/* Decode pyranometer sensor data received from station */
/* buf points to the first byte with this data          */
/* **************************************************** */
void decodePyranData(u_char *buf, WS2500_PYRAN *pyranSens)
{
   u_char tmp;

   pyranSens->energy= getLoNibble(buf[0])        +
   				 (getHiNibble(buf[0]) *10)  +
				 (getLoNibble(buf[1]) * 100);

   tmp=get2bits(buf[1], 4);
   switch(tmp){
   	case 0: pyranSens->factor=1;    break;
   	case 1: pyranSens->factor=10;   break;
   	case 2: pyranSens->factor=100;  break;
   	case 3: pyranSens->factor=1000; break;
	default:
	  printError("+ Warning: Unknown pyranometer factor coding. Skipped\n", 0);
	break;
   }
   pyranSens->new=getBit(buf[1], 7);
}


/* **************************************************** */
/* Decode sunshine duration received from station       */
/* buf points to the first byte with this data          */
/* **************************************************** */
void decodeSunDuration(u_char *buf, WS2500_SUN *sunDuration)
{
   /* 12 bit */
   sunDuration->sunDur= 	(getHiNibble(buf[1]) <<8) +
   				(getLoNibble(buf[1])  <<4) +
				getHiNibble(buf[0]);
}


/* *********************************************************************
 * Function to postprocess data read from station. At the moment here we
 * adjust the relative pressure due to height of station, and we
 * check if there were to many dropouts for one sensor
 * The function return < 0 which indicates an error or 1 which inticates
 * the status OK
 * **********************************************************************/
int postProcessData(WS2500_DATA *ws2500Data, WS2500_STATUS *ws2500Stat)
{
   int i;
   char *ptime;
   char *gmptime;
   int ret;

   DEBUG1("start postProcessData\n");
   ret=1;

   /* convert time_t to human redable date format */
   /* We choose output in local time here since this */
   /* most useful for the user                       */
   ptime=timeToDate(&ws2500Data->time, LOCALTIME);
   gmptime=timeToDate(&ws2500Data->time, GMTIME);

   /* Adjust pressure to relative value if altitude is != 0 */
   ws2500Data->insideSens.pressure= (int)((ws2500Data->insideSens.pressure +
	 				    config.altitude * 0.11) + 0.5);

   for(i=0; i<MAXTHSENS; i++){
	if( config.maxDropOuts && (ws2500Stat->tempSens[i] - 16) > config.maxDropOuts ){
		sprintf(errBuffer, "+ %s GMT, (%s): Warning: Drop out chk: Too many drop outs (%d) for TH-sensor %d\n",
									gmptime, ptime,
									ws2500Stat->tempSens[i]-16, i+1);
		printError(errBuffer, 0);
		ret=E_TOOMANYDROPOUTS;
	}
   }

   /* Inside sensor */
   if( config.maxDropOuts && (ws2500Stat->insideSens -16 ) > config.maxDropOuts){
		sprintf(errBuffer, "+ %s: Warning: Drop out chk: Too many drop outs (%d) for inside-sensor.\n",
									ptime,
									ws2500Stat->insideSens-16 );
		printError(errBuffer, 0);
		ret=E_TOOMANYDROPOUTS;
   }


   /* Rain sensor output */
   if( config.maxDropOuts && (ws2500Stat->rainSens-16) > config.maxDropOuts){
		sprintf(errBuffer, "+ %s: Warning: Drop out chk: Too many drop outs (%d) for rain-sensor.\n",
		 							ptime,
		 							ws2500Stat->rainSens-16 );
		printError(errBuffer, 0);
		ret=E_TOOMANYDROPOUTS;
   }


   /* Wind sensor output */
   if( config.maxDropOuts && (ws2500Stat->windSens-16) > config.maxDropOuts){
		sprintf(errBuffer, "+ %s: Warning: Drop out chk: Too many drop outs (%d) for wind-sensor.\n",
		 							ptime,
		 							ws2500Stat->windSens-16);
		printError(errBuffer, 0);
		ret=E_TOOMANYDROPOUTS;
   }

   /* Light sensor data */
   if( config.maxDropOuts && (ws2500Stat->lightSens-16) > config.maxDropOuts){
		sprintf(errBuffer, "+ %s: Warning: Drop out chk: Too many drop outs (%d) for light-sensor.\n",
		 							ptime,
		  							ws2500Stat->lightSens-16);
		printError(errBuffer, 0);
		ret=E_TOOMANYDROPOUTS;
   }


   /* Pyranometer sensor data */
   if( config.maxDropOuts &&  (ws2500Stat->pyranSens-16) > config.maxDropOuts){
		sprintf(errBuffer, "+ %s: Warning: Drop out chk: Too many drop outs (%d) for pyran-sensor.\n",
		 							ptime,
		  							ws2500Stat->pyranSens-16);
		printError(errBuffer, 0);
		ret=E_TOOMANYDROPOUTS;
   }


   DEBUG1("end postProcessData\n");

   return( ret );
}

/* ***************************************************************************
* check if timestamp for dataset has a reasonable value compared to the      
* current linux system time. The timestamp for the dataset should eg         
* not be a year in the past (seen from linux system time)                     
* If there is a invalid difference the function will terminate the program    
* except for the case where the user sert option -i when calling ws2500       
*  dcfStatus: info if dcd time from station was ok                            
*  ws2500Time: Time to be used entered for ws2500 data set                    
*  theTime: current time either from DCF-clock (if OK) or else from system    
*  dataReadOffset: timeoffset that might sum up while reading many datasets   
*                  from the station   (sec)                                   
*  dataTimeOffset: Offset from "now" to time for current ws2500 data set (sec)                  
* *************************************************************************** */
int checkDataTimestamp(u_char dcfStatus, time_t ws2500Time, time_t theTime, 
                        time_t dataReadOffset, unsigned long dataTimeOffset)
{
   const time_t maxOffset=MAX_DATATIMEOFFSET;
   time_t now;
   int tmp;
   char * ptime;
   

   now=time(NULL);   /* get system time */
    
   if( (tmp=abs((unsigned long)ws2500Time-(unsigned long)now)) > maxOffset ){
       if( ! config.ignoreTimeErr ){
	  fprintf(stderr, "*** Error: Too big time offset in data.\n");
	  fprintf(stderr, "* There was a huge time offset (%d days) from  the current linux system time\n", tmp/3600/24);
	  fprintf(stderr, "* to the time of the ws2500 data set read from the station. Please check the\n");
	  fprintf(stderr, "* time of your linux system. The current value is printed below. If you simply \n");
	  fprintf(stderr, "* choose to ignore this time offset in the future, call the program with \n");
	  fprintf(stderr, "* option \"-i\" on your own risk of getting data with wrong timestamps!\n");
	  fprintf(stderr, "* If your system clock is ok it might also help to have the ws2500 station \n");
	  fprintf(stderr, "* resync with the DCF signal which is automatically done at 03:00am. \n*\n");
	  fprintf(stderr, "* Some more information about the problem (time values are in local time): \n");

	  ptime=timeToDate(&now, LOCALTIME);
	  fprintf(stderr, "* Current linux system time:          %s\n", ptime);

	  if( dcfStatus ){
             ptime=timeToDate(&theTime, LOCALTIME);
	     fprintf(stderr, "* DCF time (is OK):                   %s \n", ptime);
	  }else{
	     fprintf(stderr, "* DCF timenot OK (was not used)\n");
	  }  

	  ptime=timeToDate(&ws2500Time, LOCALTIME);
	  fprintf(stderr, "* Date/time for w2500 data set:       %s\n", ptime);

	  fprintf(stderr, "* Timeoffset in dataset relativ to \"now\" (sec): %lu (in days:%lu) \n", 
       							   dataTimeOffset, dataTimeOffset/3600/24 );
	  fprintf(stderr, "* Additional time error caused by reading many datasets (sec): %lu \n", (unsigned long)dataReadOffset );


	  fprintf(stderr, "* Exit due to error!\n\n");
	  return(E_TIMEDIFFTOBIG);
       }else{
          fprintf(stderr, "+ Warning: Too big time offset in data. To see more don't call with option \"-i\" \n");
       }
   }
   return(0);
}			


/* ****************************************************
*  retrieve all sensor data from buffer for one dataset
*
* PC Version 3.1:
*
* thanks to Thorsten: ws2500@tbis.de:
* MAXTHSENS temperature humidity sensors
*
* Windsensor
* Innensensor
* Regensensor (Achtung 8 Bit!! 0 - 255) Neuflag entf�llt
*
* Sonnenscheindauer
* Helligkeitssensor
* Pyranometer entf�llt.
*
* WS2500 1.0
*
* Regensensor (7-Bit) 0- 127 !
* Windsensor
* Innensensor
* Helligkeitssensor
* Pyranometer
*
* We return 1 if processing of data was OK or < 0 which indicates an error
*/
int getData(WS2500_DATA *ws2500Data, DCF_INFO *dcfInfo,
            WS2500_STATUS *ws2500Stat)
{
   int i, j, tmp, ret;
   static int dcfNotAvailable=0;
   static time_t firstTime=0;
   u_char *buf;
   struct tm t;
   time_t theTime, tmpTime; 	 /* Seconds since 1.1. 1970 */
   DEBUG1("start getData\n");

   tmpTime=0;

   ws2500Data->blockNr=((buffer[1]&255)<<8) | (buffer[0]&255); /* Blocknumber*/

   /* ---------------------------------------------------------- */
   /* Store date of dataset into structure                       */
   /* time is stored in unix fashion, in seconds since 01.01.1970*/

   /* Get difference in minutes from now for current dataset */
   tmp=((buffer[3]&255)<<8) + (buffer[2]&255);

   if(dcfInfo->dcfStatus){
	   t.tm_sec=  dcfInfo->sec;
	   t.tm_min=  dcfInfo->min;
	   t.tm_hour= dcfInfo->hour;
	   t.tm_mday= dcfInfo->day;
	   t.tm_mon=  dcfInfo->month-1;
	   t.tm_year= dcfInfo->year-1900;
	   t.tm_isdst=-1; /* Ignore daylight saving time */

	   if( (theTime=mktime(&t)) < 0 ){
   		printError( "*** Error: Cannot convert DCF time to unix time_t\n", 1);
		return(-1);
	   }
   }else{
   	theTime=time(NULL);
   	if( !dcfNotAvailable ) 
		printError( "+ Warning: DCF time not available. Using system time.\n", 0);
	dcfNotAvailable=1; /* print DCF warning only one time per call */	
   }

   /* Store timestamp */
   ws2500Data->time=theTime-(tmp*60);


   if( dcfInfo->dcfStatus ){ /* DCF is OK */
      /* Store when we were here last time to get time difference */
      /* between fisrt and succeeding  calls of this function     */
      tmpTime=time(NULL);

      /* Now add timedifference since last call to timestamp  */
      /* we do so only if DCF is available, cause else we get */
      /* our time from the system anyway, see above           */
      if( firstTime ){
   	   ws2500Data->time += (tmpTime-firstTime);
      }else{
   	   firstTime=tmpTime;  /* Initialize firstTime if zero */
      }	
   }

   /* check if timestamp for dataset has a reasonable value compared to the  */
   /* current linux system time. The timestamp for the dataset should eg     */
   /* not be a year in the past (seen from linux system time)                */
   if( (i=checkDataTimestamp(dcfInfo->dcfStatus,ws2500Data->time, theTime, (tmpTime-firstTime), tmp*60)) < 0){
   	return(i);
   }
   			
   buf=buffer+4;

   /* ---------------------------------------------------------- */
   /* Now get data for temp humidity sensors                     */
   /* First get the data of all "even" sensors                   */
   for(i=0,j=0; i<MAXTHSENS; i+=2, j+=5){
      if( ws2500Stat->tempSens[i] >=16 ){
	ws2500Data->thSens[i].temp= (getLoNibble(buf[j]) / 10.0) +
					getHiNibble(buf[j])      +
					(get3bits(buf[j+1], 0) * 10.0);
	if( getBit(buf[j+1],3) )
		ws2500Data->thSens[i].temp*=-1.0;

	ws2500Data->thSens[i].new= getBit(buf[j+2], 3);
	
	/* calc hum from low and high digits and check if valid. Set ".new" status */
	ws2500Data->thSens[i].hum=
	           calcCheckHum( getHiNibble(buf[j+1]), get3bits(buf[j+2], 0), 
	                         &ws2500Data->thSens[i].new, i+1 );		      
	}			 
   }

   /* Now get the "odd" sensors */
   for(i=1,j=2; i<MAXTHSENS; i+=2,j+=5){
      if( ws2500Stat->tempSens[i] >=16 ){
	ws2500Data->thSens[i].temp= (getHiNibble(buf[j]) / 10.0) +
					getLoNibble(buf[j+1])      +
					(get3bits(buf[j+1], 4) * 10.0);
	if( getBit(buf[j+1],7) )
		ws2500Data->thSens[i].temp*=-1;

	ws2500Data->thSens[i].new= getBit(buf[j+2], 7);
	ws2500Data->thSens[i].hum=
	           calcCheckHum( getLoNibble(buf[j+2]), get3bits(buf[j+2], 4), 
	                         &ws2500Data->thSens[i].new, i+1 );		      
      }
   }

   if( ws2500Stat->version == 10 ){ /* Bios version 1.0 */
       /* Get data for rain sensor:                                  */
       if( ws2500Stat->rainSens >=16 )
       	  decodeRainData(&buf[20], &ws2500Data->rainSens, 0 );
       /* Get data for Wind sensor                                   */
       if( ws2500Stat->windSens >=16 )
          decodeWindData(&buf[21], &ws2500Data->windSens);
       /* Get data from inside sensor                                */
       /* this is: temperature, humidity and pressure                */
       if( ws2500Stat->insideSens >=16 )
          decodeInsideData(&buf[24], &ws2500Data->insideSens);
       /* Get data for light sensor                                  */
       if( ws2500Stat->lightSens >=16 )
          decodeLightData(&buf[28], &ws2500Data->lightSens);
       /* Data from Pyranometer                                      */
       if( ws2500Stat->pyranSens >=16 )
          decodePyranData(&buf[30], &ws2500Data->pyranSens);
       ws2500Data->sunDuration.sunDur=-1;

   }else{ /* Bios Version 1.1 or 3.1 */
       /* ---------------------------------------------------------- */
       /* Get data for Wind sensor                                   */
       if( ws2500Stat->windSens >=16 )
          decodeWindData(&buf[20], &ws2500Data->windSens);
       /* Get data from inside sensor                                */
       /* this is: temperature, humidity and pressure                */
       if( ws2500Stat->insideSens >=16 )
          decodeInsideData(&buf[23], &ws2500Data->insideSens);
       /* Get data for rain sensor:                                  */
       if( ws2500Stat->rainSens >=16 )
          decodeRainData(&buf[27], &ws2500Data->rainSens, 1 );
       /* Get sunshine duration */
       if( ws2500Stat->lightSens >=16 )
          decodeSunDuration(&buf[28], &ws2500Data->sunDuration);
       /* Get data for light sensor                                  */
       if( ws2500Stat->lightSens >=16 )
          decodeLightData(&buf[30], &ws2500Data->lightSens);
   }/* End if ws2500-PC */


   ret=postProcessData(ws2500Data, ws2500Stat);

   DEBUG1("end getData\n");
   return(ret);
}



/* **********************************************************************
 * Read Last Value file containing the last values retrieved from the
 * weatherstation. This is needed to perform a tolCheck across calls of
 * ws2500

 ************************************************************************* */
int readLastValFile(char * file, WS2500_DATA *wd, WS2500_STATUS *ws)
{
   FILE *fd;
   int status, i, v1, v2, v3, v4, v5, v6, v7, v8;
   long vl1;
   float vf1;

   DEBUG1("start readLastValFile\n");
   if( (fd=fopen(file, "r")) == NULL){
	sprintf(errBuffer, "* Can't open last value file \"%s\". No big problem. Skipped.\n",
		file);
	printError(errBuffer, 0);
	return(-1);
   }

   status=0;
   /*
    * Format:
    * temp_i       t_omit_i     t_currErr_i,  hum_i  h_omit_i  h_curr_err_i
    * raincount    r_omit       r_currErr
    * wind_speed   ws_omit      ws_currErr
    * light_lux    light_factor lux_omit      lux_currErr
    * pyran_energy pyran_factor energy_omit   energy_currErr
    * inside_t     inside_t_omit inside_t_currErr, inside_h inside_h_omit inside_h_currErr, \
      inside_p     inside_p_omit inside_p_currErr
   */
   DEBUG1("start read TH\n");
   for(i=0; i<MAXTHSENS; i++){
   	/* T/H sensors 0...7 */
	if( fscanf(fd, "THs: %f %d %d, %d %d %d\n", &vf1, &v1, &v2, &v3, &v4, &v5) != 6){
	   status=-2; goto Error;
	}else{
	    wd->thSens[i].temp		= vf1;
	    ws->tolStat.t_omit[i]	= v1;
	    ws->tolStat.t_currErr[i]	= v2;
	    wd->thSens[i].hum		= v3;
	    ws->tolStat.h_omit[i]	= v4;
	    ws->tolStat.h_currErr[i]	= v5;
	}
   }
   /* Rain Sensor */
   DEBUG1("start read Rain\n");
   if( fscanf(fd, "Rs: %d %d %d\n", &v1, &v2, &v3) != 3){
	status=-2; goto Error;
   }else{
	wd->rainSens.count		= v1;
	ws->tolStat.r_omit		= v2;
	ws->tolStat.r_currErr		= v3;
   }
   /* Wind Sensor */
   DEBUG1("start read Wind\n");
   if( fscanf(fd, "Ws: %f %d %d\n", &vf1, &v1, &v2) != 3){
	status=-2; goto Error;
   }else{
	wd->windSens.speed		= vf1;
	ws->tolStat.ws_omit		= v1;
	ws->tolStat.ws_currErr		= v2;
   }
   /* Light Sens */
   DEBUG1("start read Light\n");
   if( fscanf(fd, "Ls: %ld %d %d %d %d\n", &vl1, &v1, &v2, &v3, &v4) != 5){
	status=-2; goto Error;
   }else{
	wd->lightSens.lux 	= vl1;
	wd->lightSens.factor 	= v1;
	ws->tolStat.lux_omit	= v2;
	ws->tolStat.lux_currErr	= v3;
	wd->sunDuration.sunDur=v4;
   }
   /* Pyranometer */
   DEBUG1("start read Pyranometer\n");
   if( fscanf(fd, "Ps: %ld %d %d %d\n", &vl1, &v1, &v2, &v3) != 4){
	status=-2; goto Error;
   }else{
	wd->pyranSens.energy 	= vl1;
	wd->pyranSens.factor 	= v1;
	ws->tolStat.energy_omit	= v2;
	ws->tolStat.energy_currErr= v3;
   }
   /* Inside sensor */
   DEBUG1("start read Inside\n");
   if( fscanf(fd, "Is: %f %d %d, %d %d %d, %d %d %d\n",
    			&vf1, &v1, &v2, &v3, &v4, &v5, &v6, &v7, &v8) != 9){
	status=-2; goto Error;
   }else{
	wd->insideSens.th.temp 		= vf1;
	ws->tolStat.inside_t_omit	= v1;
	ws->tolStat.inside_t_currErr	= v2;
	wd->insideSens.th.hum 		= v3;
	ws->tolStat.inside_h_omit	= v4;
	ws->tolStat.inside_h_currErr	= v5;
	wd->insideSens.pressure 	= v6;
	ws->tolStat.p_omit		= v7;
	ws->tolStat.p_currErr		= v8;
   }

   fclose(fd);
   return(0);

   Error:
   	fclose(fd);
	sprintf(errBuffer, "* Error reading data from file last value \"%s\". File Skipped.\n",
		file);
	printError(errBuffer, 0);

	return(status);
   DEBUG1("end readLastValFile\n");
}


/* **********************************************************************
 * Read Last Value file containing the last values retrieved from the
 * weatherstation. This is needed to perform a tolCheck across calls of
 * ws2500

 ************************************************************************* */
int writeLastValFile(char * file, WS2500_DATA *wd, WS2500_STATUS *ws){
   FILE *fd;
   int status, i;

   DEBUG1("start writeLastValFile\n");
   if( (fd=fopen(file, "w")) == NULL){
	sprintf(errBuffer, "* Can't open last value file \"%s\" for writing. Skipped\n",
		file);
	printError(errBuffer, 0);
	return(-1);
   }

   status=0;
   /*
    * Format:
    * temp_i       t_omit_i     t_currErr_i,  hum_i  h_omit_i  h_curr_err_i
    * raincount    r_omit       r_currErr
    * wind_speed   ws_omit      ws_currErr
    * light_lux    light_factor lux_omit      lux_currErr  sunDuration
    * pyran_energy pyran_factor energy_omit   energy_currErr
    * inside_t     inside_t_omit inside_t_currErr, inside_h inside_h_omit inside_h_currErr, \
      inside_p     inside_p_omit inside_p_currErr
   */
   for(i=0; i<MAXTHSENS; i++){
   	/* T/H sensors 0...7 */
	if( fprintf(fd, "THs: %f %d %d, %d %d %d\n",
				wd->thSens[i].temp,
				ws->tolStat.t_omit[i],
				ws->tolStat.t_currErr[i],
				wd->thSens[i].hum,
				ws->tolStat.h_omit[i],
				ws->tolStat.h_currErr[i] ) <=0 ){
	   status=-2; goto Error;
	}
   }
   /* Rain Sensor */
   if( fprintf(fd, "Rs: %d %d %d\n",
   				wd->rainSens.count,
				ws->tolStat.r_omit,
				ws->tolStat.r_currErr) <= 0 ){
	status=-2; goto Error;
   }
   /* Wind Sensor */
   if( fprintf(fd, "Ws: %f %d %d\n",
   				wd->windSens.speed,
				ws->tolStat.ws_omit,
				ws->tolStat.ws_currErr) <= 0 ){
	status=-2; goto Error;
   }
   /* Light Sens */
   if( fprintf(fd, "Ls: %ld %d %d %d %d\n",
   				wd->lightSens.lux,
				wd->lightSens.factor,
				ws->tolStat.lux_omit,
				ws->tolStat.lux_currErr,
				wd->sunDuration.sunDur) <=0){
	status=-2; goto Error;
   }
   /* Pyranometer */
   if( fprintf(fd, "Ps: %ld %d %d %d\n",
   				wd->pyranSens.energy,
				wd->pyranSens.factor,
				ws->tolStat.energy_omit,
				ws->tolStat.energy_currErr) <=0){
	status=-2; goto Error;
   }
   /* Inside sensor */
   if( fprintf(fd, "Is: %f %d %d, %d %d %d, %d %d %d\n",
    				wd->insideSens.th.temp,
				ws->tolStat.inside_t_omit,
				ws->tolStat.inside_t_currErr,
				wd->insideSens.th.hum,
				ws->tolStat.inside_h_omit,
				ws->tolStat.inside_h_currErr,
				wd->insideSens.pressure,
				ws->tolStat.p_omit,
				ws->tolStat.p_currErr) <= 0){
	status=-2; goto Error;
   }

   fclose(fd);
   return(0);

   Error:
   	fclose(fd);
	sprintf(errBuffer, "* Error writing data to last value file \"%s\".\n",
		file);
	printError(errBuffer, 1);
	return(status);
   DEBUG1("end writeLastValFile\n");
}



/* ***********************************************************************
 * check if data in ws2500Data are valid compared to the older data
 * from   ws2500LastVals and the tolerance values in config.t.*
 * Results of check are the "currErr"-values and possibly
 * the "omit"-values in tolstat.* structure inside teh ws2500-structure.
 * in ws2500Data only the omit
 * variables will be set. In ws2500LastVals the counter currErr
 * will be incremented on error.
 * values that are out of band in ws2500Data will be overwritten by their
 * corresponding older values from ws2500LastVals.
 * Since these data are kept across calls of ws2500, it could happen, that in a
 * first call the is no say wind sensor, so no last value canbe obtained. In the
 * second call of ws2500 a wind sensor has been added. No there might be a problem
 * since the lastval of this sensor may not be used since this sensor did not
 * exist in the last call. We use the variable currErr to note if we have a lastval
 * for a sensor. If it is <0 there is none. If >=0 there is one.
 * The function returns 0 if nothing had to be done else E_APPLIEDTOLCHECK
 *********************************************************************** */
int checkTol(WS2500_DATA *ws2500Data, WS2500_DATA *ws2500LastVals,
	      WS2500_STATUS *ws2500Stat){
   WS2500_DATA ws2500NewLastVals;
   char t[64], *p;
   int i;
   int gotIt, di;
   long l, dl;
   float df;

   DEBUG1("begin checkTolStat\n");
   /* The lastvals for next run will be the current values except for those values */
   /* that are detected to be out of the tolerance band and are set below          */
   ws2500NewLastVals=*ws2500Data;

   gotIt=0;  /* If a tolcheck had to be applied => E_APPLIEDTOLCHECK */
   /* Convert time-value to readable calendar format */
   asctime_r(localtime(&ws2500Data->time), (char *)t);
   p=rindex((char*)t, (int)'\n');
   if( p != NULL )
   	*p='\0';

   for(i=0; i<MAXTHSENS; i++){
     if( ws2500Stat->tempSens[i] >= 16 ){	/* If sensor exists */
        /* --------- Check temperature sensor i */
     	if( config.t.t_tol[i] && ws2500Stat->tolStat.t_currErr[i] >= 0 ){  /* We have an old val ?*/
	    /* Is sensor value out of tolerance band ? */
	    df=ws2500LastVals->thSens[i].temp - ws2500Data->thSens[i].temp;
	    if( fabs(df) > config.t.t_tol[i] ){
	       gotIt=E_APPLIEDTOLCHECK;
	       /* Increase error count and set value to last (ok) value */
	       sprintf(errBuffer, "+ Tol chk, %s: Sensor T(%d) set from %5.1f to %5.1f\n",
	       	    t, i+1,
		    ws2500Data->thSens[i].temp,
		    ws2500LastVals->thSens[i].temp );
	       printError(errBuffer, 0);
	       ws2500Stat->tolStat.t_currErr[i]++;
	       /* Look if there were to many errors already and disable sensor */
	       if( config.t.t_maxErr[i] &&
	           ws2500Stat->tolStat.t_currErr[i] > config.t.t_maxErr[i] ){
	          if( !ws2500Stat->tolStat.t_omit[i]){
		     sprintf(errBuffer, "+ Tol chk: Sensor had more than %d errors. Disableing data output.\n",
		  		config.t.h_maxErr[i]);
	       	     printError(errBuffer, 0);
		  }
	       	  ws2500Stat->tolStat.t_omit[i]=1;
	       }
	       /* Overwrite current value by last value */
	       ws2500Data->thSens[i].temp=ws2500LastVals->thSens[i].temp;
	       ws2500NewLastVals.thSens[i].temp=ws2500Data->thSens[i].temp;

	       /* drive lastvalue in direction of current value by usind delta-tol value */
	       if( df > 0.0 )
	          ws2500NewLastVals.thSens[i].temp-=config.t.t_delta[i];
	       else
	          ws2500NewLastVals.thSens[i].temp+=config.t.t_delta[i];

	    }else{   /* There was a valid entry, so clear error counts and omit flag */
		if(ws2500Stat->tolStat.t_currErr[i] > 0 ){
		   sprintf(errBuffer, "+ Tol chk, %s: Sensor T(%d) OK again\n", t, i+1);
	           printError(errBuffer, 0);
		}
		ws2500Stat->tolStat.t_omit[i]=0;
		ws2500Stat->tolStat.t_currErr[i]=0;
	    }
	}else{
	   ws2500Stat->tolStat.t_currErr[i]=0;  /* Mark tolchk active */
	}

	/* --------- Check humidity sensor i */
     	if( config.t.h_tol[i] && ws2500Stat->tolStat.h_currErr[i] >= 0 ){  /* We have an old val ?*/
	    /* Is sensor value out of Tol band ? */
	    di=ws2500LastVals->thSens[i].hum- ws2500Data->thSens[i].hum;
	    if( abs(di) > config.t.h_tol[i] ){
	       gotIt=E_APPLIEDTOLCHECK;
	       /* Increase error count and set value to last (ok) value */
	       sprintf(errBuffer, "+ Tol chk, %s: Sensor H(%d) set from %d to %d\n",
	       	    t, i+1,
		    ws2500Data->thSens[i].hum,
		    ws2500LastVals->thSens[i].hum );
	       printError(errBuffer, 0);

	       ws2500Stat->tolStat.h_currErr[i]++;
	       /* Look if there were to many errors already and disable sensor */
	       if( config.t.h_maxErr[i] &&
	           ws2500Stat->tolStat.h_currErr[i] > config.t.h_maxErr[i] ){
	          if( !ws2500Stat->tolStat.h_omit[i]){
	             sprintf(errBuffer, "+ Tol chk: Sensor had more than %d errors. Disableing data output.\n",
		  		config.t.h_maxErr[i]);
	              printError(errBuffer, 0);
		  }
	       	  ws2500Stat->tolStat.h_omit[i]=1;
	       }
	       /* Overwrite current value by last value */
	       ws2500Data->thSens[i].hum=ws2500LastVals->thSens[i].hum;
	       ws2500NewLastVals.thSens[i].hum=ws2500Data->thSens[i].hum;

	       /* drive lastvalue in direction of current value by usind delta-tol value */
	       if( di > 0 )
	          ws2500NewLastVals.thSens[i].hum-=config.t.h_delta[i];
	       else
	          ws2500NewLastVals.thSens[i].hum+=config.t.h_delta[i];

	    }else{   /* There was a valid entry, so clear error counts and omit flag */
		if(ws2500Stat->tolStat.h_currErr[i] > 0 ){
		   sprintf(errBuffer, "+ Tol chk, %s: Sensor H(%d) OK again\n", t, i+1);
	       	   printError(errBuffer, 0);
		}
		ws2500Stat->tolStat.h_omit[i]=0;
		ws2500Stat->tolStat.h_currErr[i]=0;
	    }
	}else{
	   ws2500Stat->tolStat.h_currErr[i]=0;  /* Mark tolCheck active */
	}
     }
   }

   /* --------- Check wind sensor */
   if(ws2500Stat->windSens >= 16){
	if( config.t.ws_tol && ws2500Stat->tolStat.ws_currErr >= 0 ){  /* We have an old val ?*/
	/* Is sensor value out of Tol band ? */
	df=ws2500LastVals->windSens.speed - ws2500Data->windSens.speed;
	if( fabs(df) > config.t.ws_tol ){
	        gotIt=E_APPLIEDTOLCHECK;
		/* Increase error count and set value to last (ok) value */
		sprintf(errBuffer, "+ Tol chk, %s: Value speed from Ws set from %5.1f to %5.1f\n",
			t,
			ws2500Data->windSens.speed,
			ws2500LastVals->windSens.speed );
	       printError(errBuffer, 0);
		ws2500Stat->tolStat.ws_currErr++;
		/* Look if there were to many errors already and disable sensor */
		if( config.t.ws_maxErr &&
			ws2500Stat->tolStat.ws_currErr > config.t.ws_maxErr ){
	           if( !ws2500Stat->tolStat.ws_omit){
		   	sprintf(errBuffer, "+ Tol chk: Sensor had more than %d errors. Disableing data output.\n",
				config.t.ws_maxErr);
	           	printError(errBuffer, 0);
		   }
		   ws2500Stat->tolStat.ws_omit=1;
		}
		/* Overwrite current value by last value */
		ws2500Data->windSens.speed=ws2500LastVals->windSens.speed;
		ws2500NewLastVals.windSens.speed=ws2500Data->windSens.speed;

	       /* drive lastvalue in direction of current value by usind delta-tol value */
	       if( df > 0.0  )
	          ws2500NewLastVals.windSens.speed-=config.t.ws_delta;
	       else
	          ws2500NewLastVals.windSens.speed+=config.t.ws_delta;
	}else{   /* There was a valid entry, so clear error counts and omit flag */
		if(ws2500Stat->tolStat.ws_currErr > 0 ){
		   sprintf(errBuffer, "+ Tol chk, %s: Windsensor OK again\n", t);
	           printError(errBuffer, 0);
		}
		ws2500Stat->tolStat.ws_omit=0;
		ws2500Stat->tolStat.ws_currErr=0;
	}
	}else{
	   ws2500Stat->tolStat.ws_currErr=0;  /* Mark tolCheck active */
	}
   }

   /* --------- Check rain sensor */
   /* Rain sensor is different. We do not set the rain sensors value, the counter to the last
    * value, but instead echo a rainamount of zero in this case, not the difference. This is better
    * since the rain sensor can change in a random fashion if there is a thunderstorm. Lightning
    * seems to move the counter by a random amount in any direction
   */
   if(ws2500Stat->rainSens >= 16 && ws2500Data->rainSens.delta >=0 ){
	if( config.t.r_tol && ws2500Stat->tolStat.r_currErr >= 0 ){  /* We have an old val ?*/
	/* Is sensor value out of Tol band ? */
	di=ws2500Data->rainSens.count-ws2500LastVals->rainSens.count;
	/* rainsen tocheck is only applied if new value is much bigger than last value  */
	/* not if it is much smaller (di < 0 )                                          */
	/* since rain counter may overflow eg from 255 to 0 which is no tolerance error */
	if( di > config.t.r_tol || di < 0 ){
	        gotIt=E_APPLIEDTOLCHECK;
		/* Increase error count and set value to last (ok) value */
		sprintf(errBuffer, "+ Tol chk, %s: Value Rainfall of Rs set from %d to 0\n",t, di);
	       printError(errBuffer, 0);
		ws2500Stat->tolStat.r_currErr++;
		ws2500Data->rainSens.delta=0;
		/* Look if there were to many errors already and disable sensor */
		if( config.t.r_maxErr &&
			ws2500Stat->tolStat.r_currErr > config.t.r_maxErr ){
	           if( !ws2500Stat->tolStat.r_omit){
   		   	sprintf(errBuffer, "+ Tol chk: Sensor had more than %d errors. Disableing data output.\n",
				config.t.r_maxErr);
	           	printError(errBuffer, 0);
		   }
		   ws2500Stat->tolStat.r_omit=1;
		}
	}else{   /* There was a valid entry, so clear error counts and omit flag */
		if(ws2500Stat->tolStat.r_currErr > 0 ){
		   sprintf(errBuffer, "+ Tol chk, %s: Rainsensor OK again\n", t);
	           printError(errBuffer, 0);
		}
		ws2500Stat->tolStat.r_omit=0;
		ws2500Stat->tolStat.r_currErr=0;
	}
	}else{
	   ws2500Stat->tolStat.r_currErr=0;  /* Mark tolCheck active */
	}
   }

   /* --------- Check pressure sensor */
   if(ws2500Stat->insideSens >= 16){
	if( config.t.p_tol && ws2500Stat->tolStat.p_currErr >= 0 ){  /* We have an old val ?*/
	/* Is sensor value out of Tol band ? */
	di=ws2500LastVals->insideSens.pressure - ws2500Data->insideSens.pressure;
	if( abs(di) > config.t.p_tol ){
	        gotIt=E_APPLIEDTOLCHECK;
		/* Increase error count and set value to last (ok) value */
		sprintf(errBuffer, "+ Tol chk, %s: Value pres. from Is set from %d to %d\n",
			t,
			ws2500Data->insideSens.pressure,
			ws2500LastVals->insideSens.pressure );
	       printError(errBuffer, 0);
		ws2500Stat->tolStat.p_currErr++;
		/* Look if there were to many errors already and disable sensor */
		if( config.t.p_maxErr &&
			ws2500Stat->tolStat.p_currErr > config.t.p_maxErr ){
	           if( !ws2500Stat->tolStat.p_omit){
		   	sprintf(errBuffer, "+ Tol chk: Sensor had more than %d errors. Disableing data output.\n",
				config.t.p_maxErr);
	           	printError(errBuffer, 0);
		   }
		   ws2500Stat->tolStat.p_omit=1;
		}
		/* Overwrite current value by last value */
		ws2500Data->insideSens.pressure=ws2500LastVals->insideSens.pressure;
		ws2500NewLastVals.insideSens.pressure=ws2500Data->insideSens.pressure;

	       /* drive lastvalue in direction of current value by usind delta-tol value */
	       if( di > 0 )
	          ws2500NewLastVals.insideSens.pressure-=config.t.p_delta;
	       else
	          ws2500NewLastVals.insideSens.pressure+=config.t.p_delta;
	}else{   /* There was a valid entry, so clear error counts and omit flag */
		if(ws2500Stat->tolStat.p_currErr > 0 ){
		   sprintf(errBuffer, "+ Tol chk, %s: Insidesensor (P) OK again\n", t);
	           printError(errBuffer, 0);
		}
		ws2500Stat->tolStat.p_omit=0;
		ws2500Stat->tolStat.p_currErr=0;
	}
	}else{
	   ws2500Stat->tolStat.p_currErr=0;  /* Mark tolCheck active */
	}
   }


   /* --------- Check inside Temp-sensor */
   if(ws2500Stat->insideSens >= 16){
	if( config.t.inside_t_tol && ws2500Stat->tolStat.inside_t_currErr >= 0 ){  /* We have an old val ?*/
	/* Is sensor value out of Tol band ? */
	df=ws2500LastVals->insideSens.th.temp - ws2500Data->insideSens.th.temp;
	if( fabs(df) > config.t.inside_t_tol ){
	        gotIt=E_APPLIEDTOLCHECK;
		/* Increase error count and set value to last (ok) value */
		sprintf(errBuffer, "+ Tol chk, %s: Value T from Is set from %5.1f to %5.1f\n",
			t,
			ws2500Data->insideSens.th.temp,
			ws2500LastVals->insideSens.th.temp );
	       printError(errBuffer, 0);
		ws2500Stat->tolStat.inside_t_currErr++;
		/* Look if there were to many errors already and disable sensor */
		if( config.t.inside_t_maxErr &&
			ws2500Stat->tolStat.inside_t_currErr > config.t.inside_t_maxErr ){
	           if( !ws2500Stat->tolStat.inside_t_omit){
		   	sprintf(errBuffer, "+ Tol chk: Sensor had more than %d errors. Disableing data output.\n",
				config.t.inside_t_maxErr);
	           	printError(errBuffer, 0);
	 	   }
		   ws2500Stat->tolStat.inside_t_omit=1;
		}
		/* Overwrite current value by last value */
		ws2500Data->insideSens.th.temp=ws2500LastVals->insideSens.th.temp;
		ws2500NewLastVals.insideSens.th.temp=ws2500Data->insideSens.th.temp;

	       /* drive lastvalue in direction of current value by usind delta-tol value */
	       if( df > 0.0 )
	          ws2500NewLastVals.insideSens.th.temp-=config.t.inside_t_delta;
	       else
	          ws2500NewLastVals.insideSens.th.temp+=config.t.inside_t_delta;
	}else{   /* There was a valid entry, so clear error counts and omit flag */
		if(ws2500Stat->tolStat.inside_t_currErr > 0 ){
		   sprintf(errBuffer, "+ Tol chk, %s: Insidesens (T) sensor OK again\n", t);
	           printError(errBuffer, 0);
		}
		ws2500Stat->tolStat.inside_t_omit=0;
		ws2500Stat->tolStat.inside_t_currErr=0;
	}
	}else{
	   ws2500Stat->tolStat.inside_t_currErr=0;  /* Mark tolCheck active */
	}

	/* --------- Check inside Hum-sensor */
	if( config.t.inside_h_tol && ws2500Stat->tolStat.inside_h_currErr >= 0 ){  /* We have an old val ?*/
	/* Is sensor value out of Tol band ? */
	di=ws2500LastVals->insideSens.th.hum - ws2500Data->insideSens.th.hum;
	if( abs(di) > config.t.inside_h_tol ){
	        gotIt=E_APPLIEDTOLCHECK;
		/* Increase error count and set value to last (ok) value */
		sprintf(errBuffer, "+ Tol chk, %s: Value H from Is set from %d to %d\n",
			t,
			ws2500Data->insideSens.th.hum,
			ws2500LastVals->insideSens.th.hum );
	       printError(errBuffer, 0);
		ws2500Stat->tolStat.inside_h_currErr++;
		/* Look if there were to many errors already and disable sensor */
		if( config.t.inside_h_maxErr &&
			ws2500Stat->tolStat.inside_h_currErr > config.t.inside_h_maxErr ){
	           if( !ws2500Stat->tolStat.inside_h_omit){
		   	sprintf(errBuffer, "+ Tol chk: Sensor had more than %d errors. Disableing data output.\n",
				config.t.inside_h_maxErr);
	           	printError(errBuffer, 0);
		   }
		   ws2500Stat->tolStat.inside_h_omit=1;
		}
		/* Overwrite current value by last value */
		ws2500Data->insideSens.th.hum=ws2500LastVals->insideSens.th.hum;
		ws2500NewLastVals.insideSens.th.hum=ws2500Data->insideSens.th.hum;

	       /* drive lastvalue in direction of current value by usind delta-tol value */
	       if( di > 0 )
	          ws2500NewLastVals.insideSens.th.hum-=config.t.inside_h_delta;
	       else
	          ws2500NewLastVals.insideSens.th.hum+=config.t.inside_h_delta;
	}else{   /* There was a valid entry, so clear error counts and omit flag */
		if(ws2500Stat->tolStat.inside_h_currErr > 0 ){
		   sprintf(errBuffer, "+ Tol chk, %s: Insidesens (H) OK again\n", t);
	           printError(errBuffer, 0);
		}
			ws2500Stat->tolStat.inside_h_omit=0;
			ws2500Stat->tolStat.inside_h_currErr=0;
	}
	}else{
	   ws2500Stat->tolStat.inside_h_currErr=0;  /* Mark tolCheck active */
	}
   }


   /* --------- Check light sensor */
   if(ws2500Stat->lightSens >= 16){
	if( config.t.lux_tol && ws2500Stat->tolStat.lux_currErr >= 0 ){  /* We have an old val ?*/
	/* Is sensor value out of Tol band ? */
	dl=ws2500LastVals->lightSens.lux * ws2500LastVals->lightSens.factor -
			ws2500Data->lightSens.lux * ws2500Data->lightSens.factor;
	if( labs(dl) > config.t.lux_tol ){
	        gotIt=E_APPLIEDTOLCHECK;
		/* Increase error count and set value to last (ok) value */
		sprintf(errBuffer, "+ Tol chk, %s: Value lux from Ls set from %ld to %ld\n",
			t,
			ws2500Data->lightSens.lux*(long)ws2500Data->lightSens.factor,
			ws2500LastVals->lightSens.lux*(long)ws2500LastVals->lightSens.factor);
	       printError(errBuffer, 0);
		ws2500Stat->tolStat.lux_currErr++;
		/* Look if there were to many errors already and disable sensor */
		if( config.t.lux_maxErr &&
			ws2500Stat->tolStat.lux_currErr > config.t.lux_maxErr ){
	           if( !ws2500Stat->tolStat.lux_omit){
		   	sprintf(errBuffer, "+ Tol chk: Sensor had more than %d errors. Disableing data output.\n",
				config.t.lux_maxErr);
	       		printError(errBuffer, 0);
		   }
		   ws2500Stat->tolStat.lux_omit=1;
		}
		/* Overwrite current value by last value */
		ws2500Data->lightSens.lux=ws2500LastVals->lightSens.lux;
		ws2500Data->lightSens.factor=ws2500LastVals->lightSens.factor;
		ws2500NewLastVals.lightSens.lux=ws2500Data->lightSens.lux;
		ws2500NewLastVals.lightSens.factor=ws2500Data->lightSens.factor;

	       /* drive lastvalue in direction of current value by usind delta-tol value */
	       l=ws2500LastVals->lightSens.lux*(long)ws2500LastVals->lightSens.factor;
	       if( dl > 0L ){
		  l-=config.t.lux_delta;
		  ws2500NewLastVals.lightSens.lux=(long) (l/ws2500LastVals->lightSens.factor);
	       }else{
		  l+=config.t.lux_delta;
		  ws2500NewLastVals.lightSens.lux=(long) (l/ws2500LastVals->lightSens.factor);
	       }
	}else{   /* There was a valid entry, so clear error counts and omit flag */
		if(ws2500Stat->tolStat.lux_currErr > 0 ){
		   sprintf(errBuffer, "+ Tol chk, %s: Lightsensor OK again\n", t);
		   printError(errBuffer, 0);
		}
		ws2500Stat->tolStat.lux_omit=0;
		ws2500Stat->tolStat.lux_currErr=0;
	}
	}else{
	   ws2500Stat->tolStat.lux_currErr=0;  /* Mark tolCheck active */
	}
   }


   /* --------- Check pyranometer sensor */
   if(ws2500Stat->pyranSens >= 16){
	if( config.t.energy_tol && ws2500Stat->tolStat.energy_currErr >= 0 ){  /* We have an old val ?*/
	/* Is sensor value out of Tol band ? */
	dl=ws2500LastVals->pyranSens.energy * ws2500LastVals->pyranSens.factor -
			ws2500Data->pyranSens.energy * ws2500Data->pyranSens.factor;
	if( labs(dl) > config.t.energy_tol ){
	        gotIt=E_APPLIEDTOLCHECK;
		/* Increase error count and set value to last (ok) value */
		sprintf(errBuffer, "+ Tol chk, %s: Value energy from Ps set from %ld to %ld\n",
			t,
			ws2500Data->pyranSens.energy*(long)ws2500Data->pyranSens.factor,
			ws2500LastVals->pyranSens.energy*(long)ws2500LastVals->pyranSens.factor);
	       printError(errBuffer, 0);
		ws2500Stat->tolStat.energy_currErr++;
		/* Look if there were to many errors already and disable sensor */
		if( config.t.energy_maxErr &&
			ws2500Stat->tolStat.energy_currErr > config.t.energy_maxErr ){
	           if( !ws2500Stat->tolStat.energy_omit){
		   	sprintf(errBuffer, "+ Tol chk: Sensor had more than %d errors. Disableing data output.\n",
				config.t.energy_maxErr);
	           	printError(errBuffer, 0);
		   }
		   ws2500Stat->tolStat.energy_omit=1;
		}
		/* Overwrite current value by last value */
		ws2500Data->pyranSens.energy=ws2500LastVals->pyranSens.energy;
		ws2500Data->pyranSens.factor=ws2500LastVals->pyranSens.factor;
		ws2500NewLastVals.pyranSens.energy=ws2500Data->pyranSens.energy;
		ws2500NewLastVals.pyranSens.factor=ws2500Data->pyranSens.factor;

	       /* drive lastvalue in direction of current value by usind delta-tol value */
	       l=ws2500LastVals->pyranSens.energy*(long)ws2500LastVals->pyranSens.factor;
	       if( dl > 0 ){
		  l-=config.t.energy_delta;
		  ws2500NewLastVals.pyranSens.energy=(long) (l/ws2500LastVals->pyranSens.factor);
	       }else{
		  l+=config.t.energy_delta;
		  ws2500NewLastVals.pyranSens.energy=(long) (l/ws2500LastVals->pyranSens.factor);
	       }
	}else{   /* There was a valid entry, so clear error counts and omit flag */
		if(ws2500Stat->tolStat.energy_currErr > 0 ){
		   sprintf(errBuffer, "+ Tol chk, %s: Pyranometersensor OK again\n", t);
	           printError(errBuffer, 0);
		}
		ws2500Stat->tolStat.energy_omit=0;
		ws2500Stat->tolStat.energy_currErr=0;
	}
	}else{
	   ws2500Stat->tolStat.energy_currErr=0;  /* Mark tolCheck active */
	}
   }


   /* Finally copy (the now corrected) current values to lastValues for next run */
   *ws2500LastVals=ws2500NewLastVals;


   DEBUG1("end checkTolStat\n");
   return(gotIt);
}


/* *********************************************************************** */
/* Format the New flag which is actually a status flag.                    */
/* It can return the chars '0', '1' or 'h', see ws2500.h                   */
/* The input value can be the decimal 0,1 or a character  like 'h'         */         
/* *********************************************************************** */
char formatNewFlag(int value){
   if( value <= 9 ){
   	return( (char)(value+48) ); /* return a char in the range of int 0...9 */
   }else{
   	return( (char)value );      /* print a char like 'h'            */
   }
}


/* *********************************************************************** */
/* print all data of available sensors if stat is != 0                     */
/* *********************************************************************** */
void printData(WS2500_DATA *ws2500Data, WS2500_STATUS *ws2500Stat)
{
   int i;
   static int firstCall=1;
   char *ptime;
   char buf[25];
   int min, hour;
   

   /* Convert time-value to readable calendar format */
   /* Data will be printed with dates in GMtime also called UTC */
   /* to avoid trouble with daylight saving time                */
   ptime=timeToDate(&ws2500Data->time, GMTIME);

   if( ! config.printTerse ){ /* short or long output ?*/
       printf("Data Blocknumber: %u\n", ws2500Data->blockNr );
       printf("Date: %s\n", (char*)ptime);
       printf("Station: %d\n", config.stationId); 


       for(i=0; i<MAXTHSENS; i++){
   	    if( ws2500Stat->tempSens[i] >= 16 &&
	         !(ws2500Stat->tolStat.t_omit[i] || ws2500Stat->tolStat.h_omit[i]) ){
		printf("Temp/Hum %2d (%d drop outs): T: %4.1f C, H: %-2d %%, New: %c \n", i+1,
			    ws2500Stat->tempSens[i]-16,
			    ws2500Data->thSens[i].temp,
			    ws2500Data->thSens[i].hum,
			    formatNewFlag(ws2500Data->thSens[i].new)
			              );
	    }
       }
       /* Inside sensor */
       if( ws2500Stat->insideSens >= 16 &&
           !(ws2500Stat->tolStat.inside_t_omit || ws2500Stat->tolStat.inside_h_omit) ){
	  printf("Inside (%d drop outs):      ", ws2500Stat->insideSens-16);
	  printf("T: %4.1f C, H: %-2d %%, ",
      		    ws2500Data->insideSens.th.temp, ws2500Data->insideSens.th.hum);

	  if( config.altitude ){
             printf("Pressure(r): %4d hPa, ", ws2500Data->insideSens.pressure);
	  }else{
             printf("Pressure(a): %4d hPa, ", ws2500Data->insideSens.pressure);
	  }
	  printf("New: %c\n", formatNewFlag(ws2500Data->insideSens.newTh) );
       }


       /* Rain sensor output */
       if( ws2500Stat->rainSens >= 16 && ! ws2500Stat->tolStat.r_omit){
	  printf("Rain (%d drop outs):    ", ws2500Stat->rainSens-16);
	  printf("Count: %4d, ", ws2500Data->rainSens.count);
	  if( ws2500Data->rainSens.delta >=0 ){
	     	printf("Rainfall: %5.2f mm", ((long)ws2500Data->rainSens.delta*
					 (long)config.mmrainbycount)/1000.0);
	  }else{
		printf("Rainfall: - ");
	  }

   	  printf("; New: %c\n",  formatNewFlag(ws2500Data->rainSens.new) );
       }

       /* Wind sensor output */
       if( ws2500Stat->windSens >= 16 && ! ws2500Stat->tolStat.ws_omit ){
	  printf("Wind (%d drop outs):    ", ws2500Stat->windSens-16);
	  printf("Speed: %3.1f Km/h, ", ws2500Data->windSens.speed);
	  printf("Dir: %3d�, ", ws2500Data->windSens.direction);
	  printf("GustSpeed: 0.0, "); 	/* Not valid for ws2500 hence value set to 0 */
	  printf("GustDir: 0, ");	/* Not valid for ws2500 hence value set to 0 */
	  printf("Var: %5.1f�, ", ws2500Data->windSens.variance);
	  printf("New: %c\n", formatNewFlag(ws2500Data->windSens.new) );
       }


       /* Light sensor data */
       if( ws2500Stat->lightSens >= 16 && ! ws2500Stat->tolStat.lux_omit){
	  printf("Light sensor (%d drop outs):", ws2500Stat->lightSens-16);
	  printf("Light: %ld lux, ", ws2500Data->lightSens.lux);
	  printf("Factor: %d, ", ws2500Data->lightSens.factor);
	  printf("IsSun: %d, ", ws2500Data->lightSens.sunshine);
	  if( ws2500Data->sunDuration.sunDur > 0 ){
	    hour= ws2500Data->sunDuration.sunDur/60;
	    min= ws2500Data->sunDuration.sunDur%60;
	    sprintf(buf, "%2d.%02d (delta: %2d min)", hour, min, ws2500Data->sunDuration.deltaSunShine );
	    printf("Sunshine: %s h, ", buf);
	  }
	  printf("New: %c\n", formatNewFlag(ws2500Data->lightSens.new) );
       }

       /* Pyranometer sensor data */
       if( ws2500Stat->pyranSens >= 16 && ! ws2500Stat->tolStat.energy_omit ){
	  printf("Pyranometer (%d drop outs):", ws2500Stat->pyranSens-16 );
	  printf("Power: %3ld W/m, ", ws2500Data->pyranSens.energy);
	  printf("Factor: %3d\n", ws2500Data->pyranSens.factor);
       }

   }else{ /* *****************  Terse output ********************* */
       if( firstCall ){
          printf("# Sensorname[-number] (drop outs): values of sensor\n");
          printf("## Blocknumber: Block(1)\n");
          printf("## Date: Cal(date), time(sec)\n");
          printf("## Station: Id(1)\n");
          printf("## THS(Temp/humidity): Temperatur(°C), Humidity(%%), New(1)\n");
	  if( config.altitude )
             //printf("## PS(Pressure):  Temperatur(°C), Humidity(%%), Pressure-relativ(hPa), New\n");
             printf("## PS(Pressure): Pressure-relativ(hPa), New\n");
	  else
             //printf("## PS(Pressure):  Temperatur(°C), Humidity(%%), Pressure-absolute(hPa), New\n");
             printf("## PS(Pressure): Pressure-absolute(hPa), New\n");


          printf("## RS(Rain): Counter(1), OneCount(mm/1000), Rain(mm/1000), ET(mm/1000), Tol(1), New(1) \n");
          printf("## WS(Wind): Speed(Km/h), Direction(°), GustSpeed(Km/h), GustDirection(°), Variance(°), New(1)\n");
          printf("## LS(Light): Light(lux), Factor(1), Flag(1), Duration(h), DeltaDuration(min), Radiation(W/m^2), UVindex(1), New(1)\n");
          printf("## PYS(Pyranometer): Energy(W/m), Factor(1)\n");
	  printf("#\n");
       }
       printf("Blocknumber: %u\n", ws2500Data->blockNr );
       printf("Date: %s, %ld\n", (char*)ptime, (long)ws2500Data->time);
       printf("Station: %d\n", config.stationId); 
       for(i=0; i<MAXTHSENS; i++){
   	    if( ws2500Stat->tempSens[i] >= 16 &&
	         !(ws2500Stat->tolStat.t_omit[i] || ws2500Stat->tolStat.h_omit[i]) ){
		printf("THS-%d (%d): %3.1f, %d, %c \n", i+1,
			    ws2500Stat->tempSens[i]-16,
			    ws2500Data->thSens[i].temp,
			    ws2500Data->thSens[i].hum,
			    formatNewFlag(ws2500Data->thSens[i].new)
			              );
	    }
       }
       /* Inside sensor */
       if( ws2500Stat->insideSens >= 16 &&
           !(ws2500Stat->tolStat.inside_t_omit || ws2500Stat->tolStat.inside_h_omit) ){
	  printf("THS-17 (%d): ", ws2500Stat->insideSens-16);
	  printf("%3.1f, %d, %c \n",
      		    ws2500Data->insideSens.th.temp,
		    ws2500Data->insideSens.th.hum,
		    ws2500Data->insideSens.newTh      );

	  printf("PS     (%d): ", ws2500Stat->insideSens-16);
          printf("%d, ", ws2500Data->insideSens.pressure);
	  printf("%c \n", formatNewFlag(ws2500Data->insideSens.newP) );
       }


       /* Rain sensor output */
       if( ws2500Stat->rainSens >= 16 && ! ws2500Stat->tolStat.r_omit){
	  printf("RS    (%d): ", ws2500Stat->rainSens-16);
	  printf("%d, ", ws2500Data->rainSens.count);
	  printf("%d, ", config.mmrainbycount);
	  if( ws2500Data->rainSens.delta >=0 ){
	     	printf("%ld, ", (long)ws2500Data->rainSens.delta*(long)config.mmrainbycount);
	  }else{
		printf("-1, ");
	  }
	  printf("0, ");	/* Value for Davis VP2 evapotranspiration, 0 for ws2500 */
	  printf("%d, ", config.t.r_tol);


      	  printf("%c \n",  formatNewFlag(ws2500Data->rainSens.new) );
       }

       /* Wind sensor output */
       if( ws2500Stat->windSens >= 16 && ! ws2500Stat->tolStat.ws_omit ){
	  printf("WS    (%d): ", ws2500Stat->windSens-16);
	  printf("%3.1f, ", ws2500Data->windSens.speed);
	  printf("%d, ", ws2500Data->windSens.direction);
	  printf("0.0, 0, "); /* Values for GustSpeed and GustDirection always zero for ws2500 */
	  printf("%3.1f, ", ws2500Data->windSens.variance);
	  printf("%c \n", formatNewFlag(ws2500Data->windSens.new) );
       }


       /* Light sensor data */
       if( ws2500Stat->lightSens >= 16 && ! ws2500Stat->tolStat.lux_omit){
	  printf("LS    (%d): ", ws2500Stat->lightSens-16);
	  printf("%ld, ", ws2500Data->lightSens.lux);
	  printf("%d, ", ws2500Data->lightSens.factor);
	  printf("%d, ", ws2500Data->lightSens.sunshine);
	  if( ws2500Data->sunDuration.sunDur > 0 ){
	    hour= ws2500Data->sunDuration.sunDur/60;
	    min= ws2500Data->sunDuration.sunDur%60;
	    sprintf(buf, "%2d.%02d", hour, min);
	    printf("%s, ", buf);
	    printf("%2d, ", ws2500Data->sunDuration.deltaSunShine );
	    		
	  }else{
      	    printf("0, 0, ");
	  }
	  printf("0, 0, %c\n", formatNewFlag(ws2500Data->lightSens.new) );
       }

       /* Pyranometer sensor data */
       if( ws2500Stat->pyranSens >= 16 && ! ws2500Stat->tolStat.energy_omit ){
	  printf("PYS    (%d): ", ws2500Stat->pyranSens-16 );
	  printf("%ld, ", ws2500Data->pyranSens.energy);
	  printf("%d\n", ws2500Data->pyranSens.factor);
       }

   }
   firstCall=0;
}


/* ************************************************************* */
/* Send a command to station and wait for input and check input  */
/* On error this function will 					 */
/* be <0:  A value describing an eroror				 */
/*    >0: Number of bytes in buffer 				 */
/* ************************************************************* */
int execCommand(int fd, COMMAND c, u_char *par)
{
   int stat=0, tryCount;

   tryCount=RETRYCOUNT;	/* How many times we try to resend a failed command to station */
   while( tryCount-- ){
   	stat=sendCommand(fd, c, par);	/* Send Command "c" to station  */
   	stat=readData(fd, 1);		/* Read results 	       */

	if( stat > 0 ){
		if( tryCount < RETRYCOUNT-1 ){
			printError("+ Resending of command was successful.\n", 0);
		}
		stat=cleanData(stat);	/* Remove ctrl chars and check */
		if( stat <= 0 ) {
			printError("*** Error decoding data\n", 1);
			stopCom(fd, config.port);
			return(E_DECODEDATA);
		}
		stat=trimData(stat);
		if( stat <= 0 ) {
			printError("*** Error trimming data\n", 1);
			stopCom(fd, config.port);
			return(E_TRIMDATA);
		}
		if( stat == 1 && buffer[0] == NAK ){
			printError("*** Error during command transfer to station \n", 1);
			stopCom(fd, config.port);
			return(E_CMDXFER);
		}
		break;		/* Everything is OK; leave while loop */
	}else{
		/* Try to restart communication to station and resend last command that failed */
		if( tryCount > 0 ){
			printError("+ Trying to resend last command to station ...\n", 1);
			stopCom(fd, config.port);		/* Restart Communications */
			config.fd=startCom(config.port);
			if( config.fd <= 0 ){
					return(config.fd);	/* No success */
					printError("+ Resending of command failed. \n", 0);
			}else{
				fd=config.fd;}
		}else{
			printError("*** Error: Did not receive any more data \n", 1);
			stopCom(fd, config.port);
			return(E_NODATA);
		}
	}
   }/* while */

   return(stat);
}


/* *************************************** */
/* Execute a command to the weatherstation */
/* *************************************** */
int runCommand(USER_COMMAND c, char opt, int *optArgs )
{
   u_char cmdBuf[5];
   char *pLastValFile;
   int stay, i, tmp, ret, returnStatus, lastValStat, tolStatus;
   short lastRainCount=-1;
   short lastSunDuration=-1;
   DCF_INFO dcfInfo;
   WS2500_STATUS ws2500Stat, tmpStat;
   WS2500_DATA ws2500Data;
   WS2500_DATA ws2500LastData;


   DEBUG1("begin runCommand\n");

   bzero(&ws2500Data, sizeof(WS2500_DATA));
   bzero(&ws2500LastData, sizeof(WS2500_DATA));

   /* Initialize relevant flags in ws2500LastData and ws2500Data */
   for(i=0; i<MAXTHSENS; i++){
	ws2500Stat.tolStat.h_currErr[i]=-1;
   	ws2500Stat.tolStat.t_currErr[i]=-1;
   	ws2500Stat.tolStat.t_omit[i]=0;
   	ws2500Stat.tolStat.h_omit[i]=0;
   }


   ws2500Stat.tolStat.r_currErr=-1;
   ws2500Stat.tolStat.r_omit=0;
   ws2500Stat.tolStat.ws_currErr=-1;
   ws2500Stat.tolStat.ws_omit=0;
   ws2500Stat.tolStat.lux_currErr=-1;
   ws2500Stat.tolStat.lux_omit=0;
   ws2500Stat.tolStat.energy_currErr=-1;
   ws2500Stat.tolStat.energy_omit=0;
   ws2500Stat.tolStat.p_currErr=-1;
   ws2500Stat.tolStat.p_omit=0;
   ws2500Stat.tolStat.inside_t_currErr=-1;
   ws2500Stat.tolStat.inside_t_omit=0;
   ws2500Stat.tolStat.inside_h_currErr=-1;
   ws2500Stat.tolStat.inside_h_omit=0;


   ret=99;
   returnStatus=0;
   tolStatus=0;

   lastValStat=-1; /* Flag to find out if any lastvalues are there        */
                   /* either read from file or as a result of new ws-data */

   pLastValFile=NULL;
   if( config.t.checkTol &&  (c==DOGETALLDATA || c== DOGETNEWDATA)){
      if( !strcmp(config.t.lastValFile, "config") ){	/* User said: -C "config" */
	pLastValFile=config.t.confLastValFile;
	lastValStat=readLastValFile(pLastValFile, &ws2500LastData,
						  &ws2500Stat      );
	if( lastValStat >=0 )
		lastRainCount=ws2500LastData.rainSens.count;
		lastSunDuration=ws2500LastData.sunDuration.sunDur;
      }else if( strcmp(config.t.lastValFile, "inline") ){	/* User did not say -C "inline" */
	/* User should have given the name of the file on commandline using -C */
	pLastValFile=config.t.lastValFile;
	lastValStat=readLastValFile(pLastValFile, &ws2500LastData,
						  &ws2500Stat        );
	if( lastValStat >=0 )
		lastRainCount=ws2500LastData.rainSens.count;
		lastSunDuration=ws2500LastData.sunDuration.sunDur;
      }
   }

   /* Setup communication with station */
   if((config.fd=startCom(config.port)) <0 )
   	return(E_ERROR);


   switch(c){
     case DOPOLLDCF:
       ret=execCommand(config.fd, POLLDCF, NULL);  /* get current time */
       returnStatus=ret;
       if( ret < 0 ) break;
       readDcf(&dcfInfo, config.useSystemTime);		     /* Evaluate dcf data */
       printDcf(dcfInfo);

       if( dcfInfo.dcfStatus )
       	   returnStatus=0;
       else		
       	   returnStatus=E_DCFNOTINSYNC;
     break;

     case DOFIRSTDATASET:
     case DOCURDATASET:
     case DOGETALLDATA:
     case DOGETNEWDATA:
       if( c != DOGETNEWDATA && c != DOCURDATASET ){
       	  ret=execCommand(config.fd, FIRSTDATASET, NULL);/* Send command c to station        */
	  returnStatus=ret;
          if( ret < 0 ) break;

       	  if( buffer[0] != ACK ){
	     printError("*** Error:Could not address first dataset\n", 1);
	     return(-1);
	  }
       }
       ret=execCommand(config.fd, POLLDCF, NULL);  /* get current time */
       returnStatus=ret;
       if( ret < 0 ) break;
       readDcf(&dcfInfo, config.useSystemTime);
       ret=execCommand(config.fd, STATUS, NULL);   /* Fetch status  */
       returnStatus=ret;
       if( ret < 0 ) break;
       readStatus(&ws2500Stat, ret);
       if( config.t.checkTol ){ 
         /* Update tolcheck Status to reflect availability of sensors */ 
         ws2500Status2tolStatus(&ws2500Stat);
         /* Upon successful communications init delete lastval file */
   	  unlink(pLastValFile);
	}	

       stay=0;
       do{
	    ret=execCommand(config.fd, GETDATASET, NULL); /* Now fetch data */
	    /* execCommand only return <0 (error) or > 0 (number of bytes in buffer) */
            if( ret < 0 ){  /* There was an error */
	        /* if returnStatus indicates no error up to now (>=0) or if the error   */
		/* value contained therein is less important that the current error     */
		/* (returnStatus < ret) then we store the new more important error.     */
		/* An error is more importatnt than another if its value is closer to 0 */
	    	if( (returnStatus >= 0) || (returnStatus < ret) ){
			returnStatus=ret;
		}
	    	break;
	    }
	    if (!(ret == 1 && buffer[0] == DLE)) {
	       ret=getData(&ws2500Data, &dcfInfo, &ws2500Stat);
	       if( ret > 0 || ret == E_TOOMANYDROPOUTS ){
		  if( ret == E_TOOMANYDROPOUTS ){
			/* See comment above */
			if( (returnStatus >= 0) || (returnStatus < ret) ){
				returnStatus=ret;
			}
		  }
		  if( c == DOGETALLDATA || c==DOGETNEWDATA ){
	             if( lastRainCount >=0 )
	       	  	   ws2500Data.rainSens.delta = ws2500Data.rainSens.count-lastRainCount;
		     else
		  	      ws2500Data.rainSens.delta=-1; /* We have no lastRainCount */

		     if( lastSunDuration >= 0 ){
		  	  		ws2500Data.sunDuration.deltaSunShine=ws2500Data.sunDuration.sunDur-lastSunDuration;
					/* Check if sunduration counter of station had overflow */
					if(  ws2500Data.sunDuration.deltaSunShine >24*60 ||
					     ws2500Data.sunDuration.deltaSunShine < 0          ){
					   ws2500Data.sunDuration.deltaSunShine=0;
					}
		     }else{
					ws2500Data.sunDuration.deltaSunShine=-1;
		     }
		  }else{
		    ws2500Data.rainSens.delta=-1;
		    ws2500Data.sunDuration.deltaSunShine=-1; 	   
		   }  

		  /* Check if read values are in in the tolerance band */
		  if( (c==DOGETALLDATA || c== DOGETNEWDATA) && config.t.checkTol ){
	             /* Results of check are the "currErr"-values and possibly
			* the "omit"-values in tolStat.* inside of WS2500_DATA.
			* in ws2500Data only the omit
			* variables will be set. In ws2500LastValsthe counter currErr
			* will be incremented on error.
		       */
		      /* Calculate a delta value of the counter for rain sensor */
		      if( tolStatus == 0 )
			   if( lastValStat >=0 ) /* We already have a first lastValues */
				   tolStatus=checkTol(&ws2500Data, &ws2500LastData, &ws2500Stat);
			   else
				   ws2500LastData=ws2500Data; /* Create the first lastVals */
		      else
			   /* Keep Error info in tolstat */
			   if( lastValStat >=0 ) /* We already have a first lastValues */
				   tolStatus=checkTol(&ws2500Data, &ws2500LastData, &ws2500Stat);
			   else
				   ws2500LastData=ws2500Data; /* Create the first lastVals */
	              lastValStat=1;
		  }

		  lastRainCount=ws2500Data.rainSens.count;
		  lastSunDuration=ws2500Data.sunDuration.sunDur;
	    	  printData(&ws2500Data, &ws2500Stat);
	       }else{
		   if( (returnStatus >= 0) || (returnStatus < ret) ){
			   returnStatus=ret;
		   }
		   stay=0;
	       }
	       
	    }
	    ret=0;

	    if( (returnStatus >= 0 || returnStatus==E_TOOMANYDROPOUTS) &&
	       (c==DOGETALLDATA || c== DOGETNEWDATA) ){
	       ret=execCommand(config.fd, NEXTSET, NULL);

	       if(buffer[0]==ACK){
		    stay=1;
		    printf("----------------------------------------------------------------------\n");
	       }else{
		    if( buffer[0] != DLE ){
		        printError("*** Error in switching to next dataset.\n", 1);
			/* See comment above */
			if( (returnStatus >= 0) || (returnStatus < E_GETNEXTDATASET ) ){
				returnStatus=E_GETNEXTDATASET;
			}
		    }
		    stay=0;
	       }
	    }
	}while(stay);

	/* If everything is allright or if a timeout occurred save lastdata */
	if( returnStatus >= 0 || returnStatus==E_NODATA ||
		returnStatus==E_TOOMANYDROPOUTS || returnStatus==E_GETNEXTDATASET ){
	   /* If a lastVal file could be read at the beginning or there were     */
	   /* data processed (providing lastVals) we write the lastVal file back */
	   if( pLastValFile != NULL && lastValStat >=0 ){
		lastValStat=writeLastValFile(pLastValFile, &ws2500LastData,
							   &ws2500Stat      );
	   }
	   /* check if the checkTol function changed a sensor value. If yes and */
	   /* there were no other errors (ret>0) then exit with status          */
	   /* E_APPLIEDTOLCHECK, to indicate this situation                     */

	   /* See also comments above */
	   if( (returnStatus >= 0) || (tolStatus<0 && (returnStatus < tolStatus)) ){
		returnStatus=tolStatus;
	   }
	}
     break;

     case DOSTATUS:
	returnStatus=execCommand(config.fd, STATUS, NULL); /* Send STATUS to station        */
        if( returnStatus < 0 ) break;
	DEBUG2("** %d\n", returnStatus);
	readStatus(&ws2500Stat, returnStatus);
	printStatus(&ws2500Stat);
	returnStatus=0;
     break;

     case DOINTERFACE:	/* Set one of several interface parameters */
     	/* First read stations status which contains current settings */
	returnStatus=execCommand(config.fd, STATUS, NULL); /* Send command c to station        */
        if( returnStatus < 0 ) break;

	readStatus(&ws2500Stat, returnStatus);
	tmpStat=ws2500Stat;

	tmp=0;
	/* Find a value in optagrs that has not been set by user   */
	/* this means the user did omit one of -WRNPLV Options     */
	/* Since on Firmware 1.0 stations the corresponding data   */
	/* (the sensor addresses)				   */
	 /* cannot be extracted from the station the user has to   */
	/* specify all options. One newe firmwae this is not needed*/
	/* the only sensor address in 1.0 that can be extracted is */
	/* the inside sensor */
	for(i=0; i<NUMOPTS; i++){
	   if( optArgs[i] == -1 && i != OPTPAR_N ) tmp=1;
	}
	if( ws2500Stat.version <= 10 && tmp ){
	   printError(
	   "Your stations firmware does not have a way to extract the current sensor\n", 1);
	   printError(
	   "addresses. On the other hand changing these values or the interval value \n", 0);
	   printError(
	   "requires to set ALL values! This means if you want to change one such a value\n",0);
	   printError(
	   "you have to specify all of  the -I -W -R -N -P -V options with corresponding\n", 0);
	   printError(
	   "values not just one or two of them. Sorry. Newer firmware (>1.0) does\n", 0);
	   sprintf(errBuffer,
	   "suffer from this problem. Your stations firmware is: %d .\n", ws2500Stat.version);
	   printError(errBuffer, 0);

	   returnStatus=-1;
	   break;
	}else if( ws2500Stat.version == 31 || ws2500Stat.version == 11 ){
	   if(optArgs[OPTPAR_P] != -1 ){  /* Pyranometer sensor address cannot be set */
	  	sprintf(errBuffer,
		  "+ Warning: Pyranometer sensor address cannot be set with station firmware %d. Ignored.\n",
		  ws2500Stat.version);
	   	printError(errBuffer, 0);
	   }
	}

	/* Insert values given by user into existing structure */
	/* The values are in optArgs[], where, OPTPAR_I R, ... represent the index values  */
	/* for this particular options. So the value of -I is in optArgs[OPTPAR_I] or this */
	/* variable is -1; */
	stay=1;
	ret=0;
	for(i=0; stay && i<NUMOPTS; i++){
	   if( optArgs[i] <0 ) continue;
	   switch(i){
	      case OPTPAR_I: 	/* recording interval */
		if( optArgs[i] < 2 || optArgs[i] > 63 ) {
		   printError("*** Error: interval has limit from 2..63 minutes. \n", 1);
		   ret=-1;
		   stay=FALSE;
		   break;
		}
		tmpStat.interval=optArgs[i];
		printf("Interval of %d min leads to max recording time of %4.1f days\n",
			tmpStat.interval, (tmpStat.interval *1024.0)/60/24 );
	      break;

	      case OPTPAR_R: /* Address of rain sensor */
		if( optArgs[i] < 0 || optArgs[i] > 7 ) {
		   printError("*** Error: sensor address has limit from 0..7. \n", 1);
		   ret=-1;
		   stay=FALSE;
		   break;
		}
		tmpStat.addrSensRain=optArgs[i];
	      break;

	      case OPTPAR_W: /* Address of wind sensor */
		if( optArgs[i] < 0 || optArgs[i] > 7 ) {
		   printError("*** Error: sensor address has limit from 0..7. \n", 1);
		   ret=-1;
		   stay=FALSE;
		   break;
		}
		tmpStat.addrSensWind=optArgs[i];
	      break;

	      case OPTPAR_L: /* Address of light sensor */
		if( optArgs[i] < 0 || optArgs[i] > 7 ) {
		   printError( "*** Error: sensor address has limit from 0..7. \n", 1);
		   ret=-1;
		   stay=FALSE;
		   break;
		}
		tmpStat.addrSensLight=optArgs[i];
	      break;

	      case OPTPAR_P: /* Address of pyranometer sensor */
		if( optArgs[i] < 0 || optArgs[i] > 7 ) {
		   printError("*** Error: sensor address has limit from 0..7. \n", 1);
		   ret=-1;
		   stay=FALSE;
		   break;
		}
		tmpStat.addrSensPyran=optArgs[i];
	      break;

	      case OPTPAR_N: /* Address of inside sensor */
		if( optArgs[i] < 0 || optArgs[i] > 7 ) {
		   printError("*** Error: sensor address has limit from 0..7. \n", 1);
		   ret=-1;
		   stay=FALSE;
		   break;
		}
		tmpStat.addrSensInside=optArgs[i];
	      break;
	      
	      case OPTPAR_V: /* Protocol Version */
		if( optArgs[i] < 0 || optArgs[i] > 1 ) {
		   printError("*** Error: Protocol version must be either 0 or 1. \n", 1);
		   ret=-1;
		   stay=FALSE;
		   break;
		}
		tmpStat.protocol=optArgs[i];
	      break;

	   }
	 DEBUG3("optArgs: %d; i:%d\n", optArgs[i], i);
	}

	if( ret < 0 ){
	  returnStatus=ret;
	  break; /* Something above went wrong. Terminate */
	}

	/* Now glue together the new values to be transferred to the station */
	/* this are a total 4 bytes containing Interval, addresses of the    */
	/* wind, rain, light, pyranometer & inside sensors as well as the    */
	/* protocol version all the data from above */
	bzero(cmdBuf, 5);
	if( ws2500Stat.version ==10 ){
	   cmdBuf[0]=(tmpStat.interval&255) | (1<<7);
	   cmdBuf[1]=((tmpStat.addrSensRain & 0x7)        |
		     ((tmpStat.addrSensWind & 0x7)<<4)   |
		     ((u_char)1<<7))&255;
	   cmdBuf[2]=(tmpStat.addrSensPyran & 0x7)       |
		     ((tmpStat.addrSensLight & 0x7)<<4)  |
		     ((u_char)1<<7);
	   cmdBuf[3]=(tmpStat.protocol & 0x1)            |
		     ((tmpStat.addrSensInside & 0x7)<<4) |
		     ((u_char)1<<7);

	}else if( ws2500Stat.version == 31 || ws2500Stat.version == 11 ){
	   cmdBuf[0]=1 | (1<<7);  		     /* First interval */
	   cmdBuf[1]=(tmpStat.interval&255) | (1<<7);  /* next interval */
	   cmdBuf[2]=((tmpStat.addrSensRain & 0x7)        |
		     ((tmpStat.addrSensWind & 0x7)<<4)   |
		     ((tmpStat.protocol&1) <<3)       |
		     ((u_char)1<<7))&255;
	   cmdBuf[3]=(tmpStat.addrSensLight & 0x7)       |
		     ((tmpStat.addrSensInside & 0x7)<<4)  |
		     ((u_char)1<<7);
	}
	FOR(i=0; i< 4; i++){
		DEBUG2("%x\n", cmdBuf[i]&255);
	}
	returnStatus=execCommand(config.fd, INTERFACE, cmdBuf);
        if( returnStatus < 0 ) break;

	if( returnStatus == 1 && buffer[0]==ACK ){
		printf("OK\n");
		returnStatus=0;
	}else{
		printError("*** Error: Setting interface parameters\n", 1);
		returnStatus=E_SETINTERFACE;
	}
     break;

     case NOCOMMAND:
     break;
   }

   stopCom(config.fd, config.port);

   return(returnStatus);
   DEBUG1("end2 runCommand\n");
}


/* ************************** */
/* print out some usage hints */
/* ************************** */
void usage(void){
   fprintf(stderr, "ws2500 {-[d|s|f|g|x|v|u|n] -C <parm> | {-[IRLNPVW <val>]}} [-c cfg,-a <alt>,-D,-t,-p device]\n");
   fprintf(stderr, "\t -a <alt>: Set altitude(m). Used for calculation of relative pressure.\n");
   fprintf(stderr, "\t -d: Get DCF Date and Time\n");
   fprintf(stderr, "\t -u <n>: Get DCF Date and Time, but print only time in format n.\n");
   fprintf(stderr, "\t -s: Get status information\n");
   fprintf(stderr, "\t -f: Get first available data set (for testing)\n");
   fprintf(stderr, "\t     Be aware: This will make all data appear to be new to next -n call.\n");
   fprintf(stderr, "\t -g: Get current data set to which the internal ws2500 stations buffer pointer\n");
   fprintf(stderr, "\t     currently points. For testing, may be empty, does not affect -n.\n");
   fprintf(stderr, "\t -n: Get new available data sets since last -n call.\n");
   fprintf(stderr, "\t -x: Get all available data sets (better redirect output to file)\n");
   fprintf(stderr, "\t     Be aware: This will make all data appear to be new to next -n call.\n");
   fprintf(stderr, "\t -c <cfgFile>: Use <cfgFile> for reading configuration data.\n");
   fprintf(stderr, "\t -t: Output is terse. Thought for automatic postprocessing of data.\n");
   fprintf(stderr, "\t -I <interval>: Set interval for data collection on WS2500.\n");
   fprintf(stderr, "\t -{[NLRWP] <value>}: Set one or more sensor addresses to corresponding \n");
   fprintf(stderr, "\t    <val> for sensor: iNside, Light, Rain, Wind, Pyranometer.\n");
   fprintf(stderr, "\t -V <value>: Set protocol version to 1.2 (0) or 1.1 (1).\n");
   fprintf(stderr, "\t -D: Run in debug mode. Shows used config file and lots of debug information.\n");
   fprintf(stderr, "\t -v: Show version information.\n");
   fprintf(stderr, "\t -p <device>: serial port to connect to (/dev/ttyS?).\n");
   fprintf(stderr, "\t -C inline|config|<file>: Enable tolerance check for sensor values.\n");
   fprintf(stderr, "\t -i: Ignore a possible time offset from time in dataset to system time.\n");
   fprintf(stderr, "\t -S: Use linux system time instead of stations DCF time even if available.\n");

   exit(1);
}



/* ************************************************ */
/* process on line of input from configuration file */
/* the config format is: variable=value             */
/* ************************************************ */
void processLine(char *line, int lineNo, char *file){
   int i, wc=0, v1, v2, v3;
   float vf, vf1;
   long vld, vld1;
   char words[2][PATHLEN];
   char *cp, *cp1, *ep;

   cp=index(line, (int)'#');
   if( cp != NULL )
   	*cp='\0';  /* Truncate everything right from a # (comment) */

   line+=strspn(line, " \t"); /* skip leading whitespace */
   if( ! strlen(line) )
   	return;

   cp=index(line, (int)'='); /* Try to find = in line */
   if( cp == NULL ){
   	sprintf(errBuffer, "+ Warning: invalid line in config file %s, line %d\n",
			file, lineNo);
	printError(errBuffer, 0);
   }else{
	cp1=cp;		/* Keep pointer on '=' in mind */
	cp--;		/* Now search backwards and skip any blnak or tab char */
	while( (*cp == ' ' || *cp == '\t') && cp >line ) cp--;
	*(cp+1)='\0';	/* Set EOS for variable name */
	strcpy(words[wc++], line);  /* copy "variable" name left from = */

  	cp1++;  /* skip "=" sign */
	line=cp1;
	line+=strspn(line, " \t");
	strcpy(words[wc++], line);  	     /* Copy rest of line to "value" */
	for(i=0; i< (int)strlen(words[0]); i++)   /* Make variable name lower case */
   	   words[0][i]=tolower(words[0][i]);



	if( !strlen(words[0]) || !strlen(words[1]) ){
	   sprintf(errBuffer, "+ Warning: Variable or value in %s line %d is empty.\n",
	   		file, lineNo);
	   printError(errBuffer, 0);
	}


	/* Now evaluate options found in config file */
	/* ++++                                  +++ */
	/* altitude */
	if( !strcmp(words[0], "altitude") ){
		i=(int)strtol(words[1], &ep, 10);
		if( errno== EINVAL || ep==words[1] ||  i < 0 ){
			sprintf(errBuffer, "+ Warning: Invalid altitude value in %s, line %d. Skipped.\n",
					file, lineNo);
			printError(errBuffer, 0);
		}else
		  config.altitude=i;
	/* serialPort */
	}else if( !strcmp(words[0], "serialport") ){
		strcpy(config.port, words[1]);

	/* printTerse */
	}else if( !strcmp(words[0], "printterse") ){
		i=(int)strtol(words[1], &ep, 10);
		if( errno== EINVAL || ep==words[1] || ( i != 0 && i != 1) ){
			sprintf(errBuffer, "+ Warning: Numeric value 0 or 1 required in %s, line %d. Skipped.\n",
					file, lineNo);
			printError(errBuffer, 0);
		}else
		   config.printTerse=i;

	/* stationId */
	}else if( !strcmp(words[0], "stationid") ){
		i=(int)strtol(words[1], &ep, 10);
		if( errno== EINVAL || ep==words[1] || i <= 0 ){
			sprintf(errBuffer, "+ Warning: Numeric value >= 1 required in %s, line %d. Skipped.\n",
					file, lineNo);
			printError(errBuffer, 0);
		}else
		   config.stationId=i;

	}else if( !strcmp(words[0], "mmrainbycount") ){
		vf=(float)atof(words[1]);
		if( errno== EINVAL || vf < 0.0 ){
			sprintf(errBuffer, "+ Warning: Numeric value >0 required in %s, line %d. Skipped.\n",
					file, lineNo);
			printError(errBuffer, 0);
		}else
		   config.mmrainbycount=(int)(vf*1000+0.5);

	}else if( !strcmp(words[0], "lastvaluefile") ){
		   strcpy(config.t.confLastValFile, words[1]);

	}else if( !strncmp(words[0], "toltemperature_", 15 ) ){
		i=strlen(words[0]);
		i=atoi(words[0]+(i-1));		/* Extract number of th sensor */
		if( i <=0 || i >MAXTHSENS ){
		    sprintf(errBuffer, "+ Warning: Illegal tol-index entry (>MAXTHSENS) in %s, line %d. Skipped.\n",
				file, lineNo);
		    printError(errBuffer, 0);
		}else{
		   i--; /* Internal we have thsens 0..7, not 1..8 */
		   if( sscanf( words[1], "%f %d %f", &vf, &v1, &vf1) != 3){
		    	sprintf(errBuffer, "+ Warning: Float dec float value required in %s, line %d. Skipped.\n",
				file, lineNo);
			printError(errBuffer, 0);
		   }else if(vf > 0.0 && v1 >= 0 && vf > (vf1*2.0) && vf1 >=0.0) {
			config.t.t_maxErr[i]=v1;
			config.t.t_tol[i]=vf;
			config.t.t_delta[i]=vf1;
		   }else{
			sprintf(errBuffer, "* Error: tol must be > 0 & MaxErr >=0 and tol > delta*2 & delta >= 0 in %s, line %d. Ignored.\n",
				file, lineNo);
			printError(errBuffer, 1);
		   }
		}
	}else if( !strncmp(words[0], "tolhumidity_", 12 ) ){
		i=strlen(words[0]);
		i=atoi(words[0]+(i-1));		/* Extract number of th sensor */
		if( i <=0 || i >MAXTHSENS ){
		    sprintf(errBuffer, "+ Warning: Illegal tol-index entry (>MAXTHSENS) in %s, line %d. Skipped.\n",
				file, lineNo);
		    printError(errBuffer, 0);
		}else{
		   i--;
		   if( sscanf( words[1], "%d %d %d", &v1, &v2, &v3 ) != 3){
		    	sprintf(errBuffer, "+ Warning: Float dec dec value required in %s, line %d. Skipped.\n",
				file, lineNo);
			printError(errBuffer, 0);
		   }else  if(v1 > 0 && v2 >= 0 && v1 > (v3*2) && v3 >=0){
		   	config.t.h_maxErr[i]=v2;
			config.t.h_tol[i]=v1;
			config.t.h_delta[i]=v3;
		   }else{
			sprintf(errBuffer, "* Error: Tol must be > 0 & MaxErr >=0 & tol > delta*2 & delta >= 0 in %s, line %d. Ignored.\n",
				file, lineNo);
			printError(errBuffer, 1);
		   }
		}
	}else if( !strcmp(words[0], "tolinsidetemperature")  ){
	   if( sscanf( words[1], "%f %d %f", &vf, &v1, &vf1 ) != 3){
		    sprintf(errBuffer, "+ Warning: Float dec float value required in %s, line %d. Skipped.\n",
				file, lineNo);
		    printError(errBuffer, 0);
	    }else  if(vf > 0.0 && v1 >= 0  && vf > (vf1*2.0) && vf1 >= 0.0){
	    	config.t.inside_t_maxErr=v1;
		config.t.inside_t_tol=vf;
		config.t.inside_t_delta=vf1;
	    }else{
			sprintf(errBuffer, "* Error: Tol must be > 0 & MaxErr >=0 & tol > delta*2  & delta >= 0 in %s, line %d. Ignored.\n",
				file, lineNo);
			printError(errBuffer, 1);
		   }
	}else if( !strcmp(words[0], "tolinsidehumidity")  ){
	   if( sscanf( words[1], "%d %d %d", &v1, &v2, &v3 ) != 3){
		    sprintf(errBuffer, "+ Warning: dec dec dec value required in %s, line %d. Skipped.\n",
				file, lineNo);
		    printError(errBuffer, 0);
	    }else if(v1 > 0 && v2 >= 0 && v1 > (v3*2) && v3 >= 0){
		config.t.inside_h_tol=v1;
		config.t.inside_h_maxErr=v2;
		config.t.inside_h_delta=v3;
	    }else{
			sprintf(errBuffer, "* Error: Tol must be > 0 & MaxErr >=0 & tol > delta*2 & delta >= 0 in %s, line %d. Ignored.\n",
				file, lineNo);
			printError(errBuffer, 1);
		   }
	}else if( !strcmp(words[0], "tolpressure")  ){
	   if( sscanf( words[1], "%d %d %d", &v1, &v2, &v3 ) != 3){
		    sprintf(errBuffer, "+ Warning: dec dec  dec value required in %s, line %d. Skipped.\n",
				file, lineNo);
		    printError(errBuffer, 0);
	    }else if(v1 > 0 && v2 >= 0 && v1 > (v3*2) && v3 >= 0){
	    	config.t.p_tol=v1;
		config.t.p_maxErr=v2;
		config.t.p_delta=v3;
	    }else{
			sprintf(errBuffer, "* Error: Tol must be > 0 & MaxErr >=0 & tol > delta*2 & delta >= 0 in %s, line %d. Ignored.\n",
				file, lineNo);
			printError(errBuffer, 1);
		   }
	}else if( !strcmp(words[0], "tolwindspeed") ){
	   if( sscanf( words[1], "%f %d %f", &vf, &v1, &vf1 ) != 3){
		    sprintf(errBuffer, "+ Warning: Float dec float value required in %s, line %d. Skipped.\n",
				file, lineNo);
		    printError(errBuffer, 0);
	    }else  if(vf > 0.0 && v1 >= 0 && vf > (vf1*2.0) && vf1 >= 0.0){
	        config.t.ws_tol=vf;
		config.t.ws_maxErr=v1;
		config.t.ws_delta=vf1;
	    }else{
			sprintf(errBuffer, "* Error: Tol must be > 0 & MaxErr >=0 & tol > delta*2 & delta >= 0 in %s, line %d. Ignored.\n",
				file, lineNo);
			printError(errBuffer, 1);
		   }
	}else if( !strcmp(words[0], "tolrain") ){
	   if( sscanf( words[1], "%d %d %d", &v1, &v2, &v3 ) != 3){
		    sprintf(errBuffer, "+ Warning: dec dec dec value required in %s, line %d. Skipped.\n",
				file, lineNo);
	            printError(errBuffer, 0);
	    }else if(v1 > 0 && v2 >= 0 && v1 > (v3*2) && v3 >= 0){
		config.t.r_tol=v1;
		config.t.r_maxErr=v2;
		config.t.r_delta=v3;
	    }else{
			sprintf(errBuffer, "* Error: Tol must be > 0 & MaxErr >=0 & tol > delta*2 & delta >= 0 in %s, line %d. Ignored.\n",
				file, lineNo);
			printError(errBuffer, 1);
		   }
	}else if( !strcmp(words[0], "tollux") ){
	   if( sscanf( words[1], "%ld %d %ld", &vld, &v1, &vld1 ) != 3){
		    sprintf(errBuffer, "+ Warning: dec dec dec value required in %s, line %d. Skipped.\n",
				file, lineNo);
		    printError(errBuffer, 0);
	    }else  if(vld > 0L && v1 >= 0 && vld > (vld1*2L) && vld1 >= 0L){
	    	config.t.lux_maxErr=v1;
		config.t.lux_tol=vld;
		config.t.lux_delta=vld1;
	    }else{
			fprintf(stderr, "* Error: Tol must be > 0 & MaxErr >=0 & tol > delta*2 & delta >= 0 in %s, line %d. Ignored.\n",
				file, lineNo);
		   }
	}else if( !strcmp(words[0], "tolenergy") ){
	   if( sscanf( words[1], "%ld %d %ld", &vld, &v1, &vld1 ) != 3){
		    sprintf(errBuffer, "+ Warning: dec dec dec value required in %s, line %d. Skipped.\n",
				file, lineNo);
		    printError(errBuffer, 0);
	    }else if(vld > 0L && v1 >= 0 && vld > (vld1*2L) && vld1 >= 0L){
	    	config.t.energy_maxErr=v1;
		config.t.energy_tol=vld;
		config.t.energy_delta=vld1;
	    }else{
			sprintf(errBuffer, "* Error: Tol must be > 0 & MaxErr >=0 & tol > delta*2 & delta >= 0 in %s, line %d. Ignored.\n",
				file, lineNo);
			printError(errBuffer, 1);
		   }
	}else if( !strcmp(words[0], "maxdropoutcount") ){
	   if( sscanf( words[1], "%d", &v1 ) != 1){
		    sprintf(errBuffer, "+ Warning: dec value required in %s, line %d. Skipped.\n",
				file, lineNo);
		    printError(errBuffer, 0);
	    }else if(v1 >= 0 ){
	    	config.maxDropOuts=v1;
	    }else{
			sprintf(errBuffer, "* Error: MaxDropOutCount be >= 0 in %s, line %d. Ignored.\n",
				file, lineNo);
			printError(errBuffer, 1);
		   }
	}else{
		sprintf(errBuffer, "+ Warning: Unknown option %s in config file %s, line %d \n",
				words[0], file, lineNo);
		printError(errBuffer, 0);
	}
  }
}


/* **************************************** */
/* Read configuration data from config file */
/* config info is stored in glocal "config" */
/* **************************************** */
int readConfigFile(char *pathName){
   char stdPath[PATHLEN];
   char line[PATHLEN];
   uid_t uid;
   struct passwd *pw;
   FILE *conf;
   int lNum;


   if( pathName == NULL ){
   	strcpy(stdPath, config.cfgFile);
   }else{
   	strcpy(stdPath, pathName);
   }

   /* We look for the standard config file in "." and in $HOME */
   /* or only in the file specified by the user in pathName          */
   if ((conf = fopen(stdPath, "r")) == NULL) {
      if( pathName != NULL ){
      	sprintf(errBuffer, "Error: Cannot find config file %s.\n", pathName);
	printError(errBuffer, 1);
	return(-1);
      }else{
        DEBUG2("No config file: %s \n", stdPath);
      }
      /* Try in currentdirectory or */
      uid=getuid();   				 /* in user specified file     */
      pw=getpwuid(uid);  /* Find password entry for user */
      if( pw == NULL ){
      	printError("+ Warning: Cannot find password entry for user.\n", 0);
	return(0);
      }else {
      	strcpy(stdPath, pw->pw_dir); /* Users home directory */
	strcat(stdPath, "/");
	strcat(stdPath, config.cfgFile);
	if ((conf = fopen(stdPath, "r")) == NULL) { /* Try in home dir */
	   	DEBUG2("No config file: %s \n", stdPath);

   		/* Now we additionally look in /etc */
		strcpy(config.cfgFile, "ws2500.conf");
		strcpy(stdPath, "/etc/ws2500/");
		strcat(stdPath, config.cfgFile);
		if ((conf = fopen(stdPath, "r")) == NULL) { 
		      DEBUG2("No config file: %s \n", stdPath);
		      return(0);
		}      
	}
      }
   }

   DEBUG2("Reading config file %s \n", stdPath);

   /* Now read contents of file */
   lNum=1;
   while(fgets(line, PATHLEN, conf)){
        if (strlen(line) > 0)
                line[strlen(line) - 1] = '\0';
        processLine(line, lNum++, stdPath);
   }
   fclose(conf);
   return(0);
}


/* --------------------------------------------------------------------------------------
   main()
  -------------------------------------------------------------------------------------- */
int main(int argc, char **argv){
   const char *flags = "a:c:dfghinxp:vsu:tC:DI:R:L:N:P:V:W:S";
   char cmdOpt;
   int opt, i, stat, ret;
   int optPars[NUMOPTS];
   USER_COMMAND c=NOCOMMAND;


   /* Default serial port  device */
   strcpy(config.port, MODEMDEVICE);
   strcpy(config.cfgFile, ".ws2500.conf");
   
   config.speed=BAUDRATE;
   config.altitude=0;
   config.printTerse=0;
   config.printTimeOnly=0;
   config.maxDropOuts=0;
   config.mmrainbycount=DEFAULT_MMRAINBYCOUNT;
   config.ignoreTimeErr=FALSE;
   config.stationId=1;   /* Default number of weather station */
   config.useSystemTime=FALSE; /* By default use DCF if available */

   /* Initialize default values for tolerance values */
   for(i=0;i<MAXTHSENS;i++){
   	config.t.t_tol[i]=0.0;  config.t.h_tol[i]=0;
	config.t.t_maxErr[i]=0; config.t.h_maxErr[i]=0;
	config.t.t_delta[i]=0.0;
	config.t.h_delta[i]=0;
   }
   config.t.p_tol=0; 	config.t.p_maxErr=0;    config.t.p_delta=0;
   config.t.r_tol=0; 	config.t.r_maxErr=0;    config.t.r_delta=0;
   config.t.ws_tol=0;	config.t.ws_maxErr=0;   config.t.ws_delta=0.0;
   config.t.lux_tol=0;	config.t.lux_maxErr=0;  config.t.lux_delta=0;
   config.t.energy_tol=0;config.t.energy_maxErr=0; config.t.energy_delta=0;
   config.t.inside_t_tol=0;config.t.inside_t_maxErr=0; config.t.inside_t_delta=0.0;
   config.t.inside_h_tol=0;config.t.inside_t_maxErr=0; config.t.inside_h_delta=0;
   config.t.checkTol=0;  /* Tolerance check is disabled */
   config.t.lastValFile[0]='\0';
   config.t.confLastValFile[0]='\0';

   ret=98;

   if( argc < 2 ) usage();

   /* Set locale to default C to force output in "C"-format especially
    * time and date values
   */
   setlocale(LC_ALL, "C");

   /* Set default output buffer and buffer type to avoid timeouts of the */
   /* weather station due to the time printf takes to do its job.        */
   setvbuf(stdout, outBuffer, _IOFBF, OUTPUTBUFFERSIZE);

   cmdOpt='\0';
   for(i=0;i<NUMOPTS; i++) optPars[i]=-1; /* Optinal parameters for runCommand() */

   /* Evaluate Options */
   stat=0;
   /* look if user specified a particular configfile to be read by -c */
   /* if yes, we should not try to read the default files right now   */
   /* but only the user specified file 				      */
   /* To debug in readConfigFile we need to set debugging here as well */
   for(i=0; i<argc; i++){
   	if( !strcmp("-c", argv[i]) ) stat=1;
	/* Checkif we want to run in debug mode */
	if( !strcmp("-D", argv[i]) ){
		doDebug=1;
	   	setvbuf(stdout, NULL, _IONBF, 0); /*  unbuffered */
	}	
   }
   if( !stat )
   	readConfigFile(NULL);

   while( (opt = getopt(argc, argv, flags)) >0){
      switch(opt){
	 case 'h':			/* help */
      	   usage();
	 break;

	 case 'a':
      	   config.altitude=atoi(optarg);	/* retrieve DCF time */
	 break;

	 case 'c':
	   if( readConfigFile(optarg) <0 )
	   	exit(1);
	 break;

	 case 'd':
      	   c=DOPOLLDCF;			/* retrieve DCF time */
	 break;

	 case 'f':			/* Get firstdata set sored in device */
           c=DOFIRSTDATASET;
	 break;

	 case 'g':			/* Get current data  set sored in device */
           c=DOCURDATASET;
	 break;

	 case 'i':			/* Serial Port */
	   config.ignoreTimeErr=TRUE;
	 break;

	 case 'n':			/* Get data not yet extracted from device */
           c=DOGETNEWDATA;
	 break;

	 case 'p':			/* Serial Port */
	   strcpy(config.port, optarg);
	 break;

	 case 's':			/* Print status of station */
           c=DOSTATUS;
	 break;

	 case 't':			/* Print status of station in terse form */
           config.printTerse=1;
	 break;

	 case 'u':			/* Serial Port */
	   c=DOPOLLDCF;
	   config.printTimeOnly=atoi(optarg);
	 break;

	 case 'x':			/* Serial Port */
	   c=DOGETALLDATA;
	 break;

	 case 'C':
	    i=strlen(optarg);
	    if( i > PATHLEN ) i=PATHLEN;
	    strncpy(config.t.lastValFile, optarg, i);
	    config.t.checkTol=TRUE;
	 break;

	 case 'S':
	    config.useSystemTime=TRUE;
	 break;

	 case 'D':			/* Debug on , already handled above*/
	 break;

	 case 'I':  /* Set parameters in weather station: */
	    c=DOINTERFACE;
	    optPars[OPTPAR_I]=atoi(optarg);
	    cmdOpt=opt;
	 break;
	 case 'W':  /* Intervall, Rain-, wind-, Light-, Pyran-SensAdr */
	    c=DOINTERFACE;
	    optPars[OPTPAR_W]=atoi(optarg);
	    cmdOpt=opt;
	 break;
	 case 'R':  /* Inside-SensAdres,protocol version */
	    c=DOINTERFACE;
	    optPars[OPTPAR_R]=atoi(optarg);
	    cmdOpt=opt;
	 break;
	 case 'N':  /* -> Set sonsor Addres of inside sensor */
	    c=DOINTERFACE;
	    optPars[OPTPAR_N]=atoi(optarg);
	    cmdOpt=opt;
	 break; 
	 case 'L':
	    c=DOINTERFACE;
	    optPars[OPTPAR_L]=atoi(optarg);
	    cmdOpt=opt;
	 break;
	 case 'P':
	    c=DOINTERFACE;
	    optPars[OPTPAR_P]=atoi(optarg);
	    cmdOpt=opt;
	 break; 
	 case 'V':
	    c=DOINTERFACE;
	    optPars[OPTPAR_V]=atoi(optarg);
	    cmdOpt=opt;
	 break;

	 case 'v':			/* print version */
      	   printf("ws2500 data extraction utility, by Rainer Krienke\n");
	   printf("%s\n", Version);
	   exit( 0 );
	 break;

	 default:
      	   usage();
	 break;
      }
   }

   /* If the user specified any main command (like -d, ...) execute it now */
   if( c != NOCOMMAND ){
       ret=runCommand(c, cmdOpt, optPars);
       exit(abs(ret));
   }else
   	usage();

  return(0);
}
