Copyright
---------

wetter.cgi is written by Rainer Krienke and is distributed under the
GNU General Public License. 


Author and warrenty
-------------------

Rainer Krienke, krienke@uni-koblenz.de
Thomas Dreﬂler

The author does not provide any warranty nor responsibility  for whatever might
happen by using this program. If you run it things happen since YOU pressed the
ENTER key. So if your dog starts barking at you or stops eating and looks 
sick after you started the program, don't blame me ....



Wat can it do?
--------------

This perl script is thought to be executed by a web server as CGI
application. So you can watch the output with a web browser pointing to
the scripts URL. It will show a graphical representation of weather data
taken from a mysql database created by ws2500tomysql. 

It will eg show an overview with displays for temperature, humidity, for
rain and wind etc. It will also (textually) show the latest values and the
maxima, minima and the average of all sensors displayed. You can freely
choose the time period that is to be displayed. Next you can click on
each of the images shown in the overview to get a more detailed view of
the sensors data. 

In the latest version it can also generate statistical data  like 
the number of eg rain-, ice- or warm days (and more) in a period of time.

You can program your WS2500PC station to use a certain interval where
data are stored into the stations memory. wetter.cgi can display data
with any interval chosen.
 


Version
-------

See file ($version=....)

Tested on a SuSE 9.1 Linux system with MYSQL 4.0.15

Software Needed
---------------
You need perl obviously. You will need the apache web server as well
as the perl DBI modules to access the mysql database from perl.
You also need the perl CGI module.
You also need the perl module Date::Calc used for date calculations.
Please take care to get a current version of it (version 5.3 works) since
there is a bug in earlier versions, that leads to an error in
wetter.cgi.


Installation
------------

Copy the script to a directory that can be reached by your web server
and adapt the path and URL-variables in the head of the script.
You can also put the whole config in a seperate file: "wetter.cgi.conf".
This is very helpful, when you want to install a newer version of this
tool.  In this case your configuration will not be lost when upgrading.
Besides the script itself you will need 
gnuplot at least version 3.7 patchlevel 1
Older version of gnuplot cannot set a background color, so gnuplot
will fail cause I try to set one. You can however remove the background 
color entry. See
function create*GnuplotConf() in the script in the set terminal line.

Moreover you need several perl modules especially:
CGI, DBI, Date::Calc, and Carp.

Since this script has to write images in the paths given in the scripts
head, you will need write access to these directories. The best choice
is to have the script run with suexec enabled in the web server 
so it is run by your user
id not by an annonymous user like wwwrun. The images created cannot be
deleted by the script itself, since in this case the users web browser
would be unable to display them. So you will need to write a cron job
that takes care of deleting old images from time to time. The cronjob
might consist of a simple call like 

find <wherever> -mmin +30 -print|xargs rm -f

to delete images that are older than 30 minutes.

The script shows (besides other infos) the latest weather data (temp,
wind, ....). Each sensor is displayed with its name to the left. This
name is extracted from the weather database from table "sensor_descr".
You have to enter valid names for each sensor you want to display
together with their sensor id. 

1...r8 TH/Sensors
17: Inside-TH/Sensor 
20: Inside Pressure sensor
30: WindSensor
40: RainSensor
50: LightSensor

If you do not enter this information into the mysql table sensor_descr,
then only the sensor ids will be displayed but no name.

You have to configure the sensors for which latest data should be
displayed. This is done by $latestSens (see script). This variable
contains abbreviations of the sensor you want to display:

TH=Temp/Hum; PR=Pressure; WI=Wind; LI=Light; RA=Rain; PY=Pyranometer

If you want to display the latest values for Temp Hum, Rain and Wind you
have to say:
	$latestSens="TH RA WI"; 
	
in the script or in your config
file. Since the ws2500 station has up to eight TH sensors you can
specify which of these sensors should be displayed in the latest data
overview by setting $latest_th. This variable has to be set with the
sensor *IDs* not abbreviations like TH. So if you want to see the latest
data of TH sensor 1 & 2 & 17 you have to say:

$latest_th=[1,2,17];

