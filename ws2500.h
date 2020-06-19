/*

   ws2500 -- Weather Data Extraction utility (ws2500 model)

   Copyright (C) 2003, Rainer Krienke (krienke@uni-koblenz.de)
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

   $Id: ws2500.h,v 0.39 2006/05/26 08:55:47 krienke Exp $
*/
#include <locale.h>
#include <signal.h>
#include <termios.h>
#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <time.h>
#include <pwd.h>
#include <ctype.h>
#include <libgen.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/signal.h>
#include <sys/types.h>

#define BAUDRATE B19200
#define MODEMDEVICE "/dev/ttyS1"
#define MAXTHSENS 8
#define _POSIX_SOURCE 1 /* POSIX compliant source */
#define FALSE 0
#define TRUE 1
#define BUFLEN 255
#define RETRYCOUNT 3 	/* number of retries for sending a command. see */
			/* execCommand() 				*/

#define NUMOPTS  7  /* Numberof Options below; see main() */
#define OPTPAR_I 0  /* Index values in optPars for options*/
#define OPTPAR_W 1
#define OPTPAR_R 2
#define OPTPAR_N 3
#define OPTPAR_P 4
#define OPTPAR_V 5
#define OPTPAR_L 6


#define LOCK_PREFIX "/var/lock/LCK.."
#define PIDLEN      12
#define PATHLEN     1024
#define OUTPUTBUFFERSIZE 256


#define SOH 0x01
#define STX 0x02
#define ETX 0x03
#define EOT 0x04
#define ENQ 0x05
#define ACK 0x06
#define DLE 0x10
#define DC2 0x12
#define DC3 0x13
#define NAK 0x15


/*
 * Definitions for the "New" flag that is retrieved from the station for
 * each sensor. The station either reports 0 (drop out) or 1 for ok.
 * These values are actually decimal values. However in the output of
 * ws2500 we print the characters '0' or '1'.
 * Besides these values we define additionally the value 'h' for the
 * case where the humidity sensor reported a either invalid or too low
 * (<20%) value. So the New-flag has actually become a dataset status flag.
 */
#define DSETSTAT_OK            '1'  /* Dataset retrieved is ok   */
#define DSETSTAT_DROPOUT       '0'  /* Sensor had drop outs      */
#define DSETSTAT_HUMIDITY_LOW  'h'  /* Humidity is below minimal range */
#define LOWEST_HUMIDITY 20          /* Lowest hum value that can be measured */
#define INVALID_HUMIDITY 0 /* If a humidity is invalid 0 */



/* Several different exit stati for particular error conditions */
/* The errors form a hierachy. Errors with smaller numbers are */
/* considered more important than smaller numbers              */
#define E_ERROR      -1
#define E_CMDXFER    -2
#define E_DECODEDATA -3
#define E_NODATA     -4
#define E_TRIMDATA   -5
#define E_SETINTERFACE -6
#define E_GETNEXTDATASET -7
#define E_APPLIEDTOLCHECK -8
#define E_TOOMANYDROPOUTS -9
#define E_TIMEDIFFTOBIG -25     /* Difference between system time and ws2500 time to big */
#define E_DCFNOTINSYNC -50	/* DCF time from station is not valid */

#define DEFAULT_MMRAINBYCOUNT 340; /* Default mm/1000 of rain to be counted for each raincounter strike */

#define LOCALTIME 0    /* possible values of 2nd parameter of timeToDate()   */
#define GMTIME    1    /* determines timzone in which date will be formatted */

/* Define Maximal timeoffset (sec) allowed from "now" to time in ws2500 data set. See checkDataTimestamp() */
#define MAX_DATATIMEOFFSET (60*24*60*60)

typedef int BOOL;

/* Structure for tolerance vlaues for sensors. The current value of each sensor       */
/* Is comared to its last value. If the new value is +/tol more than the last it is   */
/* considered to be an error. If more than maxErr error occur the sensor is           */
/* disabled, i.e. no more data are printed out					      */
typedef struct {
	u_char checkTol;
	float t_tol[MAXTHSENS];		/* Tol values for th-sensors			*/
	float t_delta[MAXTHSENS];
	short h_tol[MAXTHSENS];
	short h_delta[MAXTHSENS];
	short p_tol;		/* Tol value for Pressure in hPa		*/
	short p_delta;
	short r_tol;		/* Tol-value for Rain sensor in counts		*/
	short r_delta;
	float ws_tol;		/* Tol-Value for wind speed 			*/
	float ws_delta;
	long lux_tol;		/* Tol value for light intensity in lux 	*/
	long lux_delta;
	long energy_tol;	/* Tol value for pyranometer energy */
	long energy_delta;
	float inside_t_tol;	/* Inside sensor t/h data */
	float inside_t_delta;
	short inside_h_tol;
	short inside_h_delta;

	short h_maxErr[MAXTHSENS];	/* Maximal tolerance violation count. If sensor has   */
	short t_maxErr[MAXTHSENS];	/* more errors than this value, it will be omitted    */
	short p_maxErr;	/* in the output, thinking it is defekt		      */
	short r_maxErr;
	short ws_maxErr;
	short lux_maxErr;
	short energy_maxErr;
	short inside_t_maxErr;
	short inside_h_maxErr;
	char lastValFile[PATHLEN]; /* File to hold the last read values in order to    */
				   /* keep the last values across calls of the program */
	char confLastValFile[PATHLEN]; /* lastValFile name from config file            */
} TOLERANCE;


