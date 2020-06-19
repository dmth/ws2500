CC	= gcc 
LD	= gcc
CFLAGS  = -Wall -O2
LDFLAGS = 

all:	ws2500

ws2500:	ws2500.o
	$(LD) $(LDFLAGS) -o ws2500 ws2500.o

static:	ws2500.o
	$(LD) $(LDFLAGS) -static -o ws2500 ws2500.o

ws2500.o: ws2500.c ws2500.h
	$(CC) $(CFLAGS) -c ws2500.c

clean:
	$(RM) ws2500 ws2500.o core make.out *~ 

dist:	ws2500.c
	make clean

	ci -u -f -m"ws2500" ws2500.c
	ci -f -u -m"ws2500" CHANGES

	VERS=`cat CHANGES|grep Id:|awk '{print $$3}'`; \
	echo "Version: $$VERS"; P=`pwd`; NAME=ws2500-$$VERS; \
	mkdir "/tmp/$$NAME"; \
	find . -print|grep -v RCS |cpio -pdm /tmp/$$NAME; \
	cd /tmp; tar cvzf $$P/../$${NAME}.tar.gz $$NAME; \
	rm -rf /tmp/$$NAME; \
	cd $$P;
	
install:	dist
	VERS=`cat CHANGES|grep Id:|awk '{print $$3}'`; \
	echo "Version: $$VERS"; P=`pwd`; NAME=ws2500-$$VERS; \
	cp $$P/../$${NAME}.tar.gz /home/krienke/www/ftp/unix/ws2500/; \
	cp $$P/CHANGES /home/krienke/www/ftp/unix/ws2500/; \
	rm -f /home/krienke/www/ftp/unix/ws2500/00_LATEST* ; \
	touch /home/krienke/www/ftp/unix/ws2500/00_LATEST_$${VERS};