Please note the [] arround the numbers!!!
You allways can only specify sensors that you really have.  However if you 
write sensor ids in $latest_th that you do not have data for in your database
this will lead to an error like 

	DBD::mysql::st fetchrow_array failed: fetch() without execute()

If you see this, check your "$latest_th" definition.
In the latest data display section you can also display data that are calculated 
from sensors values like windchill, dewpoint and absolute humidity. Of course 
in order to do so you need at least a temperature/humidity sensor and a wind sensor.
To specify if and how these values sould be displayed you need to fill the valiable
%latest_do like this:

$latest_do{"30"}="WindChill(1)";
$latest_do{"1"}="DewPoint,absHum";

This definition means that in the row of the windsensors latest data the windchill 
will be displayed based on the data of temperature sensor with sensorid 1. The wind 
speed is taken from the windsensor with sensor id 30. The next line says that in the display 
of the temperature sensor with sensor id 1 we want additionaly to standard values to 
display the dewpoint temperature as well as the absolute humidity. The sensor id given (here: 1) 
must of course be one of a temp/hum sensor else the values displayed will probably be simply 
nonesense.


Besides the configuration of the latest data, you surely want to
configure which sensors should be displayed in a graphic. Each graphic
can contain on or more values of a certain sensor type. So you can eg
display 3 TH sensors in one graphic. You can also decide only to display
The T (temperature) part of a TH sensor or to display virtual sensors like 
windchill etc.
You can also have 3 TH graphics
with one sensor displayed in each. To specify which sensors should be
displayed in which graphic, you have to use the function

	addSensor();

before calling this function be sure to have called this line of code
exaclty once:

	$sensorData=sensDisplayData->new($imgPath, $baseImgUrl, $tmpName);

The function addSensor() takes exactly two parameters and has to be called
once for each sensor you want to display. The sequence in which you call
addSensor() for sensors determines the sequence in which the graphics
are displayed. The argument of addSensor() is a anonymous hash ({...})
which contains the settings that describe what you want to display.
There are defaults for most of the things you can set so you basically
only have to denote the sensor type (TH, WI, ...) as well as the sensor
id(s) of this type to display in one graphic. Eg. the call

	$sensorData->addSensor( {"sensType" => "TH", "sensIds" => [17,],
	                         "grfxName" => "My graphics Name"} ,
	                        {} 
			      );

says that you want to display the T/H sensors with ID 17 (inside) and id
1 (first external TH sensor) should be displayed in one graphic. The
graphic gets a title "My graphics Name". 

If you take a look at function setTHdefaults() as well as
setWIdefaults() etc. you will find all the values that can be modified
in a call of addSensor() using the method demonstrated above. In
setTHdefaults() the parameters that can easily be modified by a user
are marked with the comment "USER". Changing these values in a call of
addSensor() does no harm. Changing the other parameters can be more
"dangerous", so you should know what you are doing.

The following sensor types (eg. "sensType" => "Th") exist at the moment:

TH: is a Temperature Himidity display
PR: is the air pressure display
WI: is the wind display sowing the windspeed over time
WD: is the wind display, showing the direction and speed in a polar
    coordinate system
WA: is the winddisplay showing the winddirection (angle) and variance over time
LI: is the light display.



Virtual sensors
---------------

A virtual sensor  is simply a value that has no real sensor hardware but is
calculated from hardware based sensor values. A good example is the windchill
temperature. The value is calculated from the windspeed and the current
temperature.  Wind and temperature are real sensors, winchill is a virtual
sensor. A virtual sensor is always associated with a particular real sensor.
E.G. a Windchill virtual sensor is always associated with a TH sensor. This is
why you can only activate (see below) virtual sensors in a definition of a 
real sensor with addSensor().

At  the moment only a TH sensor has virtual sensors for: Windchill,
abolute  humidity and dewPoint.

Virtual sensors are all predefined they only have to be activated. 
Thats what the second parameter of addSensor() is for. You can 
activate any of the virtual sensors mentioned above by saying something like:

	$sensorData->addSensor(   { "sensType" => "TH", "sensIds" => [1],
	                            "grfxName" => "My graphics Name"
				  } ,
	                          {  "windChill"  =>"1", "absHumidity"=>"1",
                                     "dewPoint"   =>"1"      
				  }
			      );