typedef struct {
	TOLERANCE t;	     /* tolerance values to find erroneous values from station*/
	short maxDropOuts;
	char port[PATHLEN];  /* Name of Serial port */
	char cfgFile[PATHLEN];
	int  speed;	     /* Serial Speed */
	int printTerse;      /* 0:. print terse output of data else normal */
	int printTimeOnly;   /* Print only time; used for setting unix clock */
	int altitude;	     /* altiture above sea; for calculating air pressure */
	int mmrainbycount;   /* mm of rain with each whip count */
	int fd;		     /* Filedescriptor returned by startCom */
	BOOL ignoreTimeErr;  /* Ignore a timedifference between ws2500 DCF and linux system time */	
	BOOL useSystemTime;  /* Use linux system, time instead of DCF */
	int stationId;       /* Id of weather station starting with 1 */
	int suppressWarnings; /*Warnings will not be shown */
	int terseIsJson; /* Switch between JSON and original Terse Output */
} CONFIG;

/* DCF time data structure */
typedef struct {
        u_char dcfStatus;	/* 1: OK;  0: Not OK */
        u_char weekday;
        u_char hour;
        u_char min;
        u_char sec;
        u_char day;
        u_char month;
        short year;
} DCF_INFO;

/* Structure that contains status of tolerance processing for each sensor */
typedef struct{
	u_char h_omit[MAXTHSENS]; /* Flag not to print sensor in case of to many tol errors */
	u_char t_omit[MAXTHSENS];
	short h_currErr[MAXTHSENS]; /* Counter of current tol errors */
	short t_currErr[MAXTHSENS];
	u_char inside_h_omit;
	u_char inside_t_omit;
	short inside_h_currErr;
	short inside_t_currErr;
	u_char r_omit;		/* Rain */
	short r_currErr;
	u_char ws_omit;		/* Windspeed */
	short ws_currErr;
	u_char p_omit;		/* Pressure */
	short p_currErr;
	u_char lux_omit;	/* Light intensity in lux */
	short lux_currErr;
	u_char energy_omit;	/* Pyranometer energy */
	short energy_currErr;
}TOLERANCE_STATUS;


/* WS2500 status data structure, with all data elements available */
typedef struct {
	short  version;      /* The stations bios version: 10->1.0, 31->3.1 */
	u_char tempSens[MAXTHSENS];  /* <16: not available; ==16:OK; >16: num of drop outs +16 */
	u_char rainSens;
	u_char windSens;
	u_char lightSens;
	short   pyranSens;
	u_char insideSens;
	u_char interval;
	u_char ws2500Lang;		/* 0: german; 1: english */
	u_char ws2500Hf;		/* 0: No; 1: yes */
	u_char dcfInSync;
	u_char hasDcf;
	u_char protocol;   	/* 0: 1.2; 1: 1.1 */
	u_char ws2500Type;		/* 0: WS2500; 1: WS2500PC */
	short  addrSensInside; 	/* Number of sensor for inside */
	short  addrSensWind;	/* Addr of wind sensor */
	short  addrSensRain;	/* Addr of rain sensor */
	short  addrSensPyran;	/* Addr of Pyranometer sensor */
	short  addrSensLight;	/* Addr of light sensor */
	TOLERANCE_STATUS tolStat;
}WS2500_STATUS;

/* Data from a temperature himidity sensor */
typedef struct{
	u_char new;
	float temp;		/* temperatur */
	u_char hum;		/* humidity   */
}WS2500_TEMP_HUM;

/* Data from a rain sensor */
typedef struct{
	u_char    new;
	short	count;		/* rain counter */
	short	delta;		/* delta value: curr-last */
}WS2500_RAIN;

/* Data from a wind sensor */
typedef struct{
	u_char new;
	float speed;		/* Wind spees in km/h */
	int  direction;		/* direction of wind in degree */
	float variance;		/* variance of wind direction in degree */
}WS2500_WIND;


/* Data from a inside sensor */
typedef struct{
	u_char newP;	/* The hum-new flag is also used as error condition */
	u_char newTh;	/* so it can be different from the real new flag for p */	
	WS2500_TEMP_HUM th;
	int 	pressure;	/* air pressure */
}WS2500_INSIDE;

/* Data from a lightness sensor */
typedef struct{
	u_char new;
	u_char sunshine;	/* flag for sunshine */
	long lux;		/* Lightness */
	int factor;
}WS2500_LIGHT;

/* Sunshine duration sensor */
typedef struct{
	u_char new;
	short sunDur;	      /* Sun Duration from station  */
	short deltaSunShine; /* delta variable for sunduration delta value */ 
}WS2500_SUN;


/* Data from a pyranometer sensor */
typedef struct{
	u_char new;
	long energy;		/* radiation energie in W/m */
	int factor;
}WS2500_PYRAN;


/* The complete data of all WS2500 sensors */
typedef struct{
	unsigned short blockNr; /* blocknumber given by ws2500. Has no relation to time */
	time_t time;	 /* Date of dataset in seconds from 01.01.1970 */
	WS2500_TEMP_HUM thSens[MAXTHSENS]; /* temp-humidity sensors */
	WS2500_RAIN	rainSens;
	WS2500_WIND	windSens;
	WS2500_LIGHT	lightSens;
	WS2500_SUN	sunDuration;
	WS2500_PYRAN	pyranSens;
	WS2500_INSIDE	insideSens;
}WS2500_DATA;


typedef enum { STARTCOM, POLLDCF, NEXTSET, FIRSTDATASET, GETDATASET,\
		STATUS, INTERFACE } COMMAND;

typedef enum { DOPOLLDCF, DOFIRSTDATASET, DOGETALLDATA, DOGETNEWDATA,\
		DOCURDATASET, DOSTATUS, DOINTERFACE, NOCOMMAND } USER_COMMAND;