This would display a graphic for TH sensor with id 1 and would display 
curves for windchill, abolute Humidity and dew point in the same graphic.
Please note the exact spelling of eg "absHumidity" etc. If you do not 
mention the name of a virtual sensor in the second parameter of addSensor() 
or if you assign a "0" instead of "1", the display for this virtual sensor 
will be turned off.


Not displaying all the values of a sensor
-----------------------------------------
Sometime mostly for a TH sensor you might want to display 
say the temperature and windchill  but not the humidity. So you want to 
omit the humiodity value in the graphics. To do so you simply have to fill
the variable omt as part of the first parameter of addSensor() with the 
database column names of those values that should be omitted i.e. 
*not* be displayed. For example if we consider the last example where sensor id
1 was displayed with windchill, absolute humidity and dewpoint me could decide 
that we do not want to see the humidity of this sensor. The configuration would 
be as follows:

	$sensorData->addSensor(   { "sensType" => "TH", "sensIds" => [1],
	                            "grfxName" => "My graphics Name",
				    "omit" => ["H"]
				  } ,
	                          {  "windChill"  =>"1", "absHumidity"=>"1",
                                     "dewPoint"   =>"1"      
				  }
			      );

Here the array omit has one entry "H" and this is the name of the database 
column for humidity. If you want to see only the virtual sensors but 
not neither temperature nor humidity write:

	$sensorData->addSensor(   { "sensType" => "TH", "sensIds" => [1],
	                            "grfxName" => "My graphics Name",
				    "omit" => ["T", "H"]
				  } ,
	                          {  "windChill"  =>"1", "absHumidity"=>"1",
                                     "dewPoint"   =>"1"      
				  }
			      );
 
Of course you have to take care that something is left to be displayed. 
If you for example omit  "T" and "H" and do not display a virtual sensor, then
the graphics for the TH sensor would be empty cause there would not be anything 
left to display. In this case you would see a configuration error, when 
running the script. 

You can also determine if for all sensors values like temperature and 
humidity of a TH sensor the Min,Max,Avg (MMA) values should be printed. 
By defining the array mmaOmit just like omit from above you can say
for which sensor values  you do not want any MMA values to be displayed.
For example:

	$sensorData->addSensor(   { "sensType" => "TH", "sensIds" => [1],
	                            "grfxName" => "My graphics Name",
				    "omit" => ["T", "H"],
				    "mmaOmit => ["T", "H"]
				  } ,
	                          {  "windChill"  =>"1", "absHumidity"=>"1",
                                     "dewPoint"   =>"1"      
				  }
			      );

This would mean for the MMA display, the neither for temperature nor for
humidity mma values would be displayed at the bottom of the page. The only MMA
values you would see then would be those of the virtual sensors defined.


Displaying MMA values for virtual sensors
-----------------------------------------

There is one more point. Take a look at the last example. In this case where
only the virtual sensors windchill and absHumidity and dewPoint are displayed
in a graphic, and MMA values of the real sensors are omitted, you probably
would like to display the MMA values for the three *virtual* sensors below the
graphics itself. As a default this is only done if you look at the detailed
display of one sensor (big graphic) but not in the overview of all sensors
(several small graphics) . So in this overview with the configuration from
above you wouldn't see any MMA values displayed below the (small) graphics.  To
change this you have to modify  the Attribute "doPrintMma" of the virtual
sensors configuration for the sensor  definition. The default value is "1"
meaning print the MMA values only in the detailed view of a sensor, not in the
overview of all sensors. A value of 0 would mean not to print the MMA values of
this virtual sensor anywhere. The value needed to display MMA values in both
the overview and the detailed view is "2". It can be set using a function
called setVirtSensAttrib(). Here the complete demo config: 

  $tmp=$sensorData->addSensor(   { "sensType" => "TH", "sensIds" => [1],
	                            "grfxName" => "My graphics Name",
				    "omit" => ["T", "H"],
				    "mmaOmit => ["T", "H"]
				  } ,
	                          {  "windChill"  =>"1", "absHumidity"=>"1",
                                     "dewPoint"   =>"1"      
				  }
			      );
  $sensorData->setVirtSensAttrib($tmp, "windChill", "doPrintMma", 2);
  $sensorData->setVirtSensAttrib($tmp, "dewPoint", "doPrintMma", 2);
  $sensorData->setVirtSensAttrib($tmp, "absHumidity", "doPrintMma", 2);

The last three calls of setVirtSensAttrib() set the "doPrintMma" attribute
for the three virtual sensors windChill, dewPoint, abHumidity to the value 2
telling those virtual sensors to display their MMA values in the overview as
well as the detailed view. 

Please note that this setting is only done for the virtual sensors of the
(real) sensor defined by the addSensor() call from above. The sensor defined by
addSensor() is assigned to a variable $tmp, and in setVirtSensAttrib() the
virtual sensors attributes are set only for the virtual sensors that belong 
to the real sensor referenced by $tmp that was defined just before. The
definition for two sensor displays say for sensid 1 and sendid 17 could then
look like this:

  $tmp=$sensorData->addSensor(   { "sensType" => "TH", "sensIds" => [1],
	                            "grfxName" => "My graphics Name",
				    "omit" => ["T", "H"],
				    "mmaOmit => ["T", "H"]
				  } ,
	                          {  "windChill"  =>"1", "absHumidity"=>"1",
                                     "dewPoint"   =>"1"      
				  }
			      );
  $sensorData->setVirtSensAttrib($tmp, "windChill", "doPrintMma", 2);
  $sensorData->setVirtSensAttrib($tmp, "dewPoint", "doPrintMma", 2);
  $sensorData->setVirtSensAttrib($tmp, "absHumidity", "doPrintMma", 2);

  $tmp=$sensorData->addSensor(   { "sensType" => "TH", "sensIds" => [17],
	                            "grfxName" => "My graphics Name",
				    "omit" => ["T", "H"],
				    "mmaOmit => ["T", "H"]
				  } ,
	                          {  "windChill"  =>"1", "absHumidity"=>"1",
                                     "dewPoint"   =>"1"      
				  }
			      );
  $sensorData->setVirtSensAttrib($tmp, "windChill", "doPrintMma", 2);
  $sensorData->setVirtSensAttrib($tmp, "dewPoint", "doPrintMma", 2);
  $sensorData->setVirtSensAttrib($tmp, "absHumidity", "doPrintMma", 2);

This example of two definitions show that $tmp is just a valriable that can be
reused.  

As another complete example take this: We want to display latest values for
sensor T/H 1,2 as well as for Rain and Wind. 
We also want to display graphics for the inside TH sensor (id:17), the
TH sensors 1 and 2 (but in another graphic than the inside sensor). 
For sensor id 17  we want also to display the virtual sensor dew point.
For ids 1 and 2 we do not want to display the virtual sensors. 
Next we want one more graphics again for sensor id 1 but this time we only
want to show dewpoint windchill and absolute humidity leaving out temperature
and humidity.

Besides we want the Rain-Sensor and the pressure sensor and the Wind sensor in this sequence. 
Finally we want to display a graph that shows the prevailing wind
direction.
To do this use this configuration:

$latestSens="TH,WI,RA";
$latest_th=[1,2];              # Latest Data temp/hum sensors

$sensorData=sensDisplayData->new($imgPath, $baseImgUrl, $tmpName);
$sensorData->addSensor( {"sensType"=>"TH", "sensIds"=>[17]}, 
                        {"dewPoint=> "1"} );
$sensorData->addSensor( {"sensType"=>"TH", "sensIds"=>[1,2]}, 
                        {} );
$sensorData->addSensor( { "sensType"=>"TH", 
                          "sensIds"=>[1], 
                          "omit"=>["T", "H"]
			}, 
			{"windChill"  =>"1", "absHumidity"=>"1",
                         "dewPoint"   =>"1"} );
$sensorData->addSensor( {"sensType"=>"RA"} );
$sensorData->addSensor( {"sensType"=>"PR"} );
$sensorData->addSensor( {"sensType"=>"WI"} );
$sensorData->addSensor( {"sensType"=>"WD"} );


Script configuration
--------------------

The script can be personalized  by a series of variables in the head of
the script.

You can copy all the variables between START CONFIG and END CONFIG
into a file that can be reached by your web-server unter the path
given in $configpath.  Usually the best is to put the wetter.cgi.conf
file in the same directory where the script itself is, or to out it in
the directory /etc/ws2500/.
$configPath is set to the value of the
scriptname (eg wetter.cgi) with ".conf" appended. The scriptname
and path are retrieved from the Webservers environment variable
named SCRIPT_FILENAME. apache on linux does provide this variable
automatically so you don't have to do anything else but name the
configuration file accordingly (usually wetter.cgi.conf) and put it 
in the same directory like the script itself.
If the given file exists and is readable
the scripts config will be read from there overriding the variables
set above. 

If you created a config file, made it readable, placed it into the same
directory as the script itself and still it is not used it may be that
your webserver does not provide the variable needed. In this case you
can either change one line of the wetter.cgi-script like shown below or
put your configuration file in /etc/ws2500/. 

If you choose to change the script, then write down
the complete path (starting with /) to the config file eg:

$configPath="/home/krienke/www/wetter/wetter.cgi.conf"

You find this line right before the comment "END CONFIG VARIABLES" in
the head of the script. Change the value of this variable to the correct
path and it will work.

Take care that your config file contains a valid perl-script if
unsure use perl -c wetter.cgi.conf to check the syntax, because
running wetter.cgi you won't see an error if your config file is
wrong!!!!! You will just see, that wetter.cgi is not showing any
output.
Please take care that your config file is readable only by you and
your web server but not to anyone else!


Script Parameters
-----------------

The script obeys several parameters, that are set automatically (eg
startdate and enddate of data to be displayed. These parameters are
passed in the scripts url in the form "?param=value". There is one
parameter thats useful in the initial display: ?days=<n> where <n> is
the number of days that should initially be displayed from the current
date back. So by calling the script with http://...../wetter.cgi?days=7
you always get a display of the last 7 days.

Another parameter that is used similar to the days parameter is
hours=<n>. It tells the script to display the last n hours in the
graphics instead of the default. To receiver a good result you should be
using at least a value of 6 hours.


Modifying the script (sorry this section is a little outdated .... )
--------------------

The script is in many ways quite generic making it a little complex at
some points. You should be well aquainted with perl, if you want to
change it. On the other hand many things can be done in a very easy
fashion.  For example you can easily
modify it to display not only one temp/hum sensor in a diagram but 5 or
eight. All it takes is a modification of some parameters for the function
plotData which makes all the real work to prepare plotting. Most of the
functions in the script work directly on the database with tables and
columns with particular names and will assume that
the database used is of the exact type that ws2500tomysql creates.

The script is called like a CGI script, and it prints out a HTML form to
enter a new start and end date for data display. The action URL points
again back to the script itself, so it will display the data of the
selected period of time. To give the user quicker control of what he
wants to see, I inserted some dynamically created links to select 
the current/next/last
day/month. The links point again to the script itself, but each link
adds several parameters to the URL line like http://..../wetter.cgi?pl=TH
which can be evaluated by the script to take appropriate action. The
important paramneters are:

   pl=[TH|PR|WI|LI|RA|PY]
   This parameters directs the script to draw only the plots for sensors
   given as argument to the pl variable. So pl=TH means only plot the
   Temp/Humidity sensors data nothing else. If this parameter is missing
   all plots are created. Of course this is only done for plotroutines
   found in the script. So its not enough the give a new parameter in
   order to get a ne plot of a sensor not yet plotted. See the code.
   If this variable was found in the URl the perl
   variable $plotsSelected will be set to 1. This variable is evaluated
   at different locations in the script.

   ed=date,sd=date
   These variables are used to specify the StartDate and EndDate of the
   data to be plotted. Date values are always given in the form yyyy-mm-dd
   (year-month-day).

   mmaed, mmasd
   These variables mark the date range used for calculating the minimum,
   maximum and average values in the script. The format is as usual
   yyyy-mm-dd

   mma=M,M,A
   Tis variable directs the plotting of Maximum, Minimum and Average
   values. if any of the values M,M,A is "1" the corresponding curve
   will be displayed else not.


The script consits of several perl classes (packages) as well as some 
functions  belonging to the package main. Here is a very short description of these
classes:


package sensDisplayData:
========================
Class that handles basic sensor descriptions. For each sensor type there is a
definition of all data needed by the sensor. The user can add sensors to a list
of sensors to be displayed by calling addSensor().
Each element of the resulting list contains data of a particular real existing
sensor (with attributs of database table and columns needed for this sensor etc)
as well as data about virtual sensors that are caculated from the real data
(like windchill). For virtual sensors each list element contains also a
description about the data needed and generated by this virtual sensor.

The list of sensors is implemented by an array that holds references to hashes.
Each hash describes one sensor as well as result data added by different methods
like (allInCols, allOutCols, ....)

Important Methods:
------------------
setGlobalDefaults()
setTHdefaults()
setPRdefaults()
setWIdefaults()
setWDdefaults()
setRAdefaults()
setLIdefaults()
getSensorNames()
addSensor()
getFirstSensor()
getNextSensor()
calcInputOutputCols()

Result Values:
--------------
* allInCols...
  Each hash of one sensor has the variables
  
  allInCols 
  allOutCols 
  allUnitNames 
  allOutNames
  colsDefined 
  extraCols
  extraUnits
  extraNames
  
  defined. The value
  of this hash is a reference to an array containing the values. For colsDefined
  the value of the hash is a reference to another hash.


 
 
package dataManager:
====================
This class is responsible for managing the data for data display of one
sensor.The class handles all important actions:
- Building SQl commands to extract the data needed based on the data 
  of a sensor from class sensDisplayData.
- Calculation the MMA values for this sensor
- Extracting the data from the database into an array of hashes. Each row in the
  array is one row of data. The hash contains the data of the different database
  columns requested.
- calculate the values for the virtual sensors from the existing real data.
- write the resulting data with all columns wanted (for real and virtual sensors
  as well as MMA-values) to a file for gnuplot
- Create the gnuplot control file 
- Start gnuplot to create the output graphics

* an instance of dataManager gets: 
  - a reference to the class sensDisplayData itself to be able to call its methods
  - a reference to a sensor of sensDisplayData to be worked on.
  

Important Methods:
------------------  
prepareSensData()
writeGnuplotHeader()
writeGnuplotCmds()
writeGnuplotFile()
applyVirtSensors()
getDataFromDb()
buildAllSqlCommands()
buildOneIdSqlCommand()
getMmaValues()

Result Values:
--------------
* MMA Values
  MMA values are stored in 
  $self->{"results"}->{<sensid>}->{"mma"}->{<mmaDBColName>}->
     ...->{"minValue"},  ...->{"minDate"}, ...->{"minTime"}
     ...->{"maxValue"},  ...->{"maxDate"}, ...->{"maxTime"}
     ...->{"avgValue"}

* MMA values for virtual sensors:
  $self->{"results"}->{"virtSens"}->{<virtSensName>}->{<sensId>}->
       {"mma"}->{<virtualOutName>}->
     ...->{"minValue"},  ...->{"minDate"}, ...->{"minTime"}
     ...->{"maxValue"},  ...->{"maxDate"}, ...->{"maxTime"}
     ...->{"avgValue"}
       

* SQL-Commands
  The sql command built to retrieve data from the db for this sensor:
  $self->{"results"}->{<sensid>}->{"sql"}
  
* Results of virtual Sensors    
  Results for virtual sensors are stored in the results hash that also contains
  all other results from the database query. 
  
  
  
package simpleTable:
====================
Simple HTML tybe management


package main:
=============
All the rest




Have lot of fun 
Rainer Krienke
10/2004
