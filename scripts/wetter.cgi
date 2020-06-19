#!/usr/bin/perl

use strict;
no strict "vars";

#$ENV{"DBI_PROFILE"}="2";  # Enable Profiling for DBI

#
# Perl CGI-Module for web-displaying weather data
# R. Krienke, krienke@uni-koblenz.de
$version='$Revision: 0.74 $';
#
# Changes:
# 2003-04-06 tdressler@tdressler.de
#		Add Light Sensor
#		Add calcFaktMinMaxAv (only needed by mysql,all others can use a view)
#		minor local changes
# 2003-05-02 krienke@uni-koblenz.de
#	       Added a "total" value for rain sensor display
# 2003-06.04 krienke@uni-koblenz.de
#		Rewrote parts of the script to match the new database scheme in which
#		the rain sensor has a diff value that is used instead of the counter value
# 2003-09-03  krienke@uni-koblenz.de
#	Complete rewrite of sensor configuration. Now the class sensDisplayData
#	holds all configuration of sensor data to be displayed. This data is then
#	run through for all sensors defined to create the graphics. This way a user can 
#	no create several T/H graphics with different sensor ids beeing displayed.
#	Added another Class simpleTable to print HTML tables.	
# 2003-12-15   krienke@uni-koblenz.de
#	Added some more features like display of dew point, windchill
#       and abolute humidity in latest data display. Added features to display
# 	average/Minium/Maximum 
#	values in graphics for days, weeks, months and years.
# 2003-12-15 Joerg <joerg@alcatraz.shacknet.nu>
#	added error display in latest data section. Errors will be
#	flagged by printing the sensors name in another color. See
#	config variables below.
# 2004-04-01 krienke@uni-koblenz.de
#	Rewrote much of the code in order to use GMT time internally in 
#	the script since from ws2500 version 0.70 all dates in the
#	DB are kept in GMT not local time.
# 2004-06-08 philip.marien@pandora.be, krienke@uni-koblenz.de
#	Fixes several bugs that cause some warnings. Now setting 
#	$timeIsGMT to 1 results in script output beeing in GMT time
#	instead of local time.
# 2004-10-01 krienke@uni-koblenz.de
#       Large rewrite of the whole data management and display parts of the software.
#	Created the new class dataManagement for this that does most of the work.
#	Created the idea of virtual sensors like windChill that can be displayed
#	now for each TH sensor type just by switching it on.
#	Added HTML style sheets to for font selection etc for easier 
#       style control. 
# 2006-02-01 krienke@uni-koblenz.de
#       Implementation of the statistics display.
#       Modified Max and Avg rainsensor display. These values now represent 
#       an average, maximum in one hour and not like bevor in one sensor 
#       interval. 
# 2011-05-04 krienke@uni-koblenz.de
#     - Fixed bug with quoting of column names in getLatestValues
#       The column names like T, H, range were quoted (`T`, `H`, `range`
#       to avoid SQL problems but these quoted names were also used
#       as index for storing corresponding data in associative arrays.
#       $x->{"T"} is correct but $x->{"`T`"} was used instead.
#       Thanks to  Thomas Hübner who found this bug that led to missing
#       terndsymbols in the latest values of the configured sensors
#     - Fixed gnuplot "set xlabel" command for gnuplot version 4.4.2
# 2012-02-01 krienke@uni-koblenz.de
#     - Added config options to use wind gustspeed value insread of wind
#       speed value for calculating windChill. The new options are 
#       $latestWindChillUseGustSpeed for latest values and 
#	"windChillUseGustSpeed" for windchill display in graphics 
#	see demos below.
# 2012-02-16 krienke@uni-koblenz.de
#	- Added more support for multiple stations
#	  Latestvalues have to be given in sensorId.stationId snytax now for multiple stations
#         new  $latest_pr=, $latest_wi, ... have been added in analogy to $latest_th
#	  to allow a selection of station and sensors to be displayed in latest values.
#	  New $defaultStationIdList=[] was added, and new "stationIdList"=>[1,3,4] for addSensor()
#	- Added fisrt support for radiation and uvindex from Davis VP2 station 
#	  New sensor types LR (Light radiation) and LU (Light UV index) were added
#
# What you need:
# a running Web server with cgi support and suexec (so the script is
# run by your account and not by eg wwwrun). This is good since this script
# has to write image files somewhere, where the web server can access
# them. You have to take care, that these generated images will be removed
# after a while (eg find <wherever> -mmin +30 -print|xargs rm -f).
#
# You also need gnuplot at least version 3.7 patchlevel 1
# Older version of gnuplot cannot set a background color, so gnuplot
# will fail. You can however remove the background color entry. See
# function writeGnuplotHeader() in the set terminal line.
# 
# Moreover you need several perl modules especially:
# CGI, DBI, Date::Calc, and Carp
#
# If you have all this you still have to adjust some paths and database
# relevant variables to access your mysql database.
# Now you have to define which sensors to display and which latest
# values to display. Di this by setting $latestSens and $latest_th below
# and by adding addSensor()-calls as described below.
# Copy this script wherever you want it and your web server can access
# it and give it a try. It will of course only work if the database
# scheme in use is exacly that created by ws2500tomysql!!!
#

use CGI qw(:standard);
use Date::Calc qw(:all);
require DBI;

# Needed only on solaris systems with lib in /usr/local:
$ENV{'LD_LIBRARY_PATH'}='/lib:/usr/lib:/usr/local/lib';
# Useful quite everywhere:
$ENV{'PATH'} = '/bin:/usr/bin:/sbin:/usr/sbin';

#printenv();

#
# -------- START CONFIG VARIABLES ---------------------------------------------
#
$driver="mysql";
$sysDbName="mysql";
$dbServer="sqlhost";
$dbUser="sqluser";
$dbPassword="sqlpassword";
$database="database";
$defaultPort="3306";

# This variable controls if the *output* is in GMT or in Local time
# Internally very date and time value is in GMT. User input is converted to GMT.
$timeIsGMT=0;		# This variable controls if the script time 
			# input as well as output is in
			# GMT or in Local time. Internally every date and
			# time value is in GMT. User input is converted
			# to GMT if needed.
$colGrfxTable=2;	# Number of columns in HTML table for graphics
$initialDisplayDays=7;  # range ofdays to be initially displayed
$doAutoBaseData=185;    # If the date range to be displayed has more than
			# this number of days we automatically use average
			# values on hourly basis for display. If you don't
			# want this, set this variable to 0
$navPanelPos="top";     # Position where the navigation panel (Darstellungsparameter) is 
                        # displayed. May be "top" (above graphics) or "bottom" (beneath graphics)			

# Path where the created images are stored
$basePath="/home/admin/www/wetter";
$imgPath="$basePath/images";
# URL to access the images in Path "$imgPath" via the web-server
$baseUrl="http://userpages.uni-koblenz.de/~krienke/wetter";
$baseImgUrl="$baseUrl/images";


# If you assign a URL to this variable the target (should be a .css text file)
# is used to get all the css definitions instead of the internal definitions
# made below (search for variable $docCss). If you leave $externalCssUrl
# empty the internal definitions are used.
$externalCssUrl="http://localhost/mypath/wetter.css";     
# If you place the css file (here: wetter.css) in the same directory like 
# the wetter script you can also simply write without http://...
$externalCssUrl="wetter.css"; 
# The setting below disables external css usage instead the internal
# default css settings will be used
$externalCssUrl="";     


# ==================== defaultStationId ============================
# You can define a defaultStationIdList. The values you enter in this list
# are the weather station numbers for which a sensor display can get its data.
# The alternative is to set this value in an addSensor()-call (see below) when defining
# a particular sensor saying "stationIdList"=[1,2] which means that in data for this 
# sensor can be used either from station 1 or from station 2.  If you do not use "stationIdList"
# in addSensor() then the default value of defaultStationIdList is used instead.
#
# The default can be set using $defaultStationIdList=[1,2,5]. 
# Please note that when using several station you have to 
# use the sensorId.stationId syntax for defining the latest values display!!!
# In each addSensor() call you can however always override this default by
# writing eg  "stationIdList"=>[3,4] for one sensor. See examples below. 
# 
# The old $defaultStationId=1 - syntax is still supported for backward compatibility
# but should not be used any longer.

#
# Makeing a list of ids the default when using multiple weather stations:
#$defaultStationIdList=[1,2,6,8];
$defaultStationIdList=[1];
# The default below  means "any stationId" is valid when searching for weather data
# $defaultStationId="1";


# ==================== Latest value display definition ============================
# Unit of Windspeed to be displayed
# 0: km/h, 1: Knots, 10: Knots and Km/h
$latestWindSpeedType="0";
# If nonzero then wind gustspeed is used instead of wind speed for
# calculating the latest windchill value. Of course this is only possible
# if your station provides a gustspeed value which is true for 
# a davis vantage pro2 but not true for a ws2500. So for a ws2500 you should 
# set this variable to "0".
$latestWindChillUseGustSpeed="0";

# if set to 0 no wind gust speed display will be shown in the latestData display
# instead a Wind variance display will be visible along with the other standard values
# if set to one wind variance will be replace y wind gust speed
$latestWindGust=0; # may be 0 or 1

# Enable Windrose icons in latest display for wind sensor
# The icons need to be present in the icons subdirectory in the place where wetter.cgi
# is located. If set to 0 no windrose symbols will be shown
# The icons should be named like the wind directions (eg n.png, s.png ssw.png). 
# The size should be not more than 50x50 pixel. All names are: 
# nno.png  no.png  nw.png   o.png    so.png  sso.png  sw.png   w.png
# nnw.png  n.png   ono.png  oso.png  s.png   ssw.png  wnw.png  wsw.png
$latestWindRose=0;
$latestWindRoseUrl="$baseUrl/icons";

# Types of Sensordisplays
# TH=Temp/Hum; PR=Pressure; WI=Wind; LI=Light; RA=Rain; 
# LR=Sunlight Radiation (Davis VP2)
# Which sensor to display in Latest data section of display 
# Only add Sensors you really have!!!
# eg: $latestSens="TH,PR,WI,RA,LI,LD";
$latestSens="PR,WI,RA,TH";
# Next you have to define for which sensors from which weatherstation you want to display 
# latest values. This is done by assigning a list of sensorId.stationId values to 
# $latest_th (for T/H-Sensors), $latest_pr (for barometric pressure, $latest_wi,$latest_ra.
# All your weather stations have an id, a number. The first usually has id 1, the second id 2....
# Eg:
#
# $latest_th=[17.2,1.2,17.5];     # Latest temp/hum sensors sensorId.stationId for multiple stations
#
# This definition would display three lines of latest data all for different 
# Temperatur Humidity sensors: sensorId 17 from stationId 2, sensorId 1 from stationId 2
# and sensorId 17 from stationId 5. 
# If you have just one station this usually has stationId 1. 
#
# Please note: You also have to define latest_do for virtual (calculated) 
# latest values below using the same sensor.station syntax .
# !!! So if you use the sensorId.statioonId syntax also use it below in 
#     $latest_do definitions
# $latest_pr=[1.2, 1.5];		 #Latest Data pressure sensors sensorId.stationId
# $latest_wi=[1.2, 1.5];		 #Latest Data wind sensors sensorId.stationId
# $latest_ra=[1.2, 1.5];		 #Latest Data rain sensors sensorId.stationId

# Some options that can be used to display latest data that is calculated from the
# original data values. The value on the right side is a list of logical names
# that can be calculated like WindChill and Dewpoint.
# The key of $latest_do is the sensorId or sensorId.stationID 
# for which the given logical names like windchill will be calculated.
# So for windchill calculation this is the id of a windsensor.
# For the windchill we need the sensorId of the temperature sensor to be used.
# This id is given by the values in braces on the right side. 
# If you have multiple stations at work and have defined $latest_wi, $latest_th
# using the sensorId.stationId syntax you have to use the same syntax here
# For example:
# 	$latest_do->{"wind"}->{"1.2"}="WindChill(3.2)"; 
# means that for wind sensor id 1 
# of station id 2 we want the windchill to be calculated as a latest value. For this we use 
# a temperature sensor with id 3 of station 2, we might as well use the first temperature
# sensor of the second station: "WindChill(1.2)"
# If you have just a single station you just use the sensorId everywhere instead of 
# using the syntax sensorId.stationId.

undef %latest_do;
### Entries if you have a single weather station. Only sensId is used here:
$latest_do->{"wind"}->{"1.1"}="WindChill(1.1)";	# Calc windchill wind sens 1 th sens,
$latest_do->{"th"}->{"1.1"}="DewPoint,absHum";   # Calc DewPoint, absHum for TH sens 1, single station
###  Entries if you have multiple weather stations. sensorId.stationId is used here
#$latest_do->{"wind"}->{"1.2"}="WindChill(1.2)";
#$latest_do->{"th"}->{"1.2"}="DewPoint,absHum";
#$latest_do->{"th"}->{"17.2"}="DewPoint,absHum"; # calc DewPoint and absHum for th sens 17 station 2
#$latest_do->{"th"}->{"17.5"}="DewPoint,absHum";

# The following variable lets you omit some values from the latest data display of one sensor
# If you want eg not to display the Humidity value of a TH sensor but only the 
# temperature in the latest data section of this sensor
# the following will do the job for a sensor with sensor id 1 
# The value ("H") is the name of the database column to be omitted.
#$latest_omit{"1"}="H";

# For rain and pressure sensors you can activate the trendData display. Doing this
# shows at *most* 3 older values from these sensors (as well as the current value anyway) 
# in the latest display. Note: Only *3* values are allowed since there is no more room for more
# values. You have to specify the number of hours for each of the three values of each sensor.
# If you e.g. say: 1h,6h,12h this means that for this sensor the value one/six/12 hour(s) ago will be
# displayed. Please keep the format: eg "6h" not "6" nor "360Minutes"!!! If you do not want these
# values to be displayed say eg: $latest_trendRain=[ ]; 
$latest_trendRain=[ "1h", "12h", "24h" ];
$latest_trendPressure=[ "3h", "12h", "24h" ];
#
# Watch out this is for a trend sign (up or downarrow) for temperature/humidity
# sensors. The left value is the sensorid, the right value the time in *MINUTES*
# to look back in order to compare this value with the current one. 
# So "17:10" means that for temp/hum sensor with id 17 we look for a value that
# is 10 minutes old. For each sensor only one value is allowed here.
# Be sure to choose a time that is long enough. If eg your station collects data at an 
# interval of 15 minutes it does not make sense to use eg 10 minutes below.
# You can define it here for all sensors it will be used only for those you
# add below using  addSensor()
$latest_trendTemp=[ "17:30", "1:30", "2:30", "3:30", "4:30", "5:30", "6:30", "7:30", "8:30"];

# The threshold values for sensors which show trends by an arrow sign. If the difference 
# of the current value of such a sensor and an older value is larger than the first value 
# given below an arrow (up or down) will be displayed. 
# The values given below define ranges for the value difference. For example the 
# values 0.1, 0.2, 0.4 define three ranges:  0.1->0.2[, 0.2->0.4[, 0.4 ->.... 
# Differencevalues smaller than the first value (here:0.1) will not be decorated 
# with a trend sign. Depending on which range the current difference fits in, a different 
# symbol for "small change", "more change" and "big change" will be displayed. 
# Exactly three  values a,b,c (defining three ranges) are allowed.
$latest_trendThresholdT=["0.1", "0.3", "0.5"];  # Tempdifference values little, some, a lot
$latest_trendThresholdH=["1", "3", "5"];   	# Humidity difference
$latest_trendThresholdPres=["1", "2", "3"];     # Pressure difference


# The trend-symbol definition. There are three up and three down symbols that indicate 
# a week, average and a strong thrend up or down.
$latest_trendSymbDown= ['<FONT color="black">&darr;</FONT>',     # a  little
                        '<FONT color="darkRed">&darr;</FONT>',   # somewhat more     
                        '<FONT color="red">&darr;</FONT>' ];	 # a lot 
#
$latest_trendSymbUp=['<FONT color="black">&uarr;</FONT>',       # a  little
                     '<FONT color="darkRed">&uarr;</FONT>',	 # somewhat more
                     '<FONT color="red">&uarr;</FONT>' ];	 # a lot 

# You may choose if a trend symbol or the symbol and the difference value or
# only the difference value without a symbol should be printed.
$latest_trendSymbMode="symbol+value";
#$latest_trendSymbMode="symbol";
#$latest_trendSymbMode="value";
#
# The colors for different amounts of the difference. Corresponds to 
# $latest_trendSymbDown[123] and $latest_trendSymbUp[123] 
$latest_trendSymbTextCol=["black", "darkRed","red"];
# Relative text size: Allowed are values like -1, -2, ... which makes the text size
# used for printing the value one, two, ... steps smaller than regular text.
$latest_trendSymbTextSize="-2";
    
# This variable controls whether in the latest data output a sensors errors
# will be displayed. If its !=0 then if a sensor had more dropouts in the last
# hours (given by $latestAlertHours) the sensors name will be printed in 
# the color $latestAlertColor, to show the user that this sensor had 
# to much errors (==drop outs) in this period of time. 
# The numbers of errors is taken from the error table in the database.
# So, for example
# you could say, that if any of sensors displayed in the latest data section
# had more than 10 errors in the last 12 hours then display its name in red:
#
$latestAlertErrCount=10;
$latestAlertHours=12;     # 
$latestAlertColor="red";  # Value has to be html conform


$tmpName="$$";


# ==================== Definition of sensor graphics to be displayed ============================
# Next you define all the sensor graphics (also called sensor displays) that will be displayed in a HTML table
# For each sensor you want to add, you have to write down a addSensor() call
# with appropriate paramters. Bevor the first call to addSensor() you have to create
# an object of Class "sensDisplayData". This is done by exactly using the first line
# see below) with sensDisplayData->new() before the first addSensor() demo call.
# This has to be done excatly ONE time, and then you can place calls to addSensor()
# using the just created object:
#
# $sensorData=sensDisplayData->new($imgPath, $baseImgUrl, $tmpName);
# $sensorData->addSensor( .... );
# $sensorData->addSensor( .... );
#
# The minimum of information in the first parameter 
# (the first hash, surrounded by {}) in addSensor() is the sensor
# type which may be one of TH, PR, WI, WD, WA, RA, LI. 
# TH is a Temperature Himidity display
# PR is the air pressure display
# WI is the wind display sowing the windspeed over time
# WD is the wind display, showing the direction and speed in a polar
#    coordinate system
# WA is the winddisplay showing the winddirection and varince over time
# LI is the light display.
# LR is sunlight radiation. A value retrieved by Davis Vantage Pro2 Radiation sensor
#
# All Parameters are given in a anonymous 
# hash ({"NAME1"=>"value1", "NAME2"="VALUE2", ...}). Besides the type of sensor you
# can specify all the parameters defined in the set??defaults() functions defined below, 
# where ?? is one of the Types from above (TH, ...). You probably want to specify 
# the sensorid of the sensor to be displayed, else the default sensorId for each 
# type is used. To specify one or more sensorids for one graphics simply add 
# the ids like {"sensType"=>"TH", "sensIds" => [1,2,17]}. This example would then
# display T/H sensors with id 1,2 and 17 in one graphic.
# Especially for TH sensors where temperature and humidity can be printed
# it might be useful to be able to display just one of both or even none of
# both but just the windchill value (a virtual sensor) based on this sensor.
# To do so just set the omit array to the values that should not be printed. eg:
# "omit"=>["T", "H"] would not display temp and hum of a TH sensor. So if there was no
# virtual sensor defined you would'nt see anything but an error message the there are 
# no output values to be displayed! So always take care that there is at least one value left
# one of a T, H value or a virtual sensor value.
#
# For some sensors it might be useful to let gnuplot automatically calculate
# the Y-range. Usually the lower value is set by the script to a fix value.
# For TH-Sensors this is eg 0". If you would like to let gnuplot
# determine the Y bounds by itself set "lowYbounds"=>"auto" in the
# addsensor() call like shown below.
# 
# If you do not like the default sizes of the graphics you can modify them for each sensor
# by adding non default values to the addSensorCall like 
#$sensorData->addSensor( {"sensType" => "TH", "sensIds" => [3],
#			  "xSmallScale"=>0.75, "ySmallScale"=>0.75,
#			  "xNormalScale"=>1.5, "yNormalScale"=>1.5 },
#				 {  } ); 
# the Smallscale Variables desscribes the relative size of a graphic in the overview, whereas
# the NormalScale Variables determine the relative size in the detailed sensor graphics
# The default for SmallScale is 0.5, the default for  NormalScale is 1.1.  These values are multiplied
# with the default width/height that gnuplot generates. So a value of 0.5 means "half of the normal size"
# The "normal" size is given by what gnuplot generates for the PNG terminal.
#
# By default all sensors (exepct WA, WD) defined by addSensor() will also be used in the
# statisticsMode. This may lead to a strange looking statistics table in 
# case that one real sensor is shown in two graphics for example with 
# different virtual sensor values. In the statistics display this would lead to the fact 
# that the same sensor beeing shown twice with the same statistic values since
# the statistic display  only shows stats of real sensor values not of virtual.
# If a sensor that is defined by addSensor shall NOT be visible in the statistics overview
# then one may set the attribute "statistics" => "0" like this:
#
#$sensorData->addSensor( {"sensType" => "TH", "sensIds" => [3],
#			  "statistics"=>"0", 
#                         "xSmallScale"=>0.75, "ySmallScale"=>0.75,
#			  "xNormalScale"=>1.5, "yNormalScale"=>1.5 },
#				 {  } 					);
# 
# It is even possible to define sensors only for statistic evaluation that will
# never be displayed in a graphics. This can be done by setting the "graphics"
# flag to "0" like in:
#
#$sensorData->addSensor( {"sensType" => "TH", "sensIds" => [3],
#			  "graphics"=>"0" },  {} 				);
#
# Usually a sensor inherits all entries in $defaultStationIdList as well as the single value
# $defaultStationId defined above. This id described for which weather station a sensors value 
# is displayed. If you do not want to use the defaults, define stationIdList in an addSensor call. To 
# display data of the second weather station of the third TH sensor you could write:
#$sensorData->addSensor( {"sensType" => "TH", "sensIds" => [3],
#			  "stationIdList"=>[2] },  
#			   {} 	
# 								   );
#
# If you want to allow that data for one sensor is taken from different weather stations
# you can assign a list of valid stationid's:
#$sensorData->addSensor( {"sensType" => "TH", "sensIds" => [3],
#			  "stationIdList"=>[2,3,4,6] },  
# 			  {} 				           );
# This means that in a sensor display for TH sensor id 3 values are taken from weather stations
# with either id 2, 3, 4 or 6. This is eg useful if replace your current station with a new one 
# but you want to see values from sensor id 3  from the old station as well as values from sensor id 3 from the new station with a different stationId. 

#
# In a complex setup with several weather stations you might want to manually decide which sensors 
# are *not* used to determine the latest data set available, displayed above the latest values table.
# You can say that a certain sensor should not be considered when searching for the latest data set by 
# setting  "ignoreInGetLastTimeDateSet"=>"1" like in this sensor definition:
#$sensorData->addSensor( {"sensType" => "TH", "sensIds" => [3],
#			  "statistics"=>"0", 
#                        "xSmallScale"=>0.75, "ySmallScale"=>0.75,
#			  "xNormalScale"=>1.5, "yNormalScale"=>1.5,
#			  "ignoreInGetLastTimeDateSet"=>"1" },
#				 { } 					); 
#
# In this case the sensor will not be visible as a graphics but will appear in the 
# statistics display.
#
# -------------------------- defining virtual sensors ------------------------------------
# The addSensor() function actually has two Parameters. The first one has been descibed just above. 
# The second one describes which virtual sensors (if there are any defined in the 
# set*defaults() functions) should be active.
# At the moment only for TH-sensors there are virtual sensors for windchill, 
# absolute humidity and dewpoint calculation. To activate one of them for a 
# TH-sensor the second parameter for addSensor() is a hash like:
# {"windChill"  =>"1", "absHumidity"=>"1", "dewPoint"   =>"1" }
# In this hash virtual sensors can be turned on by assigning them a "1" as showed above.
# If left undefined ({}) or even omitted no virtual sensors will be displayed.
# Please take care of the spelling of the virtual sensor names given above
# Only  one or all in the three (windChill, absHumidity, dewPoint) can be used.
#
# The wind sensor can be configured to plot data in kts instead of km/h
# To do so simply put the directive "windSpeedType"=>1 in the definition of the windsensor. 
# The example below. "windSpeedType"=>0 is the default and means plot in km/h. 
# You can set this option for every WI (Windspeed) and WD (Winddirection/speed)
# plot type individually.
#
# Attention. Either define the sensors here NOT using a config file or
# comment out the demo defs below and put the real definitions into 
# your config file. But DONT put addSensor()-calls  and the creation of 
# the sensDisplayData object in both the script and
# your config file, since this will result in nonesense or even an error!
# Values you might find useful to change are marked as USER in function
# setTHdefaults(). The same is of course true for the other sensor types not 
# only for T/H.

#$sensorData=sensDisplayData->new($imgPath, $baseImgUrl, $tmpName);
#
#$sensorData->addSensor( {"sensType" => "TH", "sensIds" => [17,2], 
#			  "grfxName" => "My graphics Name",
#			  "lowYbounds"=>"auto" },
#			 {   }   );   # No virtual sensors activated
#			 
# Now we want to define a TH sensor with virtual sensors windChill and 
# dewPoint activated:
#$sensorData->addSensor( {"sensType" => "TH", "sensIds" => [1]},
# 			 {"windChill"  =>"1", "dewPoint"   =>"1" } ); # Virtual Sensors
# The same like above but we only want to print the virtual sensor values
# not temperature or Humidity
#$sensorData->addSensor( {"sensType" => "TH", "sensIds" => [1], "omit"=>["T", "H"] },
# 			 {"windChill"  =>"1", "dewPoint"   =>"1" } ); # Virtual Sensors
#
# If your station has a wind "gustspeed" value and a wind "speed" value (eg Davis VP2 pro) you can
# choose which of the wind speed-values is used for calculating the whindChill temperature value.
# The default is to use the wind "speed" value. If you want to use "gustspeed" instead try this:
#
#$sensorData->addSensor( {"sensType" => "TH", "sensIds" => [1], "omit"=>["T", "H"], 
#			   "windChillUseGustSpeed"=>"1" },
# 			 {"windChill"  =>"1", "dewPoint"   =>"1" } ); # Virtual Sensors
#
#			 
# Defined a TH sensor with sensid 3 but do not activate any virtual sensors
# for it, so only temp and humidity will be displayed
#$sensorData->addSensor( {"sensType" => "TH", "sensIds" => [3]}, {  } ); 
#$sensorData->addSensor( {"sensType" => "PR"}, {} );
#$sensorData->addSensor( {"sensType" => "WI"}, {} );                     # Plot unit is km/h
# No gust speed display in graphics and min/max for wind sensor
#$sensorData->addSensor( {"sensType"=>"WI", "omit"=>["gustspeed"]}, {} ); 
# No gust speed display in graphics and statistics output for wind sensor
#$sensorData->addSensor( {"sensType"=>"WI", "omit"=>["gustspeed", "statgustspeed"]}, {} );


#$sensorData->addSensor( {"sensType" => "WI", "windSpeedType"=>1}, {} ); # Plot unit is kts
#$sensorData->addSensor( {"sensType" => "WI"}, {} );
#$sensorData->addSensor( {"sensType" => "RA"}, {} );
#$sensorData->addSensor( {"sensType" => "WD"}, {} );
#$sensorData->addSensor( {"sensType" => "WD", "omit"=>["gustspeed"]}, {} );
#$sensorData->addSensor( {"sensType" => "WA"}, {} );
# A light sensor with sensor Id 50
#$sensorData->addSensor( {"sensType" => "LI","sensIds"=>[50]}}, {} );
#$sensorData->addSensor( {"sensType"=>"LD", "sensIds"=>[50]}, {} );
#
# Davis Vantage Pro 2 Radiation and UVindex sensors:
#$sensorData->addSensor( {"sensType"=>"LR"}, {} );
#$sensorData->addSensor( {"sensType"=>"LU", "stationIdList"=>[1,5] }, {} );


# ==================== Optinal configs ============================
$position="Standort: Koblenz Lay, 125m &uuml;ber NN.\n";
$pageTitle="Wetterdaten aus Koblenz";
$pageAuthors='krienke@uni-koblenz.de,tdressler@tdressler.net,joerg@alcatraz.shacknet.nu,philip.marien@pandora.be';
$pageDescription="linux ws2500 based weather data display";
# Your contact address
$contact='Kontakt: Mr. X <A href="mailto:mrx@y.de">mrx@y.de</A>';
$pageMetaKeywords="wetter, Koblenz";
$pageBackgroundPicture="sky.jpg";
$pageBackgroundColor="#F0F8FF";
$pageTextColor="#000000";
$pageLinkColor="red";
$pageVisitedLinkColor="blue";
# Gnuplot background colors for graphics
$bgColorNormal="xEAF0FF";
$bgColorAverage="xE3e8F8";
# DST config, values are set by checkDst()  no need to change this
$dstStart="2004-03-29 02:00:00";  # When dst starts
$deltaIsDst=2;			  # Difference in h from GMT->DST time
$dstEnd="2004-10-31 03:00:00";	  # When DST ends
$deltaNoDst=1;			  # Difference in h from GMT-> localtime

# Some queries may be optimized by using SQL subqueries. Subqueries are 
# available since MYSQL Server Version 4.1. They seem to work really
# efficiently starting with MYSQL 5.0
# The variable below determines if the script should use subqueries 
# for MMA determination. Usually this variable is set automatically
# to 0 or 1 depending on the MYSQL server version. If this is > 5.0 it 
# is set to 1 else to 0. You can however overwrite this automatic here by 
# manually setting this variable to either 0 or 1.  
# If you want to use the automatic 
# setting put a comment sign (#) at the beginning of the line.
# Note: You need at leaset MYSQL version 4.1 if you want to use subqueries
# else you will see SQL errors.
# $useSqlSubQueries=1;


# *** You can copy all the variables between START CONFIG and END CONFIG
# *** into a file that can be reached by your web-server unter the path
# *** given below in $configpath. $configPath is set to the value of the 
# *** scriptname (eg wetter.cgi) with ".conf" appended. The scriptname
# *** and path are retrieved from the webservers environment variable
# *** named SCRIPT_FILENAME. apache on linux does provide this variable.
# *** If the given file exists and is readable
# *** the scripts config will be read from there overriding the variables
# *** set above. So  then you do not have to modify
# *** further entries in the script itself e.g. for new versions.
# *** Take care that your config file contains a valid perl-script if
# *** unsure use perl -c wetter.cgi.conf to check the syntax, because
# *** running wetter.cgi you won't see an error if your config file is
# *** wrong!!!!! You will just see, that wetter.cgi is not showing any
# *** output.
# *** Please take care that your config file is readable only by you and your
# *** web server but not to anyone else!
# *** If this method fails you can still hard code a value for
# *** $configPath in the last else-branch of the if staement.
# R.K. 
#
$scriptBasename=`basename $0`;
chomp($scriptBasename);
if( defined($ENV{"SCRIPT_FILENAME"}) && -r $ENV{"SCRIPT_FILENAME"} ){
	$configPath=$ENV{"SCRIPT_FILENAME"}. ".conf";
}elsif( defined($ENV{"SCRIPT_NAME"}) && -r $ENV{"SCRIPT_NAME"} ){
	$configPath=$ENV{"SCRIPT_NAME"} . ".conf";
}else{
	if( -r "${scriptBasename}.conf" ){
		$configPath="${scriptBasename}.conf"
	}elsif(-r "/etc/ws2500/wetter.cgi.conf" ){
		$configPath="/etc/ws2500/wetter.cgi.conf";
	}else{
		$configPath="/home/krienke/wetter/wetter.cgi.conf"
	}
}
#
# -------- END CONFIG VARIABLES ---------------------------------------------
#

$kmhToKnots=0.5399568;  # Don't change! $knot= $x "km/h" * $kmhToKnots
$preHtmlDocInit=1;  # Marks that we did not yet print the http header
#
# Set signal handler for text output of die 's and warn's
# By doing this we can see errors and warnings in the webbrowser
$SIG{__DIE__}=\&doDie;
$SIG{__WARN__}=\&doWarn;

# Print messages possibly preceded by a http header
sub doDieWarnPrint{
  my($text)=shift;

  if( $preHtmlDocInit ){
  	print "Content-Type: text/html\n\n";
  }
  print "$text";
}

# Do a die
sub doDie{
  my($text)=@_;

  doDieWarnPrint($text);
  exit(1);
}

# Do a warn
sub doWarn{
  my($text)=@_;

  doDieWarnPrint($text);
}


#
# Check if imgPath is writeble for us
#
sub imgpathWriteTest{
     my($uid, @tmp);
     
    $uid=$<;
    @tmp=getpwuid($uid);
    
    if( ! -w "$imgPath/." ){
        die "Error:<br>\n",
	"Cannot write into directory \"$imgPath\" <br>\n",
	"as user \"$tmp[0]\" (UID: $uid).<br>",
	"Write access to this directory is needed by gnuplot to temporarily store <br>\n",
	"image files representing the weather graphics. <br>\n",
	"Please change the owner of this directory or change the permissions <br>\n",
	"so that the user \"$tmp[0]\" (UID: $uid) has permissions to create/read/write files in this directory. <br>\n"; 
    }
}


#
# Now read configuration for script if existant
#
$cmd="";
if( -r "$configPath" ){
   open( FD, "$configPath" )|| warn "Cannot read \"$configPath\". Ignored\n";
   while( <FD> ){
	$cmd.=$_;
        if( length($cmd) > 100000 ){
           $cmd="";
           die "Too many commands in config file (>100000bytes.  Aborting.\n";
        }
   }
   eval $cmd;
   $cmd="";
   close(FD);
}


# Determine own script URL and remove every CGI parameter from it
$scriptUrl=self_url();
$scriptUrl=~s/\.cgi.*$/\.cgi/;


# Find gnuplot
if( -x "/usr/bin/gnuplot" ){
	$gnuplot="/usr/bin/gnuplot";
}elsif( -x "/usr/local/bin/gnuplot" ){
	$gnuplot="/usr/local/bin/gnuplot";
}

#
# Check gnuplot version, because different version
# need different config statements in writeGnuplotHeader()
#
$tmp=`/bin/bash -c 'echo "show version"|$gnuplot 2>&1'`;
if( $tmp =~ /[vV]ersion 4\.2/ ){
        $gnuplotVers="4.2";
}elsif( $tmp =~ /[vV]ersion 4\.4/ ){
	$gnuplotVers="4.4"
}elsif( $tmp =~ /[vV]ersion 4\.0/ ){
        $gnuplotVers="4";
}elsif( $tmp =~ /[vV]ersion 3\.[89]/ ){
        $gnuplotVers="4";
}elsif( $tmp =~ /[vV]ersion 3\.[7654321]/ ){
        $gnuplotVers="3";
}else{
   $gnuplotVers=0;
}
# Terminate if we cannot get gnuplot version
if( $gnuplotVers == 0 ){
   die "Cannot determine version of gnuplot. Please verify your gnuplot installation.\n";
}


#
# Print Environment for testing purposes
#
sub printenv{
   my($i);
   foreach $i (keys(%ENV)){
   	warn "*** $i: $ENV{$i} \n";
	#warn '$ENV{', "$i", '}=\'', $ENV{$i}, "\';\n";
   }
}


#
# round a value to n decimals 
#
sub round{
   my($value)=shift;  # Value to be rounded
   my($num)=shift;    # number of decimals right of "."
   my($arity)=10**$num;
   
   if( $value >= 0 ){
      return( int($value*$arity + 0.5)/$arity );
   }else{
      return( int($value*$arity - 0.5)/$arity );
   }
}

#
# Find out which version the MYSQL-Server has
#
sub getMysqlVersion{
   my($dbh)=shift;
   my($sql, $sth);
   
   $sql="SELECT VERSION()";
   $sth=$dbh->prepare($sql);
   $sth->execute();

   return(($sth->fetchrow_array())[0]);
}


#
# Function to create a SQL statement that converts GMT to Local time in a 
# SELECT query. The result is only the conversion without a SELECT
#
sub sqlGmtToLoc{
   my($startDate)=shift;
   my($endDate)=shift;
   my($tableName)=shift;
   my($dstRange)=shift;  # dstData actually set in main::
   my($defaultTime)=shift;
   my($deltaIsDst, $deltaNoDst, $tmp, $i, $startYear,$endYear, 
      $sqlDateZone, $sqlDateZone1); 
   
   
   # SQL statement that converts GMT time to local time given the start and end 
   # time as well as the time differene values in hours 
   # eg from GMT-> MEZ  and  GMT-> MESZ
   # since a select statement might result in output of several year we have to 
   # check for each year of possible output if the dateentry of the row is in DST or NOT
   # For this we generate a local statement that looks like
   # (2003-20-03 < currDate < 2003-10-31) ||(2002-20-03 < currDate < 2002-10-31) ...
   # This is a bad hack but hopefully MSQL will provide DST date calculations someday.
   # Only do this if local times are required, otherwise probably reduces MySQL performance
   # The result is eg:
   # if((th_sensors.datetime between "2005-03-27 02:00:00" AND "2005-10-30 03:00:00") 
   # OR (th_sensors.datetime between "2006-03-26 02:00:00" AND "2006-10-29 03:00:00"),
   # DATE_FORMAT(DATE_ADD(th_sensors.datetime, INTERVAl HOUR), "%Y-%m-%d\t00:00:00"),
   # DATE_FORMAT(DATE_ADD(th_sensors.datetime, INTERVAL HOUR), "%Y-%m-%d\t00:00:00")) 
   #
   if (!$timeIsGMT) {
	$startYear=(split(/-/o,$startDate))[0];  # Year of startdate
	$endYear=(split(/-/o,$endDate))[0];
        
	$tmp="";
        $deltaIsDst=$dstRange->{$startYear}->{"deltaIsDst"};
        $deltaNoDst=$dstRange->{$startYear}->{"deltaNoDst"};

	for($i=$startYear; $i<=$endYear; $i++){
	     $tmp.=" OR " if( $i>$startYear );
   	     $tmp.= "($tableName.datetime between \"" . $dstRange{$i}->{"dstStart"} . "\" AND \"" . 
	        	$dstRange{$i}->{"dstEnd"} . "\")";
	}
	$sqlDateZone=" if($tmp,";
	# this adds the timeoffset to the datetime field in each row:
	$sqlDateZone.="DATE_FORMAT(DATE_ADD($tableName.datetime, INTERVAl $deltaIsDst HOUR), \"%Y-%m-%d\\t$defaultTime\"),";
	$sqlDateZone.="DATE_FORMAT(DATE_ADD($tableName.datetime, INTERVAL $deltaNoDst HOUR), \"%Y-%m-%d\\t$defaultTime\")) ";
   } else {
  	$sqlDateZone.="DATE_FORMAT($tableName.datetime, \"%Y-%m-%d\\t$defaultTime\")";
   }
   # sqlDateZone1 is like $sqlDateZone but no $defaultTime instead the real rows date
   # sqlDateZone1 is used for normal display, sqlDateZone for
   # the case where $sampleTime != 0 
   # The difference is be important because with sqlDateZone one can group by  loctime
   # to get day statistics. in case of sqldatezone1 one would have to group by
   # left(loctime,10) (== the date part) but this is not allowed by SQL one can only group by 
   # left(datetime,10) but this causes trouble since datetime is in GMT and for correct day by day
   # grouping we need to group by local time. 
   $sqlDateZone1=$sqlDateZone;
   $sqlDateZone1=~s/\\t$defaultTime/\\t%T/g;
   
   return($sqlDateZone, $sqlDateZone1);
}


# 
# Map internally used type names for sensors to 
# the names used in the database in sensor_descr
#
sub mapTypeName2DbName{
   my($type)=shift;
   my($dbType);
   
   if   ( $type =~/TH$|temp/io ){ $dbType="th"; }
   elsif( $type =~/WI$|WD$|WA$|wind/io ){ $dbType="wind"; }
   elsif( $type =~/RA$|rain/io ){ $dbType="rain"; }
   elsif( $type =~/LI$|light|sundur|LD$/io ){ $dbType="light"; }
   elsif( $type =~/radiation|LR$/io ){ $dbType="radiation"; }
   elsif( $type =~/uvindex|LU$/io ){ $dbType="uvindex"; }
   elsif( $type =~/PR$|pressure/io ){ $dbType="pressure"; }
   else{
      warn "getSensorNames(): Unkon sensortype: \"$type\". Skipped <br>\n";
      return(undef);
   }
   
   return($dbType);
}


# --------------------------------------------------------------------------
# Class virtSens
# Class that contains all calculation functions for virtual sensors defined
# in class sensDisplayData
# Here only the calculation function itself is stored
#
package virtSens;


#
# Function for a virtual sensor i.e. a sonsor that takes some basic values that are measured
# and then calculates a new virtual sensor value from these data. An example is 
# this virtual Sensor for windchillCalculation.
# The input is a hash with all database cols as described in the set*defaults hashes defined
# above in the "virtSensor"-section. The structure of this data hash containing the result
# of the database query for the specified db cols is as described in DBI::selectall_hashref()
# its a hash where the key is the datetime col named loctime for each row found. The value is
# a reference to a hash with the other db col values for the current row.
#
sub doWindChill{
   my($self)=shift;
   my($virtSensName)=shift; # Name of the virtual Sensor
   my($refSensor)=shift;    # Reference to sensor description hash defined in set*defaults()
   my($refResult)=shift;    # Hash with result cols from database query (->input data)
   my($refMma)=shift;	    # Results for MMA calculations
   my($calcMma)=shift;	    # Do mma calculations or not
   my($i, $j, @h, $virtSens, $virtOutName);
   my($min, $max, $avg, $date, $time);
   my($refInSpeedName, $inSpeedName);
   
   
   # The argument has the format eg "1;0;1" for Min, Max, Avg 
   # All we want to know here is weather we have to calculate any of Min /Max Avg or not.
   # If any of Min/Max/Avg is wanted we calculate them all.
   if( $calcMma =~ /1/o ){
   	$calcMma=1;
   }else{
   	$calcMma=0;
   }
   
   # Find the Name of the output (result) col for this virtual sensor
   $virtSens=$self->getVirtSensors($refSensor);
   @h=keys(%{$virtSens->{"$virtSensName"}->{"out"}});

   $refInSpeedName=$virtSens->{"$virtSensName"}->{"in"}->{"wind"};
   $inSpeedName=$refInSpeedName->[0];

   # Windchill has only one output value, the windchill value
   $virtOutName=$h[0]; 
     
   $j=1; $avg=0;
   for($i=0; $i<= $#{$refResult}; $i++){
	$refResult->["$i"]->{"$virtOutName"} =
	       main::doWindChill($refResult->[$i]->{"T"}, 
	                         $refResult->[$i]->{$inSpeedName},
				 $refSensor->{"windSpeedType"} );
	
	if( $calcMma ){	
	   # Calculate Min/Max/Average Values
	   if( $j > 1){
	      $avg+=$refResult->["$i"]->{"$virtOutName"};
 	      if( $max < $refResult->["$i"]->{"$virtOutName"} ){
	         $max=$refResult->["$i"]->{"$virtOutName"};
		 ($date, $time)=split(/\t/o, $refResult->["$i"]->{"loctime"});
		 $refMma->{"$virtOutName"}->{"maxDate"}=$date;
		 $refMma->{"$virtOutName"}->{"maxTime"}=$time;
	      }
 	      if( $min > $refResult->["$i"]->{"$virtOutName"} ){
	         $min=$refResult->["$i"]->{"$virtOutName"};
		 ($date, $time)=split(/\t/o, $refResult->["$i"]->{"loctime"});
		 $refMma->{"$virtOutName"}->{"minDate"}=$date;
		 $refMma->{"$virtOutName"}->{"minTime"}=$time;
	      }
	      $j++;
	   }else{
	      $avg=$refResult->["$i"]->{"$virtOutName"};
	      $min=$max=$refResult->["$i"]->{"$virtOutName"};
              #
              ($date, $time)=split(/\t/o, $refResult->["$i"]->{"loctime"});
              $refMma->{"$virtOutName"}->{"maxDate"}=$date;
              $refMma->{"$virtOutName"}->{"maxTime"}=$time;
              #
              $refMma->{"$virtOutName"}->{"minDate"}=$date;
              $refMma->{"$virtOutName"}->{"minTime"}=$time;
   	      $j++;
	   }
	}
	#print "$i, $min, $max, ", keys(%{$refResult->[$i]}), "\n";
   }
  
   # Determine average value for virtual sensor and store min and max 
   if( $calcMma ){
      $refMma->{"$virtOutName"}->{"avgValue"}=main::round($avg/$j, 2);
      $refMma->{"$virtOutName"}->{"maxValue"}=$max;
      $refMma->{"$virtOutName"}->{"minValue"}=$min;
   }

   
   # Return reference to result hash
   return($refResult);
}


#
# calculate Absolute Humidity
#
sub doAbsHumidity{
   my($self)=shift;
   my($virtSensName)=shift; # Name of the virtual Sensor
   my($refSensor)=shift;    # Reference to sensor description hash defined in set*defaults()
   my($refResult)=shift;    # Hash with result cols from database query (->input data)
   my($refMma)=shift;	    # Results for MMA calculations
   my($calcMma)=shift;	    # Do mma calculations or not
   my($i, $j, @h, $virtSens, $virtOutName);
   my($min, $max, $avg, $date, $time);
   
   
   # The argument has the format eg "1;0;1" for Min, Max, Avg 
   # All we want to know here is weather we have to calculate any of Min /Max Avg or not.
   # If any of Min/Max/Avg is wanted we calculate them all.
   if( $calcMma =~ /1/o ){
   	$calcMma=1;
   }else{
   	$calcMma=0;
   }
   
   # Find the Name of the output (result) col for this virtual sensor
   $virtSens=$self->getVirtSensors($refSensor);
   @h=keys(%{$virtSens->{"$virtSensName"}->{"out"}});

   # absHimidity has only one output value, the humidity value
   $virtOutName=$h[0]; 
     
   $j=1; $avg=0;
   for($i=0; $i<= $#{$refResult}; $i++){
	$refResult->["$i"]->{"$virtOutName"} =
	       main::doAbsHumidity($refResult->[$i]->{"T"}, $refResult->[$i]->{"H"} );
	
	if( $calcMma ){	
	   # Calculate Min/Max/Average Values
	   if( $j > 1){
	      $avg+=$refResult->["$i"]->{"$virtOutName"};
 	      if( $max < $refResult->["$i"]->{"$virtOutName"} ){
	         $max=$refResult->["$i"]->{"$virtOutName"};
		 ($date, $time)=split(/\t/o, $refResult->["$i"]->{"loctime"});
		 $refMma->{"$virtOutName"}->{"maxDate"}=$date;
		 $refMma->{"$virtOutName"}->{"maxTime"}=$time;
	      }
 	      if( $min > $refResult->["$i"]->{"$virtOutName"} ){
	         $min=$refResult->["$i"]->{"$virtOutName"};
		 ($date, $time)=split(/\t/o, $refResult->["$i"]->{"loctime"});
		 $refMma->{"$virtOutName"}->{"minDate"}=$date;
		 $refMma->{"$virtOutName"}->{"minTime"}=$time;
	      }
	      $j++;
	   }else{
	      $avg=$refResult->["$i"]->{"$virtOutName"};
	      $min=$max=$refResult->["$i"]->{"$virtOutName"};
              #
              ($date, $time)=split(/\t/o, $refResult->["$i"]->{"loctime"});
              $refMma->{"$virtOutName"}->{"maxDate"}=$date;
              $refMma->{"$virtOutName"}->{"maxTime"}=$time;
              #
              $refMma->{"$virtOutName"}->{"minDate"}=$date;
              $refMma->{"$virtOutName"}->{"minTime"}=$time;
   	      $j++;
	   }
	}
	#print "$i, $min, $max, ", keys(%{$refResult->[$i]}), "\n";
   }
  
   # Determine average value for virtual sensor and store min and max 
   if( $calcMma ){
      $refMma->{"$virtOutName"}->{"avgValue"}=main::round($avg/$j, 2);
      $refMma->{"$virtOutName"}->{"maxValue"}=$max;
      $refMma->{"$virtOutName"}->{"minValue"}=$min;
   }

   
   # Return reference to result hash
   return($refResult);
}


#
# calculate Absolute Humidity
#
sub doDewPoint{
   my($self)=shift;
   my($virtSensName)=shift; # Name of the virtual Sensor
   my($refSensor)=shift;    # Reference to sensor description hash defined in set*defaults()
   my($refResult)=shift;    # Hash with result cols from database query (->input data)
   my($refMma)=shift;	    # Results for MMA calculations
   my($calcMma)=shift;	    # Do mma calculations or not
   my($i, $j, @h, $virtSens, $virtOutName);
   my($min, $max, $avg, $date, $time);
   
   
   # The argument has the format eg "1;0;1" for Min, Max, Avg 
   # All we want to know here is weather we have to calculate any of Min /Max Avg or not.
   # If any of Min/Max/Avg is wanted we calculate them all.
   if( $calcMma =~ /1/o ){
   	$calcMma=1;
   }else{
   	$calcMma=0;
   }
   
   # Find the Name of the output (result) col for this virtual sensor
   $virtSens=$self->getVirtSensors($refSensor);
   @h=keys(%{$virtSens->{"$virtSensName"}->{"out"}});

   # absHimidity has only one output value, the humidity value
   $virtOutName=$h[0]; 
     
   $j=1; $avg=0;
   for($i=0; $i<= $#{$refResult}; $i++){
	$refResult->["$i"]->{"$virtOutName"} =
	       main::doDewPoint($refResult->[$i]->{"T"}, $refResult->[$i]->{"H"} );
	
	if( $calcMma ){	
	   # Calculate Min/Max/Average Values
	   if( $j > 1){
	      $avg+=$refResult->["$i"]->{"$virtOutName"};
 	      if( $max < $refResult->["$i"]->{"$virtOutName"} ){
	         $max=$refResult->["$i"]->{"$virtOutName"};
		 ($date, $time)=split(/\t/o, $refResult->["$i"]->{"loctime"});
		 $refMma->{"$virtOutName"}->{"maxDate"}=$date;
		 $refMma->{"$virtOutName"}->{"maxTime"}=$time;
	      }
 	      if( $min > $refResult->["$i"]->{"$virtOutName"} ){
	         $min=$refResult->["$i"]->{"$virtOutName"};
		 ($date, $time)=split(/\t/o, $refResult->["$i"]->{"loctime"});
		 $refMma->{"$virtOutName"}->{"minDate"}=$date;
		 $refMma->{"$virtOutName"}->{"minTime"}=$time;
	      }
	      $j++;
	   }else{
	      $avg=$refResult->["$i"]->{"$virtOutName"};
	      $min=$max=$refResult->["$i"]->{"$virtOutName"};
              #
              ($date, $time)=split(/\t/o, $refResult->["$i"]->{"loctime"});
              $refMma->{"$virtOutName"}->{"maxDate"}=$date;
              $refMma->{"$virtOutName"}->{"maxTime"}=$time;
              #
              $refMma->{"$virtOutName"}->{"minDate"}=$date;
              $refMma->{"$virtOutName"}->{"minTime"}=$time;

   	      $j++;
	   }
	}
	#print "$i, $min, $max, ", keys(%{$refResult->[$i]}), "\n";
   }
  
   # Determine average value for virtual sensor and store min and max 
   if( $calcMma ){
      $refMma->{"$virtOutName"}->{"avgValue"}=main::round($avg/$j,2);
      $refMma->{"$virtOutName"}->{"maxValue"}=$max;
      $refMma->{"$virtOutName"}->{"minValue"}=$min;
   }

   
   # Return reference to result hash
   return($refResult);
}



# --------------------------------------------------------------------------
# Class sensDisplayData 
# Class that manages the data of all sensors to be displayed including
# their sequence in graphical display
# --------------------------------------------------------------------------
package sensDisplayData;

#
# constructor of sensDisplaydata
#
sub new{
        my ($class) = shift;
        my ($self) = {};
	my ($imgPath, $imgUrl, $tmp)=@_;
        my ($ret);
        bless $self, $class;
	
	#$self->{"sensors"}=[];    # Anononymous array holds all sensor data
	$self->{"sensorCount"}=0; # Number of sensors in list
	$self->{"currentSensor"}=0;
	$self->{"typeSerial"}={}; # Serial number of sensor type: 0,1,2...
	$self->{"configIds"}={};  # unique config Ids
	$self->{"imgPath"}=$imgPath;
	$self->{"imgUrl"}=$imgUrl;
	$self->{"tmpName"}=$tmp;
		
	return($self);
}


#
# Set some global Defaults for all sensors
# May be overwritten in setXXdefaults() or in any call to addSensor()
#
sub setGlobalDefaults{
   my ($self) = shift;
   my ($global)={
   	"xSmallScale" => "0.5",		# Scaling for graphics in overview
	"ySmallScale" => "0.5",
   	"xNormalScale" => "1.1",	# Scaling for graphics of one sensor
	"yNormalScale" => "1.1",
	"xCanvas"     =>  "640",
	"yCanvas"     =>  "480",
   };
   return($global);
}


#
# Method for settings defaults values for a particular sensor display type
# Returns *Reference* to data hash
#
sub setTHdefaults{
   my ($self) = shift;
   my( $virt);
   
   my ($sensor)={
	# General info fpr plot-routine
	"sensType"	=> "TH",	
	"doPlot"	=> "1",			# USER: plot yes/no
	"sensIds"	=> [1],			# USER: sensor IDs to display
	"stationId"     => $main::defaultStationId,
	"stationIdList" => $main::defaultStationIdList, # a reference to a list of stationIds allowed
	"configId"     => "0",                  # re-set in addSensors()
	"dbCols"	=> ["datetime", "T", "H"],
	"valCols"	=> [3, 4],
	"grfxName"	=> "Temperatur/Feuchte",# USER: Headname of graphics
	"valNames"	=> ["Temp", "Feuchte"],  
	"valUnits"	=> ["\260C", "%"],		# USER: Unit names of values
	"plotFormat"	=> ["with lines"],
	"imgName"	=> "th".$self->{"tmpName"},
	#"userImgName"  => "myImgName",  	# if you want to name the graphics file like 
						# you want. Do it only if you know what you are doing
	#					
	#"omit"          => ["T"],		# USER: Do not use these column(s) 
						# Useful if just one of T, H should be 
						# drawn but not both 
	
	# More Infos for calcMinMaxAv routine
	"tableName"	=> "th_sensors",	
	"mmaNames"	=> [ "Temp", "Feuchte" ],
	"mmaDBCol"	=> ["T", "H"],
	"mmaUnits"      => ["&deg;C", "%"],
	"mmaHasMin"	=> "1", 	# USER: Senors value has a minumim; see printmma
	#"mmaOmit"       => ["T"],	# USER: Omit this column(s) in MMA output
	
	# Other stuff
	"displayMMA"	=> "1",			# USER: Display for MMA on/off
	"graphics"      => "1",                 # show in graphics by default
	"statistics"    => "1",                 # show in statistics by default
   };

   # Define Filter (virtual sensors) for displaying data that is calculated
   # from the original data
   # Input data: Tablename-> Colname
   # ~~~ Virtual sensor Windchill ~~~~  
   $virt->{"windChill"}->{"in"}->{"th_sensors"} =	["T"];
   $virt->{"windChill"}->{"in"}->{"wind"}	=	["speed"];
   
   # Now define Name and Unit for extra input columns i.e those that are needed
   # by the virtual sensor and not part of the sensor for which the virtual sensor 
   # is defined. These values are used in textual output of sensor data.
   $virt->{"windChill"}->{"inUnit"}->{"wind"} = "km/h";  # Unit for extra input column
   $virt->{"windChill"}->{"inName"}->{"wind"} = "Wind";  # Name for extra input column
   
   # Output data: Valuename -> Unit
   # Multiple output colums have to be named differently
   # !!! The name may not contain a dot "." character !!!
   $virt->{"windChill"}->{"out"}->{"Windchill"}	=	"\260C";
   
   # If wanted select plot format for output value. Else a default will be used
   #$virt->{"windChill"}->{"plotFormat"}->{"Windchill"}="with linespoints";
   
   # The new virt sensor might replace a real sonsor val by his own one.
   # "omit" may contain datase attributes (from dbCols above) that are
   # omitted i.e. not displayed. In the example below the T value from the
   # virt sensor would replace the T-value from dbCols above.
   #$virt->{"windChill"}->{"omit"}->{"th_sensors"} =	["H"];
   
   # Function name for calculation of filter value
   # Function is called in package g::applyVirtSensors()
   $virt->{"windChill"}->{"function"}		=	"virtSens::doWindChill";
   $virt->{"windChill"}->{"active"}		=	"0";
   $virt->{"windChill"}->{"doCalcMma"}		=	"1";  # Do calculate MMAs
   
   # Textual print MMA values. 1 means print them in one sensor display
   # 2 means print them in both overview and one sensor display
   # 0 means don't display them   
   $virt->{"windChill"}->{"doPrintMma"}		=	"1";  
   $virt->{"windChill"}->{"doPlotMma"}		=	"0;0;0"; # graphical plot them?


   # ~~~ Virtual sensor Absolute Humidity ~~~~  
   $virt->{"absHumidity"}->{"in"}->{"th_sensors"} =	["T", "H"];

   # Output data: Valuename -> Unit
   # Multiple output colums have to be named differently
   # !!! The name may not contain a dot "." character !!!
   $virt->{"absHumidity"}->{"out"}->{"Abs-Feuchte"}	=	"g/m*3";

   # If wanted select plot format for output value. Else a default will be used
   #$virt->{"absHumidity"}->{"plotFormat"}->{"Abs-Feuchte"}="with linespoints";

   # The new virt sensor might replace a real sonsor val by his own one.
   # "omit" may contain datase attributes (from dbCols above) that are
   # omitted i.e. not displayed. In the example below the T value from the
   # virt sensor would replace the T-value from dbCols above.
   #$virt->{"absHumidity"}->{"omit"}->{"th_sensors"} =	["H"];

   # Function name for calculation of filter value
   # Function is called in package dataManager::applyVirtSensors()
   $virt->{"absHumidity"}->{"function"}		=	"virtSens::doAbsHumidity";
   $virt->{"absHumidity"}->{"active"}		=	"0";
   $virt->{"absHumidity"}->{"doCalcMma"}		="1";

   # Textual print MMA values. 1 means print them in one sensor display
   # 2 means print them in both overview and one sensor display
   # 0 means don't display them   
   $virt->{"absHumidity"}->{"doPrintMma"}		="1";  # Textual print them ?
   $virt->{"absHumidity"}->{"doPlotMma"}		="0;0;0";


   # ~~~ Virtual sensor Dew Point ~~~~  
   $virt->{"dewPoint"}->{"in"}->{"th_sensors"} =	["T", "H"];

   # Output data: Valuename -> Unit
   # Multiple output colums have to be named differently
   # !!! The name may not contain a dot "." character !!!
   $virt->{"dewPoint"}->{"out"}->{"Taupunkt"}	=	"\260C";

   # If wanted select plot format for output value. Else a default will be used
   #$virt->{"dewPoint"}->{"plotFormat"}->{"Taupunkt"}="with linespoints";

   # The new virt sensor might replace a real sonsor val by his own one.
   # "omit" may contain datase attributes (from dbCols above) that are
   # omitted i.e. not displayed. In the example below the T value from the
   # virt sensor would replace the T-value from dbCols above.
   #$virt->{"dewPoint"}->{"omit"}->{"th_sensors"} =	["H"];

   # Function name for calculation of filter value
   # Function is called in package dataManager::applyVirtSensors()
   $virt->{"dewPoint"}->{"function"}		=	"virtSens::doDewPoint";
   $virt->{"dewPoint"}->{"active"}		=	"0";
   $virt->{"dewPoint"}->{"doCalcMma"}		=	"1";

   # Textual print MMA values. 1 means print them in one sensor display
   # 2 means print them in both overview and one sensor display
   # 0 means don't display them   
   $virt->{"dewPoint"}->{"doPrintMma"}		=	"1";  # Textual print them ?
   $virt->{"dewPoint"}->{"doPlotMma"}		=	"0;0;0";
   
   
   # Enter virtSens data into sensor data hash.
   $sensor->{"virtSens"}=$virt;
   return($sensor);
}


#
# Method for settings defaults values for a particular sensor display type
# Returns *Reference* to data hash
#
sub setPRdefaults{
   my ($self) = shift;
   my ($sensor)={
	# General info fpr plot-routine
	"sensType"	=> "PR",
	"doPlot"	=> "1",
	"sensIds"	=> [1],
	"stationId"     => $main::defaultStationId, 
	"stationIdList" => $main::defaultStationIdList, # a reference to a list of stationIds allowed
	"configId"     => "20",
	"dbCols"	=> ["datetime", "P"],
	"valCols"	=> [3],
	"valNames"	=> ["Luftdr, rel"],
	"grfxName"	=> "Luftdruck",
	"valUnits"	=> ["hPa"],
	"plotFormat"	=> ["with lines"],
	"imgName"	=> "pr".$self->{"tmpName"},
	
	# More Infos for calcMinMaxAv routine
	"tableName"	=> "pressure",	
	"mmaNames"	=> [ "Druck"],
	"mmaDBCol"	=> ["P"],
	"mmaUnits"      => ["hPa"],
	"mmaHasMin"	=> "1", 	# Senors value has a minumim; see printmma
	"mmaHeight"	=> "80",	# Height of mma table output. Needed to 
					# create a balanced optics for one table
					# row.	
	# Other stuff
	"displayMMA"	=> "1",
	"graphics"      => "1",                 # show in graphics by default
	"statistics"    => "1",                 # show in statistics by default
	
   };
   
   return($sensor);
}

#
# Method for settings defaults values for a particular sensor display type
# Returns *Reference* to data hash
#
sub setWIdefaults{
my ($self) = shift;
my ($sensor)={
	# General info fpr plot-routine
	"sensType"	=> "WI",
	"doPlot"	=> "1",
	"sensIds"	=> [1],
	"stationId"     => $main::defaultStationId, 
	"stationIdList" => $main::defaultStationIdList, # a reference to a list of stationIds allowed
	"configId"     => "30",
	"dbCols"	=> ["datetime", "gustspeed", "speed"],
	"valCols"	=> [3,4],
	"grfxName"	=> "Windgeschwindigkeit",
	"valNames"	=> ["B\366en", "Wind" ],
	"valUnits"	=> ["Km/h", "Km/h"],
	"plotFormat"	=> ["with impulses"],
	"imgName"	=> "wi".$self->{"tmpName"},
	
	# More Infos for calcMinMaxAv routine
	"tableName"	=> "wind",	
	"mmaNames"	=> [ "Boeen", "Wind"],
	"mmaDBCol"	=> ["gustspeed", "speed"],
	"mmaUnits"      => ["Km/h", "Km/h" ],
	"mmaHasMin"	=> "0", 	# Senors value has a minumim; see printmma
	
	# Other stuff
	"displayMMA"	=> "1",
	"graphics"      => "1",                 # show in graphics by default
	"statistics"    => "1",                 # show in statistics by default
	
   };
      
   return($sensor);
}

#
# Method for settings defaults values for a particular sensor display type
# Returns *Reference* to data hash
#
sub setWDdefaults{
my ($self) = shift;
my ($sensor)={
	# General info fpr plot-routine
	"sensType"	=> "WD",
	"doPlot"	=> "1",
	"sensIds"	=> [1],   # HERE: only one wind sensor allowed
	"stationId"     => $main::defaultStationId, 
	"stationIdList" => $main::defaultStationIdList, # a reference to a list of stationIds allowed
        "configId"     => "130",
	"dbCols"	=> ["datetime", "speed", "angle", "gustspeed", "gustangle"],
	# The columns in the gnuplot data file. The first two columns 
	# are always date and time. The third col ist the first real data column
	# This value is actually only needed in  writeGnuplotCmds() for WD sensor type
	"valCols"	=> [3, 4, 5, 6],
	"grfxName"	=> "Windgeschwindigkeiten/Richtungen",
	"legendName"     => "Wind", # Name for legend 
	"valNames"	=> ["Geschwindigkeit", "Winkel", "B&ouml;en", "Winkel"],
	"valUnits"	=> ["Km/h", "&deg;", "Km/h", "&deg;"],
	"imgName"	=> "wd".$self->{"tmpName"},
   	"xNormalScale" => "1.0",	# Scaling for graphics of one sensor
	"yNormalScale" => "1.0",	
	# More Infos for calcMinMaxAv routine
	"tableName"	=> "wind",	
	"mmaNames"	=> ["Wind", "B&ouml;en" ],
	"mmaDBCol"	=> ["speed", "gustspeed"],
	"mmaUnits"      => ["Km/h", "Km/h"],
	"mmaHasMin"	=> "0", 	# Senors value has a minumim; see printmma
	
	# Other stuff
	"displayMMA"	=> "1",
	"graphics"      => "1",                 # show in graphics by default
	"statistics"    => "0",                 # show in statistics by default
	
   };
   
   return($sensor);
}


#
# Method for settings defaults values for a particular sensor display type
# Returns *Reference* to data hash
#
sub setWAdefaults{
my ($self) = shift;
my ($sensor)={
	# General info fpr plot-routine
	"sensType"	=> "WA",
	"doPlot"	=> "1",
	"plotFormat"	=> ["with linespoints", "with linespoints"],
	"sensIds"	=> [1],   # HERE: only one wind sensor allowed
	"stationId"     => $main::defaultStationId, 
	"stationIdList" => $main::defaultStationIdList, # a reference to a list of stationIds allowed
	"configId"     => "135",
	
	"dbCols"	=> ["datetime", "angle", "range"],
	"valCols"	=> [3],
	"grfxName"	=> "Windrichtungen/Varianz",
	"legendName"     => "Wind", # Name for legend 
	"valNames"	=> ["Winkel", "Varianz"],
	"valUnits"	=> ["Grad", "Grad"],
	"imgName"	=> "wa".$self->{"tmpName"},
	
	# More Infos for calcMinMaxAv routine
	"tableName"	=> "wind",	
	"mmaNames"	=> ["Speed","Varianz"],
	"mmaDBCol"	=> ["speed", "range"],
	"mmaUnits"      => ["Km/h", "Grad"],
	"mmaHasMin"	=> "0", 	# Senors value has a minumim; see printmma
	
	# Other stuff
	"displayMMA"	=> "1",
	"graphics"      => "1",                 # show in graphics by default
	"statistics"    => "0",                 # show in statistics by default
	
   };   
   return($sensor);
}


#
# Method for settings defaults values for a particular sensor display type
# Returns *Reference* to data hash
#
sub setRAdefaults{
   my ($self) = shift;
   my ($sensor)={
	# General info fpr plot-routine
	"sensType"	=> "RA",
	"doPlot"	=> "1",
	"sensIds"	=> [1],
	"stationId"     => $main::defaultStationId, 
	"stationIdList" => $main::defaultStationIdList, # a reference to a list of stationIds allowed
	"configId"     => "40",
	"dbCols"	=> ["datetime", "diff"],
	"valCols"	=> [3],
	"grfxName"	=> "Regen",
	"valNames"	=> ["Regen"],
	"valUnits"	=> ["l/m*m"],
	"plotFormat"	=> ["with impulses"],
	"imgName"	=> "ra".$self->{"tmpName"},
	
	# More Infos for calcMinMaxAv routine
	"tableName"	=> "rain",	
	"mmaNames"	=> [ "Regen"],
	"mmaDBCol"	=> ["diff"],
	"mmaHasMin"	=> "0", 	# Senors value has a minumim; see printmma
	"mmaUnits"      => ["mm/h"],
	"unitfactor"	=> {"diff"=>"0.001"},
	"gettotal"	=> "1",
	"totalUnit"	=> "l/m*m",
	
	# Other stuff
	"lowYbounds"    => "0",
	"displayMMA"	=> "1",
	"graphics"      => "1",                 # show in graphics by default
	"statistics"    => "1",                 # show in statistics by default
	
   };
   
   return($sensor);
}

#
# Method for settings defaults values for a particular sensor display type
# Returns *Reference* to data hash
#
sub setLIdefaults{
   my ($self) = shift;
   my ($sensor)={
	# General info fpr plot-routine
	"sensType"	=> "LI",
	"doPlot"	=> "1",
	"sensIds"	=> [1],
	"stationId"     => $main::defaultStationId, 
	"stationIdList" => $main::defaultStationIdList, # a reference to a list of stationIds allowed
	"configId"     => "50",	
	"dbCols"	=> ["datetime", "lux", "factor"],
	"valCols"	=> [3],
	"grfxName"	=> "Licht",
	"valNames"	=> ["Licht"],
	"valUnits"	=> ["lux"],
	"plotFormat"	=> ["with impulses"],
	"imgName"	=> "li".$self->{"tmpName"},
	
	# More Infos for calcMinMaxAv routine
	"tableName"	=> "light",	
	"mmaNames"	=> [ "Licht"],
	"mmaDBCol"	=> ["lux*factor"],
	"mmaHasMin"	=> "0", 	# Senors value has a minumim; see printmma
	"mmaUnits"      => ["lux"],
	"factor"	=> "factor",
	
	# Other stuff
	"displayMMA"	=> "1",
	"graphics"      => "1",                 # show in graphics by default
	"statistics"    => "1",                 # show in statistics by default
   };
   
   return($sensor);
}

#
# Method for settings defaults values for a particular sensor display type
# Returns *Reference* to data hash
#
sub setLDdefaults{
   my ($self) = shift;
   my ($sensor)={
	# General info fpr plot-routine
	"sensType"	=> "LD",
	"doPlot"	=> "1",
	"sensIds"	=> [1],
	"stationId"     => $main::defaultStationId, 
	"stationIdList" => $main::defaultStationIdList, # a reference to a list of stationIds allowed
	"configId"     => "60",
	"dbCols"	=> ["datetime", "sundur"],
	"valCols"	=> [2],
	"grfxName"	=> "Sonnenscheindauer",
	"valNames"	=> ["Sonne"],
	"valUnits"	=> ["h"],
	"plotFormat"	=> ["with impulses"],
	"imgName"	=> "ld".$self->{"tmpName"},
	
	# More Infos for calcMinMaxAv routine
	"tableName"	=> "light",	
	"mmaNames"	=> [ "Sonnenscheindauer"],
	"mmaDBCol"	=> ["sundur"],
	"mmaHasMin"	=> "0", 	# Senors value has a minumim; see printmma
	"mmaUnits"      => ["h"],
	"unitfactor"	=> {"sundur"=>"0.0166667"}, # 1/60
	"gettotal"	=> "1",
	"totalUnit"	=> "h",
	
	# Other stuff
	"lowYbounds"    => "0",
	"displayMMA"	=> "1",
	"graphics"      => "1",                 # show in graphics by default
	"statistics"    => "1",                 # show in statistics by default
	
   };
   
   return($sensor);
}

#
# Method for settings defaults values for a particular sensor display type
# Returns *Reference* to data hash
#
sub setLRdefaults{
   my ($self) = shift;
   my ($sensor)={
	# General info fpr plot-routine
	"sensType"	=> "LR",
	"doPlot"	=> "1",
	"sensIds"	=> [1],
	"stationId"     => $main::defaultStationId, 
	"stationIdList" => $main::defaultStationIdList, # a reference to a list of stationIds allowed
	"configId"     => "70",	
	"dbCols"	=> ["datetime", "radiation" ],
	"valCols"	=> [3],
	"grfxName"	=> "Sonnenstrahlung",
	"valNames"	=> ["Strahlung"],
	"valUnits"	=> ["W/m*m"],
	"plotFormat"	=> ["with impulses"],
	"imgName"	=> "lr".$self->{"tmpName"},
	
	# More Infos for calcMinMaxAv routine
	"tableName"	=> "light",	
	"mmaNames"	=> [ "Sonnenstrahlung"],
	"mmaDBCol"	=> ["radiation"],
	"mmaHasMin"	=> "0", 	# Senors value has a minumim; see printmma
	"mmaUnits"      => ["W/m*m"],
	
	# Other stuff
	"displayMMA"	=> "1",
	"graphics"      => "1",                 # show in graphics by default
	"statistics"    => "1",                 # show in statistics by default
   };
   
   return($sensor);
}


#
# Method for settings defaults values for a particular sensor display type
# Returns *Reference* to data hash
#
sub setLUdefaults{
   my ($self) = shift;
   my ($sensor)={
	# General info fpr plot-routine
	"sensType"	=> "LU",
	"doPlot"	=> "1",
	"sensIds"	=> [1],
	"stationId"     => $main::defaultStationId, 
	"stationIdList" => $main::defaultStationIdList, # a reference to a list of stationIds allowed
	"configId"     => "80",	
	"dbCols"	=> ["datetime", "uvindex" ],
	"valCols"	=> [3],
	"grfxName"	=> "UV-Index",
	"valNames"	=> ["UV-Index"],
	"valUnits"	=> ["Index"],
	"plotFormat"	=> ["with impulses"],
	"imgName"	=> "lu".$self->{"tmpName"},
	
	# More Infos for calcMinMaxAv routine
	"tableName"	=> "light",	
	"mmaNames"	=> ["UV-Index"],
	"mmaDBCol"	=> ["uvindex"],
	"mmaHasMin"	=> "0", 	# Senors value has a minumim; see printmma
	
	# Other stuff
	"displayMMA"	=> "1",
	"graphics"      => "1",                 # show in graphics by default
	"statistics"    => "1",                 # show in statistics by default
	"mmaUnits"      => ["Index"],
   };
   
   return($sensor);
}



#
# get sensor Names from Database
#
sub getSensorNames{
   my ($self)=shift;
   my ($dbh) =shift;
   my ($refSensor);
   my ($name, $i, $type, $dbType, $sql);
   
   $refSensor=$self->getFirstSensor("all");
   while( defined(%{$refSensor}) ){
      # Extract sensor information from database based on type of sensor
      # and sensor ID.
      $type=$refSensor->{"sensType"};
      $dbType=main::mapTypeName2DbName($type);
      
      if(defined($dbType) ){      
	foreach $i (@{$refSensor->{"sensIds"}}){
           # Get name from Database
	   # Since it may happen that for one sensor we accept values from different stationId's
	   # $statioIdSql might allow several stations and so the result of this SQL statement
	   # can find more than one matching line. Hence we use LIMIT 1.
	   $sql="SELECT name FROM sensor_descr WHERE sensid=$i AND type='$dbType' " . 
	        "AND " . $refSensor->{"stationIdSql"} . "LIMIT 1";
	   #print "$sql <hr>\n";
	   $name=$dbh->selectrow_array($sql);
	   # No value found?
	   if( !length($name) ){
	 	  $name="Sensor-id $i";
	   }
	   # Enter name value into sensors data
	   $refSensor->{"sensorDbNames"}->[$i]=$name;
	}
	# Get next
      }
      $refSensor=$self->getNextSensor("all");
   }
}

#
# Return the path and name to the image for a sensor display
#
sub getSensImgPath{
   my ($self)=shift;
   my ($refSens)=shift;
   my ($i);

   return( $self->{"imgPath"} . "/" . $refSens->{"imgName"} );
}


#
# Return the Url to the image for a sensor display
#
sub getSensImgUrl{
   my ($self)=shift;
   my ($refSens)=shift;

   return( $self->{"imgUrl"} . "/" . $refSens->{"imgName"} );
}


#
# helper for addSensor() function to create a partial SQL statements for the stationid selection
#
sub calcStationIdSql {
   my($self)=shift;
   my($defaultStationId)=shift;
   my($stationId)=shift;
   my($stationIdList)=shift; # ref to array
   my($i, $stationIdSql, %sid, @list);

   #print "* $stationId, ", join("#", @$stationIdList), "<br>\n";
   undef %sid;
   foreach $i (@{$stationIdList}){
      $sid{$i}=1;
   }
   # Now add the value of the config variable $refDefaults->{"stationId"} to  %sid
   # it may contain a single id of a weather station
   $sid{$stationId}=1 if( $stationId > 0 );
   @list=(keys(%sid));
   if( $#list < 0 ){  			# We did not fine any stationId yet to build 
      $list[0]=$defaultStationId;	# stationIdSql, so we use the default one
   }
   # Now construct SQL needed like "stationid=1 OR stationid=5" 
   $stationIdSql="";
   foreach $i (@list){
      $stationIdSql.=" OR " if( length($stationIdSql) );
      $stationIdSql.="stationid=$i";
   }
   $stationIdSql="( $stationIdSql )";
   #print "** $stationIdSql <br>\n";
   # return string
   return($stationIdSql);
   
}


#
# Add a new sensor to display
#
sub addSensor{
        my ($self) = shift;
	my ($refSensData)=shift;
	my ($refVirtSens)=shift;
	my ($refDefaults)={};
	my ($i, $t, $refGlobal,$configId, $tmp, $tmp1, $stationIdSql, %sid);

	$t=${$refSensData}{"sensType"};
	if( !defined($t) ){
		warn "No Type of sensor defined in Class sensDisplayData\n";
		return;
	}
	if( ${$refSensData}{"sensType"} =~ /TH/ ){
		$refDefaults=$self->setTHdefaults();
	}elsif(${$refSensData}{"sensType"} =~ /PR/ ){
		$refDefaults=$self->setPRdefaults();
	}elsif(${$refSensData}{"sensType"} =~ /WI/ ){
		$refDefaults=$self->setWIdefaults();
	}elsif(${$refSensData}{"sensType"} =~ /WD/ ){
		$refDefaults=$self->setWDdefaults();
	}elsif(${$refSensData}{"sensType"} =~ /WA/ ){
		$refDefaults=$self->setWAdefaults();
	}elsif(${$refSensData}{"sensType"} =~ /RA/ ){
		$refDefaults=$self->setRAdefaults();
	}elsif(${$refSensData}{"sensType"} =~ /LI/ ){
		$refDefaults=$self->setLIdefaults();
	}elsif(${$refSensData}{"sensType"} =~ /LD/ ){
		$refDefaults=$self->setLDdefaults();
	}elsif(${$refSensData}{"sensType"} =~ /LR/ ){
		$refDefaults=$self->setLRdefaults();
	}elsif(${$refSensData}{"sensType"} =~ /LU/ ){
		$refDefaults=$self->setLUdefaults();
	}else{
		warn "Unknown Sensor type: \"", ${$refSensData}{"sensType"},
		     "\", in Class sensDisplayData::addSensor()\n"; 
	}
	
	# Get Global default values and enty into sensor if not already defined
	$refGlobal=$self->setGlobalDefaults();
	foreach $i (keys(%{$refGlobal})){
	   if( ! defined(${$refDefaults}{$i}) ){
	   	${$refDefaults}{$i}=${$refGlobal}{$i};	
	   }
	}

	# Create a config id for each configuration entry. 
	# This id is unique for each configuration that exists
	# At the moment this is kind of doubling a sensid
	# If the user supplied one, we try this else generate a default one
	if( !defined($refSensData->{"configId"}) ){
	   if( $refSensData->{"sensType"} =~ /TH/ ){
	       # for TH sensors we we use a default config ID of the sensId used
	       $configId=$refSensData->{"sensIds"}->[0];
	   }else{
	       # All other sensor types get a default config Id that identifies
	       # The sensors type and is compatible to the old sensid scheme:
	       # wind:30, rain:40, pressure:20, light:50
	       $configId=$refDefaults->{"configId"};
	   }
	}else{
	  $configId=$refSensData->{"configId"};
	}   
	# search if configId has already been defined
	$tmp1=0;  # flag if a double defined configId has been found
	do{
	   $tmp=0;
 	   foreach $i (keys(%{$self->{"configIds"}})){
	      if( $i == $configId ){
		 $tmp=1;
		 $tmp1=$i;
		 if( $configId < 200 ){
		   $configId+=200;
		 }else{
		   $configId++; # try a new configId
		 }
	      }
	   }
	}while($tmp);   
        #
	#if( $tmp1 ){
	#   print "Found double defined configId: \"$t\". Please fix this.<br>\n";
	#}
	$refDefaults->{"configId"}=$configId;
	$self->{"configIds"}->{"$configId"}="x"; # simply define it
	#
	#print "SensType:", $refDefaults->{"sensType"},
	#      " ConfigId: $configId <br>\n"; 
	

	# Create a type serial number for each sensor for its type
	# this way we can make a difference between the first TH-sensor graphics
	# and the second, third TH sensor graphics. Each of these graphics can display
	# different sets of TH sensors (with different sensor ids).
	if( defined($self->{"typeSerial"}->{$t}) ){
		$self->{"typeSerial"}->{$t}++;	
	}else{
		$self->{"typeSerial"}->{$t}=0;
	}
	# Store typeSerial id in sensors data.
	${$refDefaults}{"typeSerial"}=$self->{"typeSerial"}->{$t};
	
	# Add type Serial id of current sensor to sensors Url name
	# so different sensor graphics have different URLs and images
	if( !length($refSensData->{"userImgName"}) ){
	   ${$refDefaults}{"imgName"}=$self->{"typeSerial"}->{$t} . 
	                          ${$refDefaults}{"imgName"} ;
	}else{
	   ${$refDefaults}{"imgName"}=$refSensData->{"userImgName"};
	}
        # Calculate stationId partial SQL statement from given *defaults*
	$refDefaults->{"stationIdSql"}=$self->calcStationIdSql($refDefaults->{"stationId"}, $refDefaults->{"stationId"}, 
							        $refDefaults->{"stationIdList"});

	# Now copy current values from user given data into default array
	# So only the key->values pairs given by user will overwrite the 
	# defaults set above
	foreach $i (keys(%{$refSensData})){
	   ${$refDefaults}{$i}=${$refSensData}{$i};
	}

	# Now we have to check if inside the sensors definition there is a *user supplied* 
        # supplied sensorId or sensorIdList value. If the user provided these data, 
	# then these values overwrite the defaults determined above
        if( defined($refSensData->{"stationId"}) || defined($refSensData->{"stationIdList"}) ){
	    # Calculate stationId partial SQL statement from given defaults
	    $refDefaults->{"stationIdSql"}=$self->calcStationIdSql($refDefaults->{"stationId"}, $refSensData->{"stationId"}, 
							        $refSensData->{"stationIdList"});
        }

   	if( ${$refSensData}{"sensType"} =~ /TH/  && $refDefaults->{"windChillUseGustSpeed"} == 1 ){
		 $refDefaults->{"virtSens"}->{"windChill"}->{"in"}->{"wind"} = ["gustspeed"];
	}

	
	# Set activation flag for virtual sensors
	foreach $i (keys(%{$refVirtSens})){
		$refDefaults->{"virtSens"}->{"$i"}->{"active"}=$refVirtSens->{$i};
	}
	
	
	if( (${$refSensData}{"sensType"} =~ /WI/  || ${$refSensData}{"sensType"} =~ /WD/  ) && 
	                                    $refDefaults->{"windSpeedType"} == 1 ){
		$refDefaults->{"valUnits"}=["kn"];
		$refDefaults->{"unitfactor"}->{"speed"}=$main::kmhToKnots;
		$refDefaults->{"mmaUnits"}=["kn"];
	}

	# Enter this sensor into list of sensors to display
	$self->{"sensors"}->[$self->{"sensorCount"}]=$refDefaults;	
	$self->{"sensorCount"}++;
	
	return($refDefaults);
}


#
# Set a property of a virtual sensor 
#
sub setVirtSensAttrib{
   my($self)=shift;
   my($sensData)=shift;
   my($virtSens)=shift;
   my($virtAttrib)=shift;
   my($value)=shift;
   
   $sensData->{"virtSens"}->{"$virtSens"}->{"$virtAttrib"}=$value;
}


#
# Return ref to hash with first sensor data in it
# Only return a sensor that has the visibility bit set depending on 
# the display Mode ($displayMode) it will be used for which can be 
# statistics (flag named: $refSensor->{"statistics"})  
# or graphics (flag named: $refSensor->{"graphics"})
# if $displayMode is "all" then all sensors will be returned no matter
# of their internal "graphics" or "statistics" flag.
#
sub getFirstSensor{
   my ($self)=shift;
   my ($displayMode)=shift; # "graphics" or "statistics" or "all"
   
   $self->{"currentSensor"}=0;
   
   # Only return sensor if its marked visible either for statistics or 
   # graphics display depending on the mode it shall be used ($displayMode)
   #
   if( $displayMode eq "all" || 
       $self->{"sensors"}->[$self->{"currentSensor"}]->{"$displayMode"} ){
         return $self->{"sensors"}->[$self->{"currentSensor"}];
   }else{
       return( $self->getNextSensor($displayMode) );
   }	 
} 


#
# Return ref to hash with sensor data of next sensor in it
# obeying $displayMode, see description above
#
sub getNextSensor{
   my ($self)=shift;
   my ($displayMode)=shift; # "graphics" or "statistics" 
   
   while( $self->{"sensorCount"} > $self->{"currentSensor"} ){
      $self->{"currentSensor"}++;
      if(  $displayMode eq "all" || 
           $self->{"sensors"}->[$self->{"currentSensor"}]->{"$displayMode"} ) {
	   return $self->{"sensors"}->[$self->{"currentSensor"}];  
      }
   }
   return(undef);	   
} 


#
# Return hash with sensor data of first sensor of type sensType
#
sub getFirstSensorOfType {
  my($self)=shift;
  my($sensType)=shift;
  my ($displayMode)=shift; # "graphics" or "statistics" 
  my($c); # just to make life more reable
  
  $self->{"currentSensorOfType"}->{"$sensType"}=0;
  $c=$self->{"currentSensorOfType"}->{"$sensType"};
  
  
  # walk through list of sensors and look for one of type searched for
  while( $self->{"sensorCount"} >= $c ){
     if( ( $displayMode eq "all" || 
           $self->{"sensors"}->[$c]->{"sensType"} eq $sensType )  && 
         $self->{"sensors"}->[$c]->{"$displayMode"} ){
	return( $self->{"sensors"}->[$c] );
     }
     $c++;
     $self->{"currentSensorOfType"}->{"$sensType"}=$c;
  }    
  return(undef);
}


#
# Return hash with sensor data of next sensor of type sensType
#
sub getNextSensorOfType {
  my($self)=shift;
  my($sensType)=shift;
  my ($displayMode)=shift; # "graphics" or "statistics" 
  my($c); # just to make life more reable
  
  $self->{"currentSensorOfType"}->{"$sensType"}++;
  $c=$self->{"currentSensorOfType"}->{"$sensType"};
  
  # walk through list of sensors and look for one of type searched for
  while( $self->{"sensorCount"} >= $c ){
     if( ( $displayMode eq "all" ||
           $self->{"sensors"}->[$c]->{"sensType"} eq $sensType ) && 
           $self->{"sensors"}->[$c]->{"$displayMode"} ){
         return( $self->{"sensors"}->[$c] );
     }
     $c++;
     $self->{"currentSensorOfType"}->{"$sensType"}=$c;
  }    
  return(undef);
}


#
# Find Sensor with certain configId
#
sub getSensorWithConfigId{
  my($self)=shift;
  my($id)=shift;
  my($refSensor);
  
  $refSensor=$self->getFirstSensor("all");
  while( defined(%{$refSensor}) ){
      return($refSensor) if( $refSensor->{"configId"} == $id );
      
      $refSensor=$self->getNextSensor("all");
  }    
  return(undef);
}


#
# Set the MMA plot flaf of virtual sensors to the value their
# real "father" sensor has been told to display
#
sub setVirtMma{
   my($self)=shift;
   my($refSensor) =shift;
   my($refDoPlotMma)=shift;

   my($mmaSelected, $i, $active);
   
   $active00;
   
   $mmaSelected=$refDoPlotMma->{"min"} . ";" . $refDoPlotMma->{"max"} . 
                 ";" . $refDoPlotMma->{"avg"};   
   # Set MMA of all virtual sensors of the real Sensor $refSensor 
   # to new MMA flags
   foreach $i (keys(%{$refSensor->{"virtSens"}})){
   	$active=1 if($refSensor->{"virtSens"}->{"$i"}->{"active"} ); 
	$refSensor->{"virtSens"}->{"$i"}->{"doPlotMma"}="$mmaSelected";
   }		
   return($active); 
}   


#
# From the data in the sensors hash for each sensor calculate all the database
# columns needed for output. These are cols needed for displayinf the sensors value as well
# as columns possibly needed by a virtual sensor (like windchill) that is calculated
# from the raw data. We also set up an arry denoting all output columns that finally
# will be printed to a file that serves as input to gnuplot.
#
sub calcInputOutputCols{
   my ($self) = shift;
   my($refSensor)=shift;
   my(@allInCols, @allOutCols, @allOutUnits, @allTables, 
      @allOutNames, @allOutPlotStyles, %outNameToVirtname, %colsDefined,
      @extraCols, @extraUnits, @extraNames);
   my($i, $j, $k, $h, $h1, $l);
      
   # Add all standard db columns to $allInCols needed for sensor display
   # Also fill array allOutCols obeying $omit{} from virtSensor definitions
   for($i=0; $i<= $#{$refSensor->{"dbCols"}}; $i++){   	
	# Keep this table and db column in mind
	$k=$refSensor->{"tableName"} . "." . $refSensor->{"dbCols"}[$i];
	if( ! defined($colsDefined{$k}) ){
	    $allInCols[$i]=$refSensor->{"tableName"} . "." . $refSensor->{"dbCols"}[$i];
	    $colsDefined{$k}=$i;
	}else{
		next;
	}

	# Dbcols named "factor" are in general only used for calculating sensor values
	# but are never displayed as a sensor value, so it can be omitted from
	# @allOutCols.
	if( $refSensor->{"dbCols"}[$i] !~ /factor/io ){
	    # The first OutCol is datetime by definition.
	    if( $i> 0 ){ 
		    $allOutCols[$i]=$refSensor->{"tableName"} . "." . $refSensor->{"dbCols"}[$i];
		    $allOutUnits[$i]=$refSensor->{"valUnits"}[$i-1];
		    $allOutNames[$i]=$refSensor->{"valNames"}[$i-1];
		    if( defined($refSensor->{"plotFormat"}[$i-1]) ){
		       $allOutPlotStyles[$i]=$refSensor->{"plotFormat"}[$i-1];
		    }else{
		       $allOutPlotStyles[$i]=$refSensor->{"plotFormat"}[0];
		    }   
	   }else{
		   $allOutCols[$i]="datetime";
		   $allOutNames[$i]="Date";
		   $allOutUnits[$i]="Date";
	   }
	}
	
 	#warn "**", $allInCols[$i], $allUnits[$i], $allNames[$i], "\n";
   }
   
   #
   # ******  From here on $i is a counter. Do not modify $i below  ******
   #
   
   # Try to find columns that are removed by a real sensor
   # Those db cols are defined in @omit of the sensor itself
   for($l=0; $l<= $#{$refSensor->{"omit"}}; $l++){   	
	   $h=$refSensor->{"omit"}->[$l];
	   $j=$refSensor->{"tableName"};
	       if( defined($colsDefined{"$j." . $h}) ){
		       # Remove entry from array
		       $h1=$colsDefined{"$j.".$h}; # Index of value (tablename.colname) in allOutCols
						   # to be cut away
		       foreach $k (keys(%colsDefined)){ # Correct index of remaning colums 
			    if( $colsDefined{$k} > $h1 ){
				    $colsDefined{$k}--;
			    }
		       }			       
		       #warn "omit index $h1\n";
		       splice(@allOutCols, $h1, 1);# omit column			   
		       splice(@allOutUnits, $h1, 1);# omit column			   
		       splice(@allOutNames, $h1, 1);# omit column			   
		       splice(@allOutPlotStyles, $h1, 1);# omit column
	       }		
   }

   # Now add all the columns needed by any virtual sensors defined, avoid double defined 
   # database columns. We sort the virtual sensornames (like windchill, ...) 
   # to obtain a defined sequence
   foreach $l (sort(keys(%{$refSensor->{"virtSens"}}))){
   	#warn "**:  $l\n";
	
   	# if virtual sensor is not active simply ignore it
	next if( ! $refSensor->{"virtSens"}->{$l}->{"active"});
	
	# Try to find columns that are removedby a virtual sensor 
	# Those db cols are defined in @omit 
	foreach  $j (sort(keys(%{$refSensor->{"virtSens"}->{$l}->{"omit"}}))){
		$h=$refSensor->{"virtSens"}->{$l}->{"omit"}->{$j};
		for($k=0; $k<=$#{$h}; $k++){
			if( defined($colsDefined{"$j." . $h->[$k]}) ){
				# Remove entry from array
				$h1=$colsDefined{"$j.".$h->[$k]}; # Index of value in allOutCols
							          # to be cut away
				foreach $i (keys(%colsDefined)){ # Correct index of remaning colums 
			   	     if( $colsDefined{$i} > $h1 ){
					     $colsDefined{$i}--;
				     }
				}			       
				#warn "omit index $h1\n";
				splice(@allOutCols, $h1, 1);# omit column			   
				splice(@allOutUnits, $h1, 1);# omit column			   
				splice(@allOutNames, $h1, 1);# omit column			   
		                splice(@allOutPlotStyles, $h1, 1);# omit column
			}		
		}
	}
		
	# Now add further input columns to allInCols needed by virtual sensors 
	# Iterate over all input table names for virtual sensor $l
   	foreach  $j (sort(keys(%{$refSensor->{"virtSens"}->{$l}->{"in"}}))){
		#warn "++: $j\n";
		$h=$refSensor->{"virtSens"}->{$l}->{"in"}->{$j};
		# Now iterate over all dbcols for table $j of virSens $l
		for($k=0; $k<=$#{$h}; $k++){
			#warn "--: $k ", $h->[$k], "\n";
			# if table.dbccol not yet defined, add it to allInCols
			if( ! defined($colsDefined{"$j.".$h->[$k]}) ){
				#warn "-> ", "$j.".$h->[$k], " ", $colsDefined{"$j".$h->[$k]}, "\n"; 
				$allInCols[$i]="$j.".$h->[$k];
				$colsDefined{"$j.".$h->[$k]}=$i;
				$extraCols[$#extraCols+1]=$allInCols[$i];
			 	$extraNames[$#extraNames+1]=$refSensor->{"virtSens"}->{$l}->{"inName"}->{$j};
			 	$extraUnits[$#extraUnits+1]=$refSensor->{"virtSens"}->{$l}->{"inUnit"}->{$j};
				$i++;
			}
		}
	}

	# Add colums to allOutCols from virtual Sensors
   	foreach  $j (sort(keys(%{$refSensor->{"virtSens"}->{$l}->{"out"}}))){
		$h=$refSensor->{"virtSens"}->{$l}->{"out"}->{$j};
		$allOutCols[$#allOutCols+1]="$j";
		$allOutUnits[$#allOutUnits+1]=$h;
		$allOutNames[$#allOutNames+1]=$j;
		# Plot format definition:
		if( defined($refSensor->{"virtSens"}->{$l}->{"plotFormat"}->{"$j"}) ){
		   $allOutPlotStyles[$#allOutPlotStyles+1]=
		      $refSensor->{"virtSens"}->{$l}->{"plotFormat"}->{"$j"};
		}else{
		   $allOutPlotStyles[$#allOutPlotStyles+1]=$refSensor->{"plotFormat"}->[0];
		}
		# Map output column name of virtual sensor to 
		# name of virtual sensor
		$outNameToVirtname{"$j"}="$l";
		#warn "AllOutCols: $j, AllOutUnits: $h \n";
	}	
   }

   if( !$#allOutCols ){
   	die "Configuration error !!!! <br>\n",
	    "There are no output values defined that could be displayed.\n",
	    "Perhaps you omitted to many sensor values in the configuration?\n";
   }
   
   $refSensor->{"allInCols"}=	[@allInCols];
   $refSensor->{"allOutCols"}=	[@allOutCols];
   $refSensor->{"allOutUnits"}= [@allOutUnits];
   $refSensor->{"allOutNames"}=	[@allOutNames];
   $refSensor->{"allOutPlotStyles"}=[@allOutPlotStyles];   
   $refSensor->{"extraCols"}=	[@extraCols];
   $refSensor->{"extraNames"}=	[@extraNames];
   $refSensor->{"extraUnits"}=	[@extraUnits];
   $refSensor->{"colsDefined"}=	{%colsDefined};
   $refSensor->{"outNameToVirtname"}={%outNameToVirtname};   



   #$j=$#allInCols;
   #for ($i=0; $i<=$j; $i++){
   #	warn "+ InCols: ", $refSensor->{"allInCols"}->[$i], "<br>\n";
   #}

   #$j=$#allOutCols;
   #for ($i=0; $i<=$j; $i++){
   #	warn "+ OutCols: $allOutCols[$i], Units: $allOutUnits[$i], Names: $allOutNames[$i] <br>\n";
   #}
   #die;
}


# Access routines to the internal data structure
# for accessing this data structure from other classes, functions.
# ----
sub getAllInCols{
   my($self)=shift;
   my($refSensor)=shift;
   
   return($refSensor->{"allInCols"});
}
sub getAllOutCols{
   my($self)=shift;
   my($refSensor)=shift;
   
   return($refSensor->{"allOutCols"});
}
sub getAllOutUnits{
   my($self)=shift;
   my($refSensor)=shift;
   
   return($refSensor->{"allOutUnits"});
}
sub getAllOutPlotStyles{
   my($self)=shift;
   my($refSensor)=shift;
   
   return($refSensor->{"allOutPlotStyles"});
}  
sub getAllOutNames{
   my($self)=shift;
   my($refSensor)=shift;
   
   return($refSensor->{"allOutNames"});
}
sub getExtraNames{
   my($self)=shift;
   my($refSensor)=shift;
   
   return($refSensor->{"extraNames"});
}
sub getExtraCols{
   my($self)=shift;
   my($refSensor)=shift;
   
   return($refSensor->{"extraCols"});
}
sub getExtraUnits{
   my($self)=shift;
   my($refSensor)=shift;
   
   return($refSensor->{"extraUnits"});
}
sub getColsDefined{
   my($self)=shift;
   my($refSensor)=shift;
   
   return($refSensor->{"colsDefined"});
}
sub getOutNameToVirtname{
   my($self)=shift;
   my($refSensor)=shift;
   
   return($refSensor->{"outNameToVirtname"});
}
sub getFactor{
   my($self)=shift;
   my($refSensor)=shift;
   
   return($refSensor->{"factor"} ? $refSensor->{"factor"} : "");
}
sub getSensIds{
   my($self)=shift;
   my($refSensor)=shift;
   
   return($refSensor->{"sensIds"});
}
sub getVirtSensors{
   my($self)=shift;
   my($refSensor)=shift;
   
   return($refSensor->{"virtSens"});
}
#----


# -----------------------------------------------------------------------
# Class for constructing SQL commands for data retrieval of sensor data
# Each instance needes a sensor instance and a reference to the data 
# of the sensor in question as an argument to the construntor
# as well as a database handle fo access to the database. 
# -----------------------------------------------------------------------
package dataManager;

sub new{
        my ($class) = shift;
	my ($localDbh)   =shift;
	my ($sensObject) =shift;
	my ($sensData)  = shift;
	my ($dstRange)  = shift;
	my ($refMma)	= shift;
        my ($self) = {};
        bless $self, $class;
		
	$self->{"localDbh"}=$localDbh;
	$self->{"sensObj"}=$sensObject;
	$self->{"sensData"}=$sensData;
	$self->{"dstRange"}=$dstRange;
	$self->{"mmaValues"}=$refMma;

	return($self);
}


# 
# Set global options for this instance. The options are needed for 
# constructiong a SQL commad. An example is the start and endtime
# for which data should be fetched
sub setOptions{
   my($self)=shift;
   my($refOptions)=shift;
   my($i);
   
   # Enter Options in %$refOptions into classes options hash
   foreach $i (keys(%$refOptions)){
   	$self->{"options"}->{"$i"}=$refOptions->{"$i"};
   }
}


# At the moment we ty the plotting of MMA values of virtual sensors 
# to the settings of the real sensor. So if MMA values are plotted for
# a real sensor they also will be plotted for its virtual sensors
# An exception to this rule is if the mma daterange is different
# from the datrange of the graphics display. In this case we cannot display
# virtsens MMA data, since we only have them for the daterange of the display
sub checkVirtMma{
   my($self)=shift;
   my($refSensor)=shift;
   my(%plotMma, $active);
   
   if( $self->{"options"}->{"mmaStartDate"} ne $self->{"options"}->{"startDate"} ||
       $self->{"options"}->{"mmaStartTime"} ne $self->{"options"}->{"startTime"} ){
         $plotMma{"min"}=0;
         $plotMma{"max"}=0;
         $plotMma{"avg"}=0;
      
         # Return value says if any virt sens was active
	 $active=$self->{"sensObj"}->setVirtMma($refSensor, \%plotMma);
	 
	 if( $active ){
	    $main::errMsg="For virtual sensors you can only display MMA values " .
	       "for the time used in the graphics display. MMA output for virtual " .
	       "sensors is disabled.";
	    return(1);
	 }else{
	    return(0);
	 }   
   }else{
      $self->{"sensObj"}->setVirtMma($refSensor, 
      				$self->{"options"}->{"refDoPlotMma"});
      return(0);				
	
   }       
}


#
# Adjust start and enddate to the beginning of the month or year 
# depending on the $sampleTime value 
# By this way we set each average value (for a month or year) at the very 
# beginning of this period.
#
sub adjustDates{
   my($sd, $st, $ed, $et, $sampleTime)=@_;
   my($y1, $m1, $d1, $y2, $m2, $d2);
   my($delta, $errCode, $errMsg);
   my($locDate, $locTime);

   $errCode=0;
   $errMsg="";
   # Convert sd and ed to local timezone
   ($locDate, $locTime)=main::timeConvert($sd, $st, "LOC");
   ($y1, $m1, $d1)=split(/-/o, $locDate);
   ($locDate, $locTime)=main::timeConvert($ed, $et, "LOC");
   ($y2, $m2, $d2)=split(/-/o, $locDate);
   
   if( $sampleTime =~ /^m/o ){      # We display monthly average values
      $errMsg="Das Startdatum wurde f&uuml;r die Darstellung tempor&auml;r vom: $d1-$m1-$y1 auf " .
           "01-$m1-$y1 umgesetzt.";
      $errCode="e1";	   
      $d1="01";
      $st="00:00:00";
      $sd="$y1-$m1-$d1";
   }elsif( $sampleTime =~ /^y/o ){
      $errMsg="Das Startdatum wurde f&uuml;r die Darstellung tempor&auml;r vom: $d1-$m1-$y1 auf " .
           "01-01-$y1 umgesetzt.";
      $errCode="e2";	   
      $m1="01";
      $d1="01";
      $st="00:00:00";
      $sd="$y1-$m1-$d1";
   }
   
   # Correct delta days for new start date	
   $delta=main::Delta_Days($y1,$m1,$d1,
                              $y2,$m2,$d2);

   # convert startDate back to GMT
   ($sd, $st)=main::timeConvert($sd, $st, "GMT");
   
   return(($sd, $st, $ed, $et, $delta, $errCode, $errMsg));
}


# Since in buildSqlCommand, when $sampleTime is Month or Year, we 
# let the database output average entries that start exactly at day 01
# or 01-01 (month & day) if $sampleTime==[my], we have to correct the displayed starting
# date to the start of the month or year as well. Else gnuplot would not display 
# all of or any data.
sub calcCorrectedDates{
   my($self)=shift;
   my($y1, $m1, $d1,$y2, $m2, $d2 ,$delta, $deltaH, $tmp,$errCode, $errMsg,
       $startDate,$endDate,$startTime,$endTime, $sampleTime);
   
   $startDate=$self->{"options"}->{"startDate"};
   $startTime=$self->{"options"}->{"startTime"};
   $endDate=$self->{"options"}->{"endDate"};
   $endTime=$self->{"options"}->{"endTime"};
   $sampleTime=$self->{"options"}->{"sampleTime"};
   
   # Calculate number of days between start and end
   ($y1, $m1, $d1)=split(/-/o, $startDate);
   ($y2, $m2, $d2)=split(/-/o, $endDate);
   ($delta, $deltaH, $tmp, $tmp)=main::Delta_DHMS($y1,$m1,$d1, split(/:/o, $startTime),
                              $y2,$m2,$d2, split(/:/o, $endTime));

   if(  $sampleTime =~ /^[my]/o ){   
       # Since in buildSqlCommand, when $sampleTime is Month or Year, we 
       # let the database output average entries that start exactly at day 01
       # or 01-01 (month & day) if $sampleTime==[my], we have to correct the displayed starting
       # date to the start of the month or year as well. Else gnuplot would not display 
       # all of or any data. The delta of days beetween start and end is corrected as well.
       # All this is done here.  This 
       # correction is done only for the display not permanently. 
       ($startDate, $startTime, $endDate, $endTime, $delta, $errCode, $errMsg)=
                             adjustDates($startDate, $startTime, $endDate, $endTime, $sampleTime);
   }
   $self->{"options"}->{"correctedStartDate"}  = $startDate;
   $self->{"options"}->{"correctedStartTime"}  = $startTime;
   $self->{"options"}->{"correctedEndDate"}    = $endDate;
   $self->{"options"}->{"correctedEndTime"}    = $endTime;
   $self->{"options"}->{"delta"} = $delta;
   $self->{"options"}->{"deltaH"} = $deltaH;
   $self->{"errCodes"}.="$errCode";		# Error information for user
   $self->{"errMsgs"}.="$errMsg";
}


#
# calculate a lower Y value for some sensors for a better graphical display. 
#
sub calcLowYbounds{
   my($self)=shift;
   my($sensData)=shift;
   my($tmp, $i, $j, $k, $f, $virt);
   
   
   if( defined($sensData->{"lowYbounds"}) ){
        # user defined lowYbounds value
	$self->{"options"}->{"lowYbounds"}=$sensData->{"lowYbounds"};
   }else{ 
      # Some sensors need a special lower y scale limit that has to be calculated
      if( $sensData->{"sensType"} =~/PR/ ){
	 $j=-1;
	 # Check all Pressure sensIds 
	 foreach $i (keys(%{$self->{"results"}})){
            if( ($j< 0) || 
	      ($j > $self->{"results"}->{$i}->{"mma"}->{"P"}->{"minValue"}) ){
	      $j=$self->{"results"}->{$i}->{"mma"}->{"P"}->{"minValue"};
	    }  
	 } 
	 $tmp=int($j *0.99);
	 $tmp=$tmp-($tmp%20);

      # if temperature is < 0 then do autoscaling else start with 0 as lower
      # bound
      }elsif( $sensData->{"sensType"} =~/TH/ ){
           $tmp=0;
	   # Look if any virtual sensor has a minimum value < 0 
	   $virt=$self->{"results"}->{"virtSens"};
	   foreach $i (keys(%{$virt})){   # virtsensor Names
	      if( $sensData->{"virtSens"}->{"$i"}->{"active"} ){
		 foreach $j (keys(%{$virt->{$i}})){ # VirtSensor Ids
	            foreach $k (keys(%{$virt->{$i}->{$j}->{"mma"}})) { # ValueName
		       if( $virt->{$i}->{$j}->{"mma"}->{"$k"}->{"minValue"} < 0 ){
		    	   $tmp="auto";
		       }
		    }
		 }
	      }
	   }
	   # Look if  any temp sonsor has value < 0 
	   $j=9999;
           foreach $i (keys(%{$self->{"results"}})){
              if( ($j == 9999) ||
		  ($j > $self->{"results"}->{$i}->{"mma"}->{"T"}->{"minValue"}) ){
		$j=$self->{"results"}->{$i}->{"mma"}->{"T"}->{"minValue"};
	      }
	   }     
   	   if( $j < 0 ){
	       $tmp="auto";
	   }    
      }else{
	 $tmp="auto";
      }

      #$self->{"results"}->{"$sensId"}->{"lowYbounds"}=$tmp;
      $self->{"options"}->{"lowYbounds"}=$tmp;
   }
}


#
# Find all date entries of all data arrays for multiple sensids of one sensortype.
# This info is used in writeDataFile() to write the data of the different sensorids
# for one graphics with possibly a different number of data of each sensorid in a 
# correct fashion. Think for example a sensor A 
# has been active right from the start, a sensor B had been added some days later.
# Sensor A and B will be displayed in one graphics
# Now for sensor A there many more datasets available then for B. Here we create a 
# list of all data entries off all sensors containing only the date-entry. 
# In writeDataFile we then can walk through this list and either echo the sensors value 
# or a "undefined" value.
#
sub mkDateList{
   $self=shift;
   $refDateList=shift;
   @data=@_;  # Array with refs to data arrays
   
   my($i, $j, $hiva, $max, $maxIdx, $equal, $arrayCount);
   
   $max=$#{$data[0]};	# longest array with data (number of elements therein)
   $maxIdx=0;
   $equal=1;    # all arrays have equal length?
   $arrayCount=$#data;
   
   for($i=1; $i<= $arrayCount; $i++){ # run through all data arrays
   	#print "+ $i \n";
	if( $#{$data[$i]} > $max ){
	   $max=$#{$data[$i]};
	   $equal=0;
	}elsif($#{$data[$i]} < $max ){
	   $equal=0;
	} 
   }
   #print " $max, $maxIdx, $equal \n";
   
   #return 1 if( $equal  );

   for($i=0; $i<=$max; $i++){
      for($j=0; $j<=$arrayCount; $j++){
          if( defined($data[$j]->[$i]) ){
	     $refDateList->{$data[$j]->[$i]->{"loctime"}}=1;
	  }
      }
   }
   return(0);
}


#
# Function that directs data extraction from db, calculation for virtual sensors
# and writing the results to a file for gnuplot for all sensids of ONE sensor. 
#
sub prepareSensData{
   my($self)=shift;
   my($mmaOnly)=shift;
   my($i, $refSensorIds,  $id, @result, $result1, %dateRef, $equal);

   # correct Start and End dates depending on sampleTime  
   $self->calcCorrectedDates(); 

   $refSensorIds=$self->{"sensObj"}->getSensIds($self->{"sensData"});
   
   # construct sql commands needed for data extraction
   $self->buildAllSqlCommands();
   
   # Iterate over all sensorIds of one sensortype, eg all
   # th_sensors

   for($i=0; $i<= $#{$refSensorIds}; $i++){
        $id=$refSensorIds->[$i];
	$self->getMmaValues();			# Determine Min/Max/Avg
	$result[$i]=$self->getDataFromDb($id) if( !$mmaOnly ); # Extract Data from Database
   }
   if( ! $mmaOnly ){
      # Take care that for all sensors of one type (eg th) there are entries in the
      # datafile with  all date-entries that are in any of the $result[] arrays. So afterwards
      # each of the data-arrays share the same number of data lines with the same date entries 
      # allthough not each line contains data but just a date entry
      $equal=$self->mkDateList(\%dateRef, @result);	

      for($i=0; $i<= $#{$refSensorIds}; $i++){
           $id=$refSensorIds->[$i];
	   # Store a reference to the date-Hash as well as the information 
	   # if all data arrays of the sensors were of equal length 
	   $self->{"results"}->{"$id"}->{"allDateEntries"}=\%dateRef;
	   $self->{"results"}->{"$id"}->{"dataNumberEqual"}=$equal;

	   $result1=$self->applyVirtSensors($id, $result[$i]); # Calculate new columns for virtual sensors
	   $self->{"results"}->{"$id"}->{"sqlData"}=$result1;  # Store result
      }	
      # Calculate a lower Y-Bound needed for some sensors (eg pressure)
      $self->calcLowYbounds($self->{"sensData"});
   }
}



#
# Write all the default gnupolut definirtions and config to gnuplot file
#
sub writeGnuplotHeader{
   my $self=shift;
   my $sensData=shift;
   my $file=shift;
   my($refSensorIds)=shift;
   
   my($imgFile)=$self->{"sensObj"}->getSensImgPath($sensData);  # Path and Name
   my($xScale)=$self->{"options"}->{"xscale"};
   my($yScale)=$self->{"options"}->{"yscale"};
   my($xCanvas)=$self->{"sensData"}->{"xCanvas"}; # Default size for canvas for, used 
   my($yCanvas)=$self->{"sensData"}->{"yCanvas"}; # gnuplot >= 4.2
   my($lowYbound)=$self->{"options"}->{"lowYbounds"};
   my($startDate)=$self->{"options"}->{"correctedStartDate"};
   my($startTime)=$self->{"options"}->{"correctedStartTime"};
   my($endDate)=$self->{"options"}->{"correctedEndDate"};
   my($endTime)=$self->{"options"}->{"correctedEndTime"};
   my($sampleTime)=$self->{"options"}->{"sampleTime"};
   my($delta)=$self->{"options"}->{"delta"};
   my($deltaH)=$self->{"options"}->{"deltaH"};

   my($err, $max, $tmp, $mytics, $tics, $timeFormat, $bgColor);
   my($lineWidth, $pointSize, $pointType);
   my($tmp, $tmp1, $gnuplotLsCmd, $gnuplotTerm, $gnuplotSize, $gnuplotXlabel);
   
   
   # Gnuplot 3 and 4 use different linestyle commands (and more  :-( ... )
   $gnuplotXlabel="set xlabel 'Datum' 0,-2";
   if( $main::gnuplotVers == 3 ){
        $gnuplotLsCmd="set linestyle";
        $gnuplotTerm="set terminal png small color";
	$gnuplotSize="set size $xScale,$yScale";
   }elsif( $main::gnuplotVers == 4 ){
        $gnuplotLsCmd="set style line";
	$gnuplotTerm="set terminal png small";
	$gnuplotSize="set size $xScale,$yScale";
   } elsif( $main::gnuplotVers == 4.2 || $main::gnuplotVers == 4.4 ){
   	# Behaviour of gnuplot in 4.2 is a little strange. The PNG terminal 
	# supports a minimal size of 640x480 and multiples >=2 of this size.
	# However you cannot use set size command to scale the size up but have to do this
	# using the set terminal png size x y  command. Scaling down is completely different: 
	# If you need to have a smaller result than 640x480 you cannot do this via 
	# the set terminal size command like "set terminal png size 320 240" 
	# parameter but now have to use the set size command eg "set size 0.5, 0.5"
	# resulting in a 320x240 pixel graphics but in a 640x480 (default) sized
	# canvas! To crop the unused space you finally have to use the set terminal 
	# crop option.
	$gnuplotLsCmd="set style line";
	$gnuplotdspCmd="set data style points";
	if( $xScale < 1 || $yScale < 1 ){
	   $gnuplotTerm="set terminal png small size $xCanvas $yCanvas crop";
	   $gnuplotSize="set size $xScale,$yScale";
	}else{
	   $gnuplotTerm="set terminal png small size " .  int($xCanvas*$xScale) 
	                                . ", " .  int($yCanvas*$yScale);
	   $gnuplotSize="#";
	}
	if( $main::gnuplotVers >= 4.4 ){
	   $gnuplotXlabel="set xlabel 'Datum' offset 0,2";
	   $gnuplotdspCmd="set style data points";
	}
   }

   open(OUT, ">$file")|| die "Cannot open $file for writing\n";
   if( $sensData->{"sensType"} !~ /WD/i ){
      $lineWidth=1;
      # User wider lines if we plot average values (day, week, month) of the original data
      $lineWidth=3 if( $sampleTime !~ /^0/o );

      $err="0";
      # Convert dates from GMT into local time
      ($startDate, $startTime)=main::timeConvert($startDate, $startTime, "LOC");
      ($endDate, $endTime)=main::timeConvert($endDate, $endTime, "LOC");

      $startDate="$startDate\t$startTime";
      $endDate="$endDate\t$endTime";			 

      if( $xScale > 0.9 && $yScale > 0.9 ){
   	   $mytics=" mytics";
      }else{
   	   $mytics=" nomytics"
      }	     

      $timeFormat='"%Y-%m-%d	%H:%M:%S"';
      if( $sampleTime !~ /^0/o ){
   	   $bgColor=$self->{"options"}->{"bgColorAverage"};
      }else{
   	   $bgColor=$self->{"options"}->{"bgColorNormal"};
      }	

      $tmp=(1/(($delta+3)/2))* $xScale; # Pointsize for max min / avg

      # For Wind angle display we use another pointtype and size
      if( $sensData->{"sensType"} =~ /WA/i ){
   	   $pointSize=1*$xScale;
	   $pointType=7;
	   $lineWidth=0.5;
      }else{
   	   $pointSize=0.5;
	   $pointType=2;
      }
      
      print OUT <<EOF
set encoding iso_8859_15
set xdata time
set autoscale
$gnuplotSize

# Be aware: There is a tab inside !!
set timefmt $timeFormat

# Line style for data  sensor1, sensor 2
$gnuplotLsCmd  1 lt  1 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd  2 lt  2 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd  3 lt  3 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd  4 lt  4 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd  5 lt  5 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd  6 lt  6 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd  7 lt  7 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd  8 lt  8 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd  9 lt  9 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd 10 lt 10 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd 11 lt 11 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd 12 lt 12 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd 13 lt 13 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd 14 lt 14 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd 15 lt 15 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd 16 lt 16 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd 17 lt 17 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd 18 lt 18 lw $lineWidth pt $pointType ps $pointSize
$gnuplotLsCmd 19 lt 19 lw $lineWidth pt $pointType ps $pointSize

# MMA line styles
$gnuplotLsCmd 30 lt 19 lw 1 pt 8 ps  $tmp
$gnuplotLsCmd 31 lt 18 lw 1 pt 8 ps $tmp
$gnuplotLsCmd 32 lt 17 lw 1 pt 8 ps $tmp
$gnuplotLsCmd 33 lt 16 lw 2 pt 8 ps $tmp
$gnuplotLsCmd 34 lt 15 lw 2 pt 8 ps $tmp
$gnuplotLsCmd 35 lt 14 lw 2 pt 8 ps $tmp
$gnuplotLsCmd 36 lt 13 lw 2 pt 8 ps $tmp
$gnuplotLsCmd 37 lt 12 lw 2 pt 8 ps $tmp
$gnuplotLsCmd 38 lt 11 lw 2 pt 8 ps $tmp
$gnuplotLsCmd 39 lt 10 lw 2 pt 8 ps $tmp
$gnuplotLsCmd 40 lt  9 lw 2 pt 8 ps $tmp
$gnuplotLsCmd 41 lt  8 lw 2 pt 8 ps $tmp
$gnuplotLsCmd 42 lt  7 lw 2 pt 8 ps $tmp
$gnuplotLsCmd 43 lt  6 lw 2 pt 8 ps $tmp
$gnuplotLsCmd 44 lt  5 lw 2 pt 8 ps $tmp

set key right		# Legend is placed right
set key samplen 1	# Make sample line shorter than default
set xtics rotate
set ytics nomirror	# do not mirror ytics on right side (=>y2tics)
set y2tics		# labels at the right side as well
set mytics 5            # Count of minor tics on y axis
set my2tics 5           # Count of minor tics on y axis
$gnuplotXlabel
set ylabel 'Wert'
set output "$imgFile";
$gnuplotTerm $bgColor
set xrange ['$startDate':'$endDate']
EOF
;

      # Some more specials for WA display
      if( $sensData->{"sensType"} =~ /WA/i ){
	 print OUT <<EOF
set label "(N)" at graph 1, graph 0
set label "(N)" at graph 1, graph 1
set label "(E)" at graph 1, graph 0.25
set label "(S)" at graph 1, graph 0.5
set label "(W)" at graph 1, graph 0.75
set yrange [0:360] 
set y2range [0:360]
set noy2tics
EOF
;
      }


      if( $xScale <1.0 || $yScale < 1.0 ){
	 print OUT "set grid xtics ytics $mytics\n";
      }else{
	 # Make major lines look in another color than minor grid lines
	 print OUT "set grid xtics ytics $mytics lt 36, lt 0\n";
      }

      if( $delta <= 10 ){
	   # Try to calculate the number of minor tics we calc $tmp. $tmp
	   # is the interval between start and end at which minor tics will
	   # be drawn in seconds. 
	   # This is used by gnuplot to place the minor tics
	   # value $tmp for xtics may not be "0"
	   $tmp=int(($delta*24+$deltaH)/(12*$xScale)+0.5);
	   $tmp=int($tmp/2)*2; $tmp=2 if( ! $tmp );
           $tmp=$tmp*3600;                      
	   if( $delta*24 + $deltaH > 8 ){   # below one day we let gnuplot 
	      print OUT "set mxtics 2\n";    # set the tics automatically
	      if( $sampleTime !~ /^[0h]/o ){
		  print OUT "set xtics autofreq\n";
		  print OUT 'set format x "%d-%m-%y"' , "\n";
	      }else{
        	 print OUT "set xtics '$startDate', $tmp ,'$endDate'\n";
		 print OUT 'set format x "%d-%m-%y\n%H:%M"' , "\n";
	      }
	   }else{
		 # Only determine format
		 print OUT 'set format x "%d-%m-%y\n%H:%M"' , "\n";
	   }
      }else{
   	   # Number of hours by one major tic, minimal number
	   # of tics for below a large graphics is about 15
	   $tmp=int((($delta?$delta:1)*24+$deltaH)/(15*$xScale));
	   # Now scale the result into reasonable chunks of 6,12,24,48 hours
	   # so the distance from one tic to the next is a multiple of 
	   # either 6, 12, 24 or 48
	   $tmp=6 if( $tmp > 4 && $tmp <= 6 );
	   $tmp=12 if( $tmp > 6 && $tmp <= 12 );
	   $tmp=24 if( $tmp > 12 && $tmp <= 24 );
	   $tmp=48 if( $tmp > 24 && $tmp <= 48 );
	   $tmp=int($tmp/24)*24 if( $tmp > 48 ); 
	   $tmp=2 if( $tmp<= 4 );
	   $tmp1=$tmp*3600; # convert tic "distance" into seconds for gnuplot
	   if( $sampleTime !~ /^[0h]/o ){
	       print OUT "set xtics '$startDate', $tmp1 ,'$endDate'\n";
               print OUT 'set format x "%d-%m-%y' , "\n";
	   }else{
               print OUT "set xtics '$startDate', $tmp1 ,'$endDate'\n";
	       if( $xScale >=1.0 ){
		  print OUT 'set format x "%d-%m-%y\n%H:%M"' , "\n";	   
	       }else{
                  print OUT 'set format x "%d-%m-%y' , "\n";
	       }
	   }
	   if( $tmp <= 48 ){
	       print OUT "set mxtics 4\n";
	   }else{
	       print OUT "set mxtics 2\n";
	   }
      }

      if( ($sensData->{"sensType"} !~ /WA/i) && 
      		($lowYbound ne "auto") ){ # plot has only positive values
           print OUT "set yrange [$lowYbound:*]" , "\n";   
           print OUT "set y2range [$lowYbound:*]" , "\n";   
      }
   }else{  
   # --------------------------    WD gnuplotconf -----------------------------------------
      if( $sampleTime !~ /^0/o ){
   	   $bgColor=$main::bgColorAverage;
	   
      }else{
   	   $bgColor=$main::bgColorNormal;
      }
      # Avoid having a grid that is to narrow (to much legend text)
      # in the small overview display
      $max=$self->{"results"}->{$refSensorIds->[0]}->{"mma"}->{"speed"}->{"maxValue"};
      if( ($max / 5 > 8) && ($xScale <1.0 || $yScale <1.0) ){
   	   $tics=10;
      }else{
   	   $tics=5;
      }

      # Determine a suitable pointsize for WD plots
      # suittable is of course purely heuristic based on the number of days that are
      # displayed in the plot
      $tmp=$delta*0.004;
      $tmp=0.25 if( $tmp >0.25 );
      $pointSize=1-$tmp;
      #print "***", $pointSize, "\n";

      print OUT <<EOF
set key right		# Legend is placed left
set key samplen 1	# Make sample line shorter than default
set angles degrees
set polar
set xtics axis $tics
set ytics axis $tics
set mxtics 1
set mytics 1	
set grid polar
set noborder
set noparam

set xlabel "Windstaerke"
set ylabel "Windstaerke"
set xtics axis nomirror
set ytics axis nomirror
set label "Norden" at graph 0.51,graph 0.95
set label "Sueden" at graph 0.51, graph 0.05
set label "Westen" at graph 0.01, graph 0.53
set label "Osten" at graph 0.93, graph 0.53

$gnuplotdspCmd

set autoscale
set size $xScale,$yScale
set pointsize $pointSize

set output "$imgFile";
$gnuplotTerm $bgColor
EOF
;
   
   }   
   close(OUT);
   return($tics);
   
}


#
# Remove unwanted chars from a string for text to be displayed by gnuplot
#
sub cleanupName{
   my( $self, $theSensName)=@_;
   
   $theSensName=~s/Ã/ss/g;
   $theSensName=~s/Ã€/ae/og; $theSensName=~s/Ã/Ae/og;
   $theSensName=~s/Ã¶/oe/og; $theSensName=~s/Ã/Oe/og;
   $theSensName=~s/ÃŒ/ue/og; $theSensName=~s/Ã/Ue/og;
   
   return($theSensName);
}


#
# Create the gnuplot commands for the sensor values to be displayed. 
# This methid is basically identical to writeOutFile() but does not iterate 
# over all data sets but instead constructs gnuplot commands for the values in allOutCols
# whereas in writeOutFile() the real values of allOutCols are printed.
# It is important that the sequence for sensor values in which the data is written to the real 
# outfile for is kepr identical to the sequence of plot commands with their "Names" else 
# The user will see a plot named "x" but the value plotted are actually "y".
#
sub writeGnuplotCmds{
   my($self)=shift;
   my($refSensorIds)=shift;
   my($sensObj)=shift;
   my($sensData)=shift;
   my($gnuplotFilename)=shift;
   my($dataFilename)=shift;
   my($tics)=shift;
   my($i, $j, $k, $l, $tmp, $tmp1, $tmp2, $value, $allOutCols, $allOutNames, $allOutUnits, 
      $allOutPlotStyles, $col, $virtSens, $sensType, $sensorName, $numSensIds, $sensId, $title);
   my($gnuplotCmd, $gnuplotComment,$calcMin, $calcMax, $calcAvg, $plotFormat, 
      $mmaPlotFormat, $ls, $mmaLs, $theSensName, $theSensName1, $sensCol);   
   my(%omit, $omitVirtual, $sampleTime, $outNameToVirtname, $hasPlots, $doGustSpeed);   
   
   $err=0; # Error Status
   
   # Variable that notes if anything will be plotted. If it remains 0
   # at the end of this function gnuplot may not be called. It would 
   # simply throw an error. 
   $hasPlots=0; 
   
   # Current display Mode (real Data, average, min/max, ...)
   $sampleTime=$self->{"options"}->{"sampleTime"};
   
   $omitVirtual=0;
   # If we display minima or maxima of day week or year basis
   # we do not want to display virtual sensors since they are
   # calculated from the eg days minima. Think of dewpoint and then
   # take the minimal humidity of the day and the minimal temp 
   # of the day and calculate dewpoint thereof. The result is not
   # what you want. Since in reality the min hum and temp did not occure at
   # the same time. 
   if( $sampleTime =~ /^.+,Min/ || $sampleTime =~ /^.+,Max/ ){
	$omitVirtual=1; 
   }
   
   # Prepare handling of rain sensor and light sensor
   $sensType=$sensData->{"sensType"};
   
   # Get mapping between name of output column and virtual sensor name
   # We use this to determine which outname is a virtual one
   $outNameToVirtname=$sensObj->getOutNameToVirtname($sensData);

      
   open( OUT, ">>$gnuplotFilename")|| die "Cannot open data file  \"$gnuplotFilename\" for appending. Abort.\n";
   
   $allOutCols=$sensObj->getAllOutCols($sensData);
   $allOutNames=$sensObj->getAllOutNames($sensData);
   $allOutUnits=$sensObj->getAllOutUnits($sensData);
   $allOutPlotStyles=$sensObj->getAllOutPlotStyles($sensData);
   $virtSens=$sensObj->getVirtSensors($self->{"sensData"});   

   # Build up hash with column names to omit from @mmaOmit this is
   # for the Min/Max Average plots of those sensors. The sensors themsdelves
   # are already omitted since they are not part of allOutCols
   foreach $i (@{$sensData->{"mmaOmit"}}){
	$omit{$i}=1;
   }
   # Get list of virtual sensors to omit if 
   # virtual sensors shall be omitted
   foreach $i (@{$allOutNames}){
   	if( $omitVirtual && defined($outNameToVirtname->{$i}) ){
		$omit{$i}=1;
	}
   }
   
   # Set starting plot style parameter for gnuplot
   $ls=1;	 
   # Set starting plot style parameter for mma-plots
   $mmaLs=30;
   $mmaPlotFormat="with linespoints  ls ##";
   
   $gnuplotComment="";
   if( $sensType !~ /WD/i ){
      $gnuplotComment=<<EOS
# This is a trick: We plot the data twice once for the x and
# y1 axes, a second time for the x,y2 axes (x1y2). This way
# the autoscaling for the left and right y axes (y1,y2) are correct.
# Without this only one y axes might be scaled correctly 
# since y1 and y2 are independent from each other.
EOS
	      ;

      # Iterate of all sensorIds of the current sensor and create gnuplot commnds for them
      $numSensIds=$#{$refSensorIds};
      for($k=0; $k<= $numSensIds; $k++){
         $sensId=$sensData->{"sensIds"}->[$k];
         $sensorName=$sensData->{"sensorDbNames"}->["$sensId"];      
         $sensorName="(id: $sensId)" if( !length($sensorName) );

	 # Now print all wanted colums. Names are in $allOutCols
	 for($j=0; $j <= $#{$allOutCols}; $j++){
	    # determine plot format
	    $plotFormat=$allOutPlotStyles->[$j];
	    if( !$plotFormat ){
		$plotFormat="with lines ls ##"; #   ## will be replaced by linestyle number
	    }    
	    if( $plotFormat !~ /ls \#\#/o ){
        	 $plotFormat.=" ls ##";
	    }
	    if( ! defined($omit{$allOutNames->[$j]}) ){ 
		 # If we just do not work one the first sensor id we omit the datetime field since
		 # this should be printed only one to the output file in the first column.
		 next if( $k  && $allOutCols->[$j] eq "loctime" );

		 #print "allOutCols:", $allOutCols->[$j], "\t";
		 #print "allOutNames:", $allOutNames->[$j], "\t";  
		 #print "allOutUnits:", $allOutUnits->[$j], "\n";
		 #
		 # The first column is always the date that is not a plottable sensor value
		 # Internally the date is one colum consisting of date and time which 
		 # are seperated by a tab. For gnuplot
		 # these are two columns so the col index in the gnuplot file is +2 from 
		 # the internal colum name index $j. This is only true when the plot command 
		 # for the first sensor id is printed, not if the second... one is beeing processed
   		 if( $k == 0){
			 $i=$j+2; 
		 }else{
		 	$i++;
		 }	 

        	 if( $j ){  
			 $hasPlots++;
	   		 $tmp=$plotFormat; $tmp=~s/##/$ls/; $ls++;
			 if( $numSensIds ){
			    $tmp1=$allOutNames->[$j] . ", $sensorName";
			 }else{
			    $tmp1=$allOutNames->[$j];
			 }
			 $tmp1.="(" . $allOutUnits->[$j] . ")";
      			 $tmp1=$self->cleanupName($tmp1);
                        
			 # We want to arrange plot commands in gnuplot cms file 
			 # in such a way, that virtual sensors are printed first
			 # the the real sensor. This way the real sensors 
			 # overwrite virtual ones and not vice versa if both
			 # have the same values
			 if( !defined($outNameToVirtname->{$allOutNames->[$j]}) ){
			      $gnuplotCmd.=<<EOS
"$dataFilename" using 1:$i title '$tmp1' $tmp, \\
	'' using 1:$i axes x1y2 notitle $tmp, \\
EOS
			      ;   
			 }else{
			      $tmp2=<<EOS
"$dataFilename" using 1:$i title '$tmp1' $tmp, \\
	'' using 1:$i axes x1y2 notitle $tmp, \\
EOS
			      ;
			      $gnuplotCmd=$tmp2 . $gnuplotCmd;   
			 }
		 }
	    }
	 }

	 # print gnuplot commands for MMA values of standard sensors
	 # Iterate over all MMA db cols for one sensor
	 # e.g. the MMA values for "T" and "H" of a th_sensor with id $sensId
	 for($j=0; $j<= $#{$self->{"sensData"}->{"mmaDBCol"}}; $j++) {

	    $col=$self->{"sensData"}->{"mmaDBCol"}->[$j];
	    
	    if( ! defined($omit{$col}) && 
	      $self->{"options"}->{"refDoPlotMma"}->{"min"} ){
	        $hasPlots++;
        	$i++; # Next datafile column
  		$tmp=$mmaPlotFormat; $tmp=~s/##/$mmaLs/; $mmaLs++;
        	$title=$self->{"sensData"}->{"mmaNames"}->[$j] . " ";
		$title.="Min";
	        $title.="(" . $self->{"sensData"}->{"mmaUnits"}->[$j] . ")";
		
		$gnuplotCmd.=<<EOS
"$dataFilename" using 1:$i title '$title' $tmp, \\
	'' using 1:$i axes x1y2 notitle $tmp, \\
EOS
			 ;   
	    }		   

	    if(  ! defined($omit{$col}) &&
	        $self->{"options"}->{"refDoPlotMma"}->{"max"} ){
	        $hasPlots++;
        	$i++; # Next datafile column
  		$tmp=$mmaPlotFormat; $tmp=~s/##/$mmaLs/; $mmaLs++;
        	$title=$self->{"sensData"}->{"mmaNames"}->[$j] . " ";
        	$title.="Max";
	        $title.="(" . $self->{"sensData"}->{"mmaUnits"}->[$j] . ")";
        	$gnuplotCmd.=<<EOS
"$dataFilename" using 1:$i title '$title' $tmp, \\
	'' using 1:$i axes x1y2 notitle $tmp, \\
EOS
			 ;   
	    }		   
	    if( ! defined($omit{$col}) &&
	        $self->{"options"}->{"refDoPlotMma"}->{"avg"} ){
	        $hasPlots++;
        	$i++; # Next datafile column
  		$tmp=$mmaPlotFormat; $tmp=~s/##/$mmaLs/; $mmaLs++;
        	$title=$self->{"sensData"}->{"mmaNames"}->[$j] . " ";
        	$title.="Avg";
	        $title.="(" . $self->{"sensData"}->{"mmaUnits"}->[$j] . ")";
        	$gnuplotCmd.=<<EOS
"$dataFilename" using 1:$i title '$title' $tmp, \\
	'' using 1:$i axes x1y2 notitle $tmp, \\
EOS
			 ;   
	    }		   

	 }   

	 # Next thing to print is the list of MMA values for virtual sensors
	 # eg windchill
	 # This is very very slow: NOTE: Improve it
	 # $j iterates over the names of virtual Sensors, $k iterates over the
	 # names of resultvalues of one specific virtual sensor $j
	 foreach $j (sort(keys(%$virtSens))){
	    ($calcMin, $calcMax, $calcAvg)=split(/;/, $virtSens->{"$j"}->{"doPlotMma"});
	    if( $virtSens->{"$j"}->{"active"} ){
	       # Sort output key names of virt sensor to define a sequence for values
	       # that corresponds to the gnuplot file.
	       foreach $k (sort(keys(%{$self->{"results"}->{"virtSens"}->{"$j"}->{"$sensId"}->{"mma"}}))){
		  if( $calcMin ){
	              $hasPlots++;
          	      $i++; # Next datafile column
		      # Get unit Name for this mma value
		      $tmp1=$sensData->{"virtSens"}->{"$j"}->{"out"}->{"$k"};
		      # construct legend name: "Valuename Min (Unit)"
		      $tmp="$k Min ($tmp1)";
		      $tmp=$self->cleanupName($tmp);
   	              $tmp1=$mmaPlotFormat; $tmp1=~s/##/$mmaLs/; $mmaLs++;
          	      $gnuplotCmd.=<<EOS
"$dataFilename" using 1:$i title '$tmp' $tmp1, \\
	'' using 1:$i axes x1y2 notitle $tmp1, \\
EOS
			 ;   
		  }

		  if( $calcMax ){
	              $hasPlots++;
          	      $i++; # Next datafile column
		      $tmp1=$sensData->{"virtSens"}->{"$j"}->{"out"}->{"$k"};
		      $tmp="$k Max ($tmp1)";
		      $tmp=$self->cleanupName($tmp);
   	              $tmp1=$mmaPlotFormat; $tmp1=~s/##/$mmaLs/; $mmaLs++;
          	      $gnuplotCmd.=<<EOS
"$dataFilename" using 1:$i title '$tmp' $tmp1, \\
	'' using 1:$i axes x1y2 notitle $tmp1, \\
EOS
 		  ;   
		  }

		  if( $calcAvg ){
	              $hasPlots++;
          	      $i++; # Next datafile column
		      $tmp1=$sensData->{"virtSens"}->{"$j"}->{"out"}->{"$k"};
		      $tmp="$k Avg ($tmp1)";
		      $tmp=$self->cleanupName($tmp);
   	              $tmp1=$mmaPlotFormat; $tmp1=~s/##/$mmaLs/; $mmaLs++;
          	      $gnuplotCmd.=<<EOS
"$dataFilename" using 1:$i title '$tmp' $tmp1, \\
	'' using 1:$i axes x1y2 notitle $tmp1, \\
EOS
			 ;   
		  }
	       }
	    }
	 }
      }
   }else{  # Senstype is a WD Type:
     $sensId=$sensData->{"sensIds"}->[0];  # For WD only one sensor id is allowed

     $hasPlots++;
     
     # Create plot command for WD sensorplot (plot in polar mode)
     # The first valCol is expected to be the speed, the second the angle
     # that is the winddirection
     # Since the in gnuplot has 0 not at the North position and increasing 
     # angles rotate in the wron direction we have to add an offset and substract 
     # the result from 360 to get 0 as "North" position and 90 as "East" etc.
     $theSensName=$sensData->{"legendName"} . "(" .
		    $sensData->{"valUnits"}->[0] . ")";
		    #join( " ", @{$sensData->{"valNames"}}) . ")"  ;

     $theSensName=$self->cleanupName($theSensName);

     $sensCol=$sensData->{"valCols"}->[1];
     # Use the max of windspeed for scaling the wd graphics
     # In a wd graphics we allow only ONE sensor
     if( $self->{"results"}->{"$sensId"}->{"mma"}->{"speed"}->{"maxValue"} >
         $self->{"results"}->{"$sensId"}->{"mma"}->{"gustspeed"}->{"maxValue"}  ){
         
	    $l=$self->{"results"}->{"$sensId"}->{"mma"}->{"speed"}->{"maxValue"};
     }else{
	    $l=$self->{"results"}->{"$sensId"}->{"mma"}->{"gustspeed"}->{"maxValue"}
     }
     
     $l=int($l-$l%$tics)+$tics;   # Range rounded to 5,10,15,20,...
     $tmp=$sensData->{"valCols"}->[0];
     
     
     #warn join(", ", keys(%{$sensData}));
     $doGustSpeed=1;
     # For the winddirection sensor plot the user might want
     # to plot only wind direction not the windgust direction
     # If he does not want windgust he would have placed
     # a "omit"=>"windgustspeed" in the sensordefinition
     # below we search for this definition
     foreach $i (@{$sensData->{"omit"}}){
	$doGustSpeed=0 if( $i == "gustspeed" );
     }
     
     if( ! $doGustSpeed ){   # if true only plot wind direction
        $gnuplotCmd.=<<EOS
plot [0:360] [-$l:$l] [-$l:$l] "$dataFilename"  \\
using (int(360-\$$sensCol+90)%360):$tmp \\
title '$theSensName' with points pointtype 1
EOS
	;
     }else{    			# plot wind and windgust direction
        $nextSensCol=$sensCol+2; # Columns in datafile
        $nextTmp=$tmp+2;
        $theSensName1=$theSensName;
        $theSensName1=~s/Wind/B\366en/;
        # we plot gustspeed first, then windseed so the latter
        # physically overwrites the former larger values. This way
        # the smaller windspeed values are better visible
        $gnuplotCmd.=<<EOS
plot [0:360] [-$l:$l] [-$l:$l] \\
"$dataFilename" using (int(360-\$$nextSensCol +90)%360):$nextTmp \\
title '$theSensName1' with points pointtype 1, \\
"$dataFilename" using (int(360-\$$sensCol+90)%360):$tmp \\
title '$theSensName' with points pointtype 1
EOS
	;
     }
   }

   # Remove trailing ", \" 
   $gnuplotCmd=~s/, \\\s$//;	   
   
   print OUT $gnuplotComment, "plot " if( $sensType !~ /WD/i );
   print OUT $gnuplotCmd, "\n\n";
   close(OUT);
   
   #warn "Gnuplot: $gnuplotCmd \n";
   #print "hasPlots: $hasPlots\n";
   
   $self->{"results"}->{"gnuplotHasPlots"}=$hasPlots;
}



#
# Run gnuplot binary
#
sub runGnuplot{
   my($self)=shift;
   my($command, $ret, $conf, $bin, $virtual);
   my($dataFilename,$gnuplotFilename,$refSensorIds, $err);
      
   $dataFilename=$self->{"options"}->{"dataFilename"};
   $gnuplotFilename=$self->{"options"}->{"gnuplotFilename"};
   $bin=$self->{"options"}->{"gnuplotBinary"};   
   $refSensorIds=$self->{"sensObj"}->getSensIds($self->{"sensData"});
   	
   # Write data for sensor display to a file
   $err=$self->writeDataFile($refSensorIds, $self->{"sensObj"}, $self->{"sensData"},
	                    $dataFilename);  # Write datafile for gnuplot
   # Write gnuplot commands to another file
   $err|=$self->writeGnuplotFile($refSensorIds, $self->{"sensObj"}, $self->{"sensData"},
	                   $gnuplotFilename, $dataFilename);

   # writeGnuplotCmds() determined that there is nothing to plot.... ?
   if( ! $self->{"results"}->{"gnuplotHasPlots"} ){
   	$err|=1;
	$main::errMsg.="There is no data left to be plotted ...<br>\n";
	$ret=0;
   }else{
        $command="/bin/sh -c \"$bin  $gnuplotFilename \""; 
        $ret=system($command);
   }

   if( $ret/256 != 0 ){
   	die "Error \"$ret\" in system call: $command\n";
   }
   return( $err );
}


#
# Function that will write the results of the dbquery to a HTML page
#
sub runTextplot{
   my($self)=shift;
   my($sampleTime)=shift;
   
   my($refSensorIds)=$self->{"sensObj"}->getSensIds($self->{"sensData"});
   my($refSens)=$self->{"sensObj"};
   my($sensData)=$self->{"sensData"};

   my($i, $j, $k, $id, $value, @allOutCols, @allOutNames, $col, $virtSens, 
       @allOutUnits, $sensType, $dataCount, $tmp, $tmp1,
       $outNameToVirtname, $omitVirtual);
   my($refResult, $startDate, $startTime);
   my($numOutCols, $dataTab, $date, $time, $minDate, $minTime, $err,
      $maxDate, $maxTime, $header, $firstHeader, $numOrigOutCol, @tmp);
   
   $omitVirtual=0;
   # If we display minima or maxima of day week or year basis
   # we do not want to display virtual sensors since they are
   # calculated from the eg days minima. Think of dewpoint and then
   # take the minimal humidity of the day and the minimal temp 
   # of the day and calculate dewpoint thereof. The result is not
   # what you want. Since in reality the min hum and temp did not occure at
   # the same time. 
   $err=0;
   if( $sampleTime =~ /^.+,Min/ || $sampleTime =~ /^.+,Max/ ){
	$omitVirtual=1; 
	$err=1;
	$main::errMsg.="When displaying minima or maxima values for " .
	    "days, weeks, months or years no virtual sensors will be displayed. <br>";
	$omitVirtual=1; 
   }

   # Prepare handling of rain sensor and light sensor
   $sensType=$sensData->{"sensType"};
   
   @allOutCols=@{$refSens->getAllOutCols($sensData)};
   @allOutNames=@{$refSens->getAllOutNames($sensData)};
   @allOutUnits=@{$refSens->getAllOutUnits($sensData)};
   # Note number of entries is alloutCols. This is done to identify
   # the extra columns added below
   $numOrigOutCol=$#allOutCols;
   #
   push(@allOutCols, @{$refSens->getExtraCols($sensData)});
   push(@allOutNames, @{$refSens->getExtraNames($sensData)});
   push(@allOutUnits, @{$refSens->getExtraUnits($sensData)});

   $outNameToVirtname=$refSens->getOutNameToVirtname($sensData);
   $virtSens=$self->{"sensObj"}->getVirtSensors($self->{"sensData"});   

   # Replace colname datetime by "loctime" because of local time management in sql
   # routines and remove tablename from strings like th_sensors.H  (=> H)
   $j=0;
   while($j <= $#allOutCols){
	if($allOutCols[$j] =~/datetime/ ){
	   $allOutCols[$j]=~s/datetime/loctime/o;
	}else{
	    $allOutCols[$j]=~s/^[^.]*\.//o;
	} 
	# Correct number of output columns for virtual sensors that shall not
	# be displayed due to display mode Min Max
        if( $omitVirtual && 
	       defined($outNameToVirtname->{$allOutCols[$j]}) ){
	   splice(@allOutCols, $j, 1);# omit column
	   splice(@allOutUnits, $j, 1);# omit column
	   splice(@allOutNames, $j, 1);# omit column
	}else{
	   $j++;
	}	
   }

   # Get the number of columns to be printed
   $numOutCols=$#allOutCols + 1;
   
   
   # Construct table header with column names
   $firstHeader="<THEAD><TR><TH class=\"sensTextTabHeader\">Sensor:</TH> " .
         "<TH class=\"sensTextTabHeader\">Nr:</TH>";
   $header="<TR><TD class=\"sensRowHeaderTextTab\">Sensor:</TD> " .
         "<TD class=\"sensRowHeaderTexttab\">Nr:</TD>";

   for($i=0; $i<$numOutCols; $i++){
   	$j=$allOutNames[$i];
	$j=~s/Date/Datum/o;
   	$header.="<TD class=\"sensRowHeaderTextTab\">". $j. ":" . "</TD>";
	$firstHeader.="<TH class=\"sensTextTabHeader\">". $j. ":". "</TH>";
   }
   
   $firstHeader.="</TR></THEAD>";
   $header.="</TR>";
   
   $numOutCols+=2;  # one more for  SensorName and one more for counter number
      
   # Iterate over all sensors ids defined
   for($k=0; $k<= $#{$refSensorIds}; $k++){
        $dataTab=simpleTable->new({"cols"=>"$numOutCols", "auto"=>"1"},  
                     'border="1" cellspacing="1" cellpadding="5" ', 
		     "$firstHeader");
        $dataTab->startTable(0, 0);   
      
        # Get number of datasets for each sensorid of the current sensor. 
        $dataCount=$#{$self->{"results"}->{$refSensorIds->[$k]}->{"sqlData"}} ;

	# Iterate over all existing datasets 
        for($i=0; $i <= $dataCount; $i++ ){	   
	   $dataTab->openRow(); # New row but *no* new column
	   $id=$refSensorIds->[$k];
	   $refResult=$self->{"results"}->{"$id"}->{"sqlData"}; # Results of sql query (the data)
	   # Use sensor name from database if possible
	   $sensorName=$sensData->{"sensorDbNames"}->["$id"];      
	   $sensorName="(id: $id)" if( !length($sensorName) );

           # Name of sensor
	   if( ! ($i %25) ){
	       print "$header\n" if( $i );	        
	       $dataTab->newCol(0,"class=\"sensRowHeaderTextTab\" ");
	       print $sensorName;
	   }else{

	   $dataTab->newCol(0,"class=\"sensRowHeaderTextTab\" ");
	       print " ";
	   }
	   $dataTab->newCol(0,"class=\"sensTextTab\"");
	   print $i+1;
	   
           # Now print all wanted colums. Names are in $allOutCols
	   for($j=0; $j <= $#allOutCols; $j++){
		   # If virtual sensors should be omitted we check if current
		   # col is from a virtual one (see also above)
		   next if( $omitVirtual && 
		            defined($outNameToVirtname->{$allOutCols[$j]}) );
		   # Value to be printed
		   $value=$refResult->[$i]->{$allOutCols[$j]};
		   # Get the minimum and maximum of the current column
		   # We have to distinguish betwenn real sensors and virtual ones
		   # because teh MMA values of real ones are store in a different place than 
		   # those of virtual ones.
		   $tmp=$allOutCols[$j];
		   $virtual=0;
		   # Real:
        	   if( defined($self->{"results"}->{$id}->{"mma"}->{"$tmp"}->{"minValue"}) ||
		       defined($self->{"results"}->{$id}->{"mma"}->{"$tmp"}->{"maxValue"}) ){
		      $min=$self->{"results"}->{$id}->{"mma"}->{"$tmp"}->{"minValue"};
        	      $max=$self->{"results"}->{$id}->{"mma"}->{"$tmp"}->{"maxValue"};
		   # virtual:
		   }else{
		      # Get name of virtual sensor
		      $tmp=$allOutCols[$j];      	# Out column name
		      $tmp1=$outNameToVirtname->{$tmp};	# Name of virt sensor
		      # Look if we have Min/Max/Avg values for this virtual sensor
		      if( defined($self->{"results"}->{"virtSens"}->{"$tmp1"}->{"$id"}->{"mma"}->{"$tmp"}) ){
		      	$min=$self->{"results"}->{"virtSens"}->{"$tmp1"}->{"$id"}->{"mma"}->{"$tmp"}->{"minValue"};
		      	$max=$self->{"results"}->{"virtSens"}->{"$tmp1"}->{"$id"}->{"mma"}->{"$tmp"}->{"maxValue"};

			$virtual=1;
		      }
		   }
		   
		   # Handle rain or LD sensordata column diff which
		   # has to be multiplied by a factor
		   $value*=$sensData->{"unitfactor"}->{$allOutCols[$j]} 
		       if( ( $sensType =~ /RA/o || $sensType =~ /LD/o ) && 
		           ( $allOutCols[$j] ne "loctime" ) &&
		           defined($sensData->{"unitfactor"}->{$allOutCols[$j]}) );
		   
		   # Now handle Light sensor where real value has to be multiplied by factor value
		   $value*=$refResult->[$i]->{"factor"} 
		             if( $sensType =~ /LI/o && $allOutCols[$j] ne "loctime" );
			     

		   if( ($sampleTime=~/^0/o) &&
		       ($value == $min) && ($sensData->{"mmaHasMin"} ne 0) ){
		       $dataTab->newCol(0,"class=\"sensTextTabMin\"");
		   # The rain sensor has a maximum based on hours not on data samples
		   }elsif( ($sampleTime=~/^0/o || ($sampleTime=~/^h/o && 
		           ($sensType =~ /RA/o || $sensType =~ /LD/o ) )) && 
		            $value == $max ){
		       $dataTab->newCol(0,"class=\"sensTextTabMax\"");
		   }else{
		       if( $virtual ){   # A virtual sensors column
		          $dataTab->newCol(0,"class=\"sensVirtTextTab\"");
		       }else{
		          if( $j > $numOrigOutCol ){ # an extra Colum (see extraCols aove)
			     $dataTab->newCol(0,"class=\"sensExtraTextTab\"");
			  }else{
			     $dataTab->newCol(0,"class=\"sensTextTab\"");
			  }
		       }
		   }
		   
		   # Reformat datetime column
		   # if column is datetime col
		   if( $allOutCols[$j] eq "loctime" ){
		      ($date, $time)=split(/\s*\t\s*/, $value);
		      @tmp=split(/-/, $date );
		      $value="$tmp[2]-$tmp[1]-$tmp[0] $time";
		   }else{ 
		      # add unit symbols to value
		      $value .= " " . $allOutUnits[$j];
		   }
		   
		   #print "allOutCols:", $allOutCols[$j], " -> ", $value, "\t"; 
		   
		   print $value, "\t";
	   }
	   print "\n";
	}
	$dataTab->endTable();
	print "<hr><br><hr><br><hr>\n" if( $i <= $dataCount );
	print "\n";
   }  

   # Print Legend only if we have raw data. When showing average Data or Min /max data
   # we do not have the min/max values of these data but only the data itself
   if( $sampleTime=~/^0/o ){

      print "<p class=\"sensTextTab\">Legende:<BR>";
      $dataTab=simpleTable->new({"cols"=>"2", "auto"=>"1"},  
                	'border="0" cellspacing="1" cellpadding="5" ', "");
      $dataTab->startTable(0, 0);
      $dataTab->newCol(0,"class=\"sensTextTabMin\"");
      print "\&nbsp;\&nbsp;";
      $dataTab->newCol();  print "<FONT size=-2>Min</FONT>";   
      $dataTab->newCol(0,"class=\"sensTextTabMax\"");
      print "\&nbsp;\&nbsp;";   
      $dataTab->newCol();  print "<FONT size=-2>Max</FONT>";   
      $dataTab->endTable();
      print "<hr>\n";
   }
   return($err);   
}


#
# Unlink unneeded temporary data
#
sub unlinkTmpData{
   my($self)=shift;
   my($refSensorIds,$id,$refResult, $k);
   
   #return;
   
   unlink($self->{"options"}->{"gnuplotFilename"});
   unlink($self->{"options"}->{"dataFilename"});
   
   $refSensorIds=$self->{"sensObj"}->getSensIds($self->{"sensData"});

   # Free memory taken by sql query results
   for($k=0; $k<= $#{$refSensorIds}; $k++){
	   $id=$refSensorIds->[$k];
	   $refResult=$self->{"results"}->{"$id"}->{"sqlData"}; # Results of sql query (the data)
	   undef @{$refResults};
   }	   
}


# 
# Create the gnuplot config file for all the sensors
#
sub writeGnuplotFile{
   my $self=shift;
   my($refSensorIds)=shift;
   my $sensObj=shift;
   my $sensData=shift;
   my $gnuplotFile=shift;
   my $dataFile=shift;
   my($tics);
   
   # Write static header information into gnuplot file
   $tics=$self->writeGnuplotHeader($sensData, $gnuplotFile, $refSensorIds);	
   
   # Next write dynamic sensor dependent information into gnuplot file
   return( $self->writeGnuplotCmds($refSensorIds, $sensObj, $sensData, $gnuplotFile, $dataFile, $tics)
                  );
}


#
# Function that will write the results of the dbquery and the virtual sensor
# calculation into a file for gnuplot.
#
sub writeDataFile{
   my($self)=shift;
   my($refSensorIds)=shift;
   my($refSens)=shift;
   my($sensData)=shift;
   my($filename)=shift;
   my($i, $j, $k, $oldid, $id, $value, $allOutCols, $col, $virtSens, $unitfactor, $sensType, $dataCount);
   my($calcMin, $calcMax, $calcAvg, $colCount);
   my($refResult, $startDate, $startTime, @virtSensKeys);
   my($sampleTime, $outNameToVirtname, $omitVirtual, $err);
   my($dateRef, $equal, @curRowIdx, $oldCount,$foundEqualRow, $loctimePrinted);
   
   # Current display Mode (real Data, average, min/max, ...)
   $sampleTime=$self->{"options"}->{"sampleTime"};
   
   $omitVirtual=0;
   # If we display minima or maxima of day week or year basis
   # we do not want to display virtual sensors since they are
   # calculated from the eg days minima. Think of dewpoint and then
   # take the minimal humidity of the day and the minimal temp 
   # of the day and calculate dewpoint thereof. The result is not
   # what you want. Since in reality the min hum and temp did not occure at
   # the same time. 
   if( $sampleTime =~ /^.+,Min/ || $sampleTime =~ /^.+,Max/ ){
   	$err=1;
	$main::errMsg.="When displaying minima or maxima values for " .
	    "days, weeks, months or years no virtual sensors will be displayed. <br>";
	$omitVirtual=1; 
   }

   # Get mapping between name of output column and virtual sensor name
   # We use this to determine which outname is a virtual one
   $outNameToVirtname=$refSens->getOutNameToVirtname($sensData);

   # Prepare handling of rain sensor and light sensor
   $sensType=$sensData->{"sensType"};
   
   # Get the start date and time and convert it to local time. Needed below 
   # in case there are no data. See ***1
   $startDate=$self->{"options"}->{"correctedStartDate"};
   $startTime=$self->{"options"}->{"correctedStartTime"};
   ($startDate, $startTime)=main::timeConvert($startDate, $startTime, "LOC");
      
   open( OUT, ">$filename")|| die "Cannot open data file  \"$filename\" for writing. Abort.\n";
   
   $allOutCols=$refSens->getAllOutCols($sensData);
   $virtSens=$self->{"sensObj"}->getVirtSensors($self->{"sensData"});   
   @virtSensKeys=sort(keys(%$virtSens));
   
   # Replace colname datetime by "loctime" because of local time management in sql
   # routines and remove tablename from strings like th_sensors.H  (=> H)
   for($j=0; $j <= $#{$allOutCols}; $j++){
	if($allOutCols->[$j] =~/datetime/ ){
	   $allOutCols->[$j]=~s/datetime/loctime/o;
	}else{
	    $allOutCols->[$j]=~s/^[^.]*\.//o;
	}  
   }
   
   # Ref to a hash with all date entries of all sensorsids of the current sensor type
   # This hash has been setup in mkDateList(). 
   $dateRef=$self->{"results"}->{$refSensorIds->[0]}->{"allDateEntries"};
   ###$equal=$self->{"results"}->{$refSensorIds->[0]}->{"dataNumberEqual"};
   
   $dataCount=0;
   
   # Index pointer for each sensorid pointing to current output row
   for($k=0; $k<= $#{$refSensorIds}; $k++){
      $curRowIdx[$k]=0;
   }
   
   #$refResult=$self->{"results"}->{$refSensorIds->[0]}->{"sqlData"}; # Results of sql query (the data)
   #$dataCount=$#{@$refResult};
   #for($i=0; $i<= $#{@$refResult}; $i++){
   #	print $refResult->[$i]->{"loctime"}, " Id: ", $refSensorIds->[0], "<br>";
   #}
   
   $colCount=$#{$allOutCols};
   # Iterate over all existing datasets 
   # The iteration is on all date entries of all the data arrays of all  eg th sensors to be displayed
   # in the graphics to be diplayed. Because not all of the data arrays have the same size (eg if one
   # of the th-sensors was added later than another) and thus not not each array has all the 
   # date entries in $dateRef (see mkDateList() )we need and index for each sensid pointing 
   # to the current data row  retrieved from the database. This is @curRowIdx
   $cc=0;
   foreach $i (sort(keys(%$dateRef))){
         $cc++;
   	#
	# Iterate over all sensor ids to be printed
	$oldid=-1;
	$loctimePrinted=0;
	#print "<br><br>New Row (date: $i)...\n";
	do{  # Actually it should be that each row of sql-data  has a different 
	     # date. So we would not need this do..while loop. But because of 
	     # problems in GMT-Local time conversions it may happen that there 
	     # are two or more entries. Without the loop the display would end with the
	     # first dataset that has a date equal to $i. With this loop we process
	     # all sensor datasets with a date equal to $i
	   $foundEqualRow=0;
	   for($k=0; $k<= $#{$refSensorIds}; $k++){
	      $id=$refSensorIds->[$k];
	      #print "<br>Id = $id\n";
	      $refResult=$self->{"results"}->{"$id"}->{"sqlData"}; # Results of sql query (the data)

	      # Check if sensor "$k"'s data row "$curRowIdx[$k]" has data for date "$i"
	      #print $i, ", " ,$refResult->[$curRowIdx[$k]]->{"loctime"}, ": $k, $curRowIdx[$k] <br>\n";
	      $oldCount=$dataCount;
	      # Now check if the current date ($i) is equal to the current sensors data row.
	      if( $refResult->[$curRowIdx[$k]]->{"loctime"} eq $i ){   
	            $foundEqualRow=1;  # We found a matching row
		    ##print "Equal: $i, k: $k <br>\n";
        	    # Now print all wanted colums. Names are in $allOutCols
		    for($j=0; $j <= $colCount; $j++){
			    # If virtual sensors should be omitted we check if current
			    # col is from a virtual one (see also above)
			    next if( $omitVirtual && 
		        	     defined($outNameToVirtname->{$allOutCols->[$j]}) );
			    # If we just do not work on the first sensor id we omit the datetime field since
			    # this should be printed only once to the output file in the first column.
			    if( $allOutCols->[$j] eq "loctime" ){
			    	next if( $loctimePrinted );
			    	$loctimePrinted=1; 
			    }
        
        		    #print "<br>OutputColumn: ", $allOutCols->[$j], ", ";
			    #
			    # Print all data values named in $allOutCols defined in $refResult

			    $value=$refResult->[$curRowIdx[$k]]->{$allOutCols->[$j]};

			    # If rain sensor or other sens with unit factor apply this factor to 
			    # value. Do not do this for loctime column (first one) only for data columns
                	    $unitfactor=$sensData->{"unitfactor"}->{$allOutCols->[$j]}?
		        	    $sensData->{"unitfactor"}->{$allOutCols->[$j]}:0;

			    if( $unitfactor && $allOutCols->[$j] && $j){
		   			    $value*=$unitfactor;
		   	        	    $value=main::round($value, 2);
			    }

			    # Now handle Light sensor where real value has to be multiplied by factor value
			    $value*=$refResult->[$curRowIdx[$k]]->{"factor"} 
		        	      if( $sensType =~ /LI/o && $allOutCols->[$j] ne "loctime" );

			    #print "allOutCols:", $allOutCols->[$j], " -> ", $value, "\t"; 

			    print OUT $value, "\t";
			    #print "V: ",$value, ",";
             		    $dataCount++;

		    }
		    # increase pointer into data array of sensor with index $k in the list of 
		    # sensors to be printed
		    $curRowIdx[$k]++;
		    # print "\n";
	      }else{
	   	   print "\t";  # Value is undefined
	   	   #print "V: undef, ";
	      }   

	      # print MMA values of standard sensors
	      # Iterate over all MMA db cols for one sensor
	      # e.g. the MMA values for "T" and "H" of a th_sensor with id $sensId
              for($j=0; $j<= $#{$self->{"sensData"}->{"mmaDBCol"}}; $j++) {
		 $col=$self->{"sensData"}->{"mmaDBCol"}->[$j];
   		 print  OUT $self->{"results"}->{"$id"}->{"mma"}->{"$col"}->{"minValue"}, "\t"
	   	      if( $self->{"options"}->{"refDoPlotMma"}->{"min"} );

		 print  OUT $self->{"results"}->{"$id"}->{"mma"}->{"$col"}->{"maxValue"}, "\t"    
	   	      if( $self->{"options"}->{"refDoPlotMma"}->{"max"} );

		 print  OUT $self->{"results"}->{"$id"}->{"mma"}->{"$col"}->{"avgValue"}, "\t"    
	   	      if( $self->{"options"}->{"refDoPlotMma"}->{"avg"} );
	      }   

	      # Next thing to print is the list of MMA values for virtual sensors
	      # eg windchill
	      # The data values have been printed already above since they are contained in 
	      # allOutCols...
      	      # This is very slow: NOTE: Improve it
	      # $j iterates over the names of virtual Sensors, $k iterates over the
	      # names of resultvalues of one specific virtual sensor $j
	      # Depending on "refDoPlotMma" we print  any of Min/Max/AVG values
	      foreach $j (@virtSensKeys){
		 if( $virtSens->{"$j"}->{"active"} ){
		    # Print MMA values.......
		    ($calcMin, $calcMax, $calcAvg)=split(/;/o, $virtSens->{"$j"}->{"doPlotMma"});
		    # Sort output key names of virt sensor to define a sequence for values
		    # that corresponds to the gnuplot file.
		    foreach $k (sort(keys(%{$self->{"results"}->{"virtSens"}->{"$j"}->{"$id"}->{"mma"}}))){
	               print OUT $self->{"results"}->{"virtSens"}->{"$j"}->{"$id"}->{"mma"}->{"$k"}->{"minValue"}, "\t"
	   		     if( $calcMin );

	               print OUT $self->{"results"}->{"virtSens"}->{"$j"}->{"$id"}->{"mma"}->{"$k"}->{"maxValue"}, "\t"
	   		     if( $calcMax );
	               print OUT $self->{"results"}->{"virtSens"}->{"$j"}->{"$id"}->{"mma"}->{"$k"}->{"avgValue"}, "\t"
	   		     if( $calcAvg );
		    }
		 }
	      }
	   }# for $k
        }while( $foundEqualRow ); 
	
	print OUT "\n";
 	#print $i, keys(%{$refResult->[$i]}), "\n";
   }# foreach  
   # ***1
   # If there are no datasets for the sensor in the specified time range
   # we have to fake at least one dataset else gnuplot will throw out a dirty error message
   # that all points are undefined.
   if( $dataCount <= 0 ){
   	print OUT "$startDate\t$startTime\t0\t0\t0\t0\t0\t0\t0\t\n";
   }

   close(OUT);
   return($err);
}


#
# Function that applies all virtual sensors to the base data extracted 
# from the database. For each sensor it will add additional fields into the result 
# hash. This function needs the hash with the database data as input which was
# created by  getDataFromDb(). The structure of this hash is
# like DBI::selectall_hashref() returns it.
#
sub applyVirtSensors{
   my($self)=shift;
   my($sensId)=shift;
   my($refResult)=shift;
   my($i, $j, $virtSensors);
   
   $virtSensors=$self->{"sensObj"}->getVirtSensors($self->{"sensData"});
    #foreach  $j (keys(%$refResult)){   # Handle all datasets
   
   foreach $i (sort(keys(%$virtSensors))){     # Handle all virtual Sensors
      if( $virtSensors->{"$i"}->{"active"} ) {
	 $j=$virtSensors->{"$i"}->{"function"};    # Function name 
	 
	 # Call virtSensor function
	 # Enter MMA-Values in $self->{"results"}->{"virtSens"}->{"mma"}->{<valName>}
	 $self->{"results"}->{"virtSens"}->{"$i"}->{"$sensId"}->{"mma"}={};

	 $refResult=$self->{"sensObj"}->$j( $i, $self->{"sensData"}, $refResult, 
	 				    $self->{"results"}->{"virtSens"}->{"$i"}->{"$sensId"}->{"mma"}, 
					    $virtSensors->{"$i"}->{"doCalcMma"} );  
      }
   } 
   return($refResult);
}


#
# This function runs a SQL staement to fetch data drom the datase for
# one sensor (to be exact: for exactly one sensorId of one sensor)
# The data is returned in a hash
#
sub getDataFromDb{
   my($self)=shift;
   my($sensId)=shift;
   my($sql, $refResult, $dbh, $sth, $i);
   
   $sql=$self->{"results"}->{"$sensId"}->{"sql"}; # SQL to execute

   $dbh=$self->{"localDbh"};
	
   # get Data  (was: $refResult=$dbh->selectall_hashref($sql, "loctime"); )
   # We need to supply a certain order for the resulting rows of the sql query
   # this is done by $i
   # warn "*** $sql\n";
   $i=0;
   $sth = $dbh->prepare($sql);
   $sth->execute();
   
   while( $refResult->[$i++] = $sth->fetchrow_hashref() ){}
   
   pop(@{$refResult}); # Pop last empty element.
   
   #for($i=0; $i <= $#$refResult; $i++){
   #	print "$i, ", keys(%{$refResult->[$i]}), "\n";
   #}
   #die;
   
   return($refResult);  
}


#
# Construct the sql commnads for all sensorids of one sensor
# using buildOneIdSqlCommand()
#
sub buildAllSqlCommands{
   my($self)=shift;
   my($i, $id, $refSensorIds, $stationIdSql);

   $refSensorIds=$self->{"sensObj"}->getSensIds($self->{"sensData"});
   $stationIdSql=$self->{"sensData"}->{"stationIdSql"};
   
   # Iterate over all sensorIds of one sensortype, eg all
   # th_sensors
   for($i=0; $i<= $#{$refSensorIds}; $i++){
   	#warn "* $i \n";
        $id=$refSensorIds->[$i];
	$self->buildOneIdSqlCommand($id, $stationIdSql);
   }
}


#
# Construct a sql command string to retrieve the sensor information wanted
# This function creates the sql command different in case a sampleTime value
# has been given, so that not each single value is extracted from the database 
# but eg one (average) value a day or week, month, year.
#
sub buildOneIdSqlCommand{
   my($self)=shift;
   my($sensId)=shift;
   my($stationIdSql)=shift;
   my($i, $j, $k, $sql, $date, $tmp);    
   my( $sqlDateZone, $sqlDateZone1, $startYear, $endYear );
   my($defaultTime)="00:00:00"; # Start of day for average values 
   				# if $sampleTime ne "0"
   my($defaultMinSec)=":00:00";  # same but without hour				

   my( $sampleTime, $refDbcols, $factor, $tableName, $currTable,
       $tableCount, $firstTable, $dstRange,
       $startDate, $startTime, $endDate, $endTime, $deltaIsDst, $deltaNoDst );
   
   $k=$self->{"sensObj"};
   # Calculate all the input and output db columns for this sensor
   # this is done by sensDisplayData::calcInputOutputCols()
   $k->calcInputOutputCols($self->{"sensData"});

   $sampleTime=$self->{"options"}->{"sampleTime"};
   $factor=$k->getFactor($self->{"sensData"});
   $refDbcols=$k->getAllInCols($self->{"sensData"});
   $startDate=$self->{"options"}->{"correctedStartDate"};
   $endDate=$self->{"options"}->{"correctedEndDate"};
   $startTime=$self->{"options"}->{"correctedStartTime"};
   $endTime=$self->{"options"}->{"correctedEndTime"};
   $dstRange=$self->{"dstRange"};
   $tableName=$refDbcols->[0];  
   $tableName=~s/\..*$//; 	# Tablename of first column needed.
   

   #die ">$sampleTime;$factor;$refDbCols;$startDate;$endDate;$startTime;$endTime\n";     
   # $sampleTime may be "d", "w", "m", "y" or "0". For the rain sensor it 
   # may additionally contain a "S" (upper case S) to indicate that for this
   # sensor we want to calculate the sums not average values.
   # If it is "0" all
   # existing vals from the db are requested, else only one average value
   # in each sample period (day, week, month or year).
   # if ne "0", so data are at least average values on daily basis
   # we replace the time db col value (not the date value) by a default time to
   # be written to the output (e.g. 12:00:00):

   # sqlDateZone1 is like $sqlDateZone but no $defaultTime instead the real rows date
   # sqlDateZone1 is used for normal display, sqlDateZone for
   # the case where $sampleTime != 0 
   ($sqlDateZone,$sqlDateZone1)=main::sqlGmtToLoc($startDate,$endDate, $tableName, $dstRange, 
                                                  $defaultTime);


   # If we want an average/Min/Max about hours we need to reformat $sqlDateZone
   # so that the date format is like <date> <Hour>:00:00   
   # sqldateZone1 does not matter in this case because if
   # $sampleTime contains a "h", we always display average/Min/max
   # values but no real values, the only thing that sqlDateZine1 
   # is used for.
   if( $sampleTime =~ /^[h]/o ){
      $sqlDateZone=~s/$defaultTime/%H$defaultMinSec/go;
      $sql.="$sqlDateZone";
      $sql.=" AS loctime";

   }	       
   
   #
   # Build up sql string for sensor to display like
   #"select datetime,T,H from th_sensors WHERE sensid=$i ORDER BY date, time;";
   $sql="SELECT ";
   $tableName="";
   for($j=0; $j<=$#{$refDbcols}; $j++){
      #warn "++ $j: ", $refDbcols->[$j], "\n";
      $k=$refDbcols->[$j];
      $k=~s/\..*$//;  # Remove columname form gt th_sensors.datetime
      $currTable=$k;
      if( $k !~ $tableName ){
	 if( !length($tableName) ){
      	     $tableName.="$k";
	     $tableCount=1;
	     $firstTable=$k;
	 }else{
      	     $tableName.=",$k";      	
	     $tableCount++;
	 }
      }
      # if $sampleTime !=0 we need to calculate Average values and not use
      # the raw data.  For the rain sensor $sampleTime 
      # may additionally contain a "S" (upper case S) to indicate that for this
      # sensor we want to calculate the sums not average values.
      if( $sampleTime=~/^0/o ){
	  if( ${$refDbcols}[$j] =~ /datetime/io  ){
	  	# Have mysql convert GMT to local time. Be aware, that 
		# gnuplot wants date and time in two cols seperated by tab
		# hence we use the sql DATE_FORMAT function here
	  	#$sql.=" DATE_FORMAT(datetime, \"%Y-%m-%d\\t%T\")";
	  	$sql.=" $sqlDateZone1 AS loctime";
	  }else{
	     $sql.=", " if( $j != 0); 
             $sql.= ${$refDbcols}[$j];
	  }    
      }else{
	    # take care of date handling for month and year for "date" col
	    if( ${$refDbcols}[$j] =~ /datetime/io  ){
	       if($sampleTime =~ /^[my]/o ){
		 $sql.=", " if( $j != 0); 
     		 # Because we take only the left 7 or 4 chars from date there is no 
		 # time field  in the output, so add a default one
		 if( $sampleTime =~ /^m/o ){
		     $tmp="-01\t$defaultTime";
		     $sql.="concat(LEFT($sqlDateZone,7),'$tmp') as loctime";
		 }elsif($sampleTime =~ /^y/o ){
		     $tmp="-01-01\t$defaultTime";
		     $sql .="concat(LEFT($sqlDateZone,4), '$tmp') as loctime";
		 }
	       }
	       if( $sampleTime =~ /^[hdw]/o ){
	    	  #$sql.="DATE_FORMAT(datetime,";
		  # The Time  field is here generated implicitly by "\t$defaultTime"
		  #$sql.=" \"%Y-%m-%d\\t\'$defaultTime\'\") AS datetime";	
		  #$sql.=" \"%Y-%m-%d\\t%T\") AS datetime";	
		  $sql.="$sqlDateZone";
		  $sql.=" AS loctime";
		  
	       }	       
	    }elsif( ${$refDbcols}[$j] !~ /time/io  ){ # !~ time && !~ date
		$sql.=", " if( $j != 0); 
		if( $sampleTime=~/[a-z]*S/o ){
		      $tmp=${$refDbcols}[$j];
		      $tmp=~s/$currTable\.//;
		      $tmp="`$tmp`" if( $tmp eq "range" );
	 	      $sql.="SUM(${$refDbcols}[$j]) AS $tmp";
		}else{
		   # Evaluate the $sampleDataType part in $sampleTime which start with a 
		   # ",". $sampletime looks like eg: "d,Avg"
 		   #
		   # Because we use names to refer to data in a perhash later we need
		   # to adapt the column names from eg AVG(th_sensors.T) to T
		   $tmp=${$refDbcols}[$j];
		   $tmp=~s/$currTable\.//;
		   $tmp="`$tmp`" if( $tmp eq "range" );
		   #
		   if( $sampleTime =~ /^.*,Avg/io ){
		       $sql.="AVG(${$refDbcols}[$j]) AS $tmp";
		   }elsif( $sampleTime =~ /^.*,Min/io ){
		       $sql.="MIN(${$refDbcols}[$j]) AS $tmp";
		   }elsif( $sampleTime =~ /^.*,Max/io ){
		       $sql.="MAX(${$refDbcols}[$j]) AS $tmp";
		   }else{
		      die "*** Illegal format for SampleTime: $sampleTime \n";
		   }	
		} 
	    }
     }#end of else
   }#for

   $sql.= " FROM $tableName WHERE ";
   
   # Add the join condition to sql statement when there are more 
   # than one tables involed. We join on the datetime column.
   # Result is like th_sensors.datetime=wind.datetime AND th_sensors.datetime
   # = rain.datetime
   $k="";
   foreach $i (split(/,/, $tableName)){
     if( $i !~ /$firstTable/ ){
	if( !length($k) ){
		$k="$firstTable.datetime = $i.datetime AND $firstTable.stationid = $i.stationid";
	}else{
		$k.=" AND $firstTable.datetime = $i.datetime AND $firstTable.stationid = $i.stationid";
	}
     }
   }
   $k.=" AND " if( length($k) );
   $sql.= "$k $firstTable.sensid=" . $sensId . " ";
   # $stationIdSql is formed like: statioid = 2 OR stationid = 5 ...
   # Here we need table names inside, so we replace stationid by $table.stationid
   $tmp=$stationIdSql; 
   $tmp=~s/stationid/$firstTable.stationid/g;
   $sql.= "AND $tmp AND $firstTable.datetime >= \"$startDate $startTime\" AND $firstTable.datetime <= \"$endDate $endTime\"";

   # Now add "group by" sql directives for the date field. dates have to 
   # be in the formt yyyy-mm-dd in order for this to work.
   # By adding "group by" and the above AVG command we let the database
   # calculate average values for all rows for each day or week etc
   # So the result of this sql command is a series of average values
   # one for eg all data rows of each day of data in the db.
   if( $sampleTime=~/^[dh]/o ){		# one data value for each day
       $sql.=" GROUP BY loctime";
   }elsif( $sampleTime=~/^m/o ){	# one data value for each month
       $sql.=" GROUP BY LEFT($sqlDateZone, 7)";
   }elsif( $sampleTime=~/^y/o ){	# one data value for each year
       $sql.=" GROUP BY LEFT($sqlDateZone, 4)";
   }elsif( $sampleTime=~/^w/o ){	# one data value for each week
       $sql.=" GROUP BY CONCAT(YEAR($sqlDateZone), '-', WEEK($sqlDateZone))";   
   }   

   #$sql.= " ORDER BY $firstTable.datetime ";
   $sql.= " ORDER BY loctime ";
   
   # Enter resulting sql query string into object using the sensorId 
   # as an index
   $self->{"results"}->{"$sensId"}->{"sql"}=$sql;
   
   #print "* $sql <br> \n";
   #warn "\n*** $sampleTime\n sql: $sql \n";
   return($sql);
}


#
# Determine Minimum, Maximum and average value for each sensorid of one sensor type
#
sub getMmaValues{
   my($self)=shift;
   
   my($dbh, $startDate, $startTime, $endDate, $endTime);
   my ($sqlTot, $sqlAvg, $sqlMin, $sqlMax, $tmp, $i, $j, $k, @res);
   my($tmp1, $tmp2, $days, $hours, $minutes, $sec);
   my(%omit);
   my($refSensorIds, $tableName, $unitFactor, $sens, $stationIdSql);
   
   $startDate=$self->{"options"}->{"mmaStartDate"};
   $startTime=$self->{"options"}->{"mmaStartTime"};
   $endDate=$self->{"options"}->{"mmaEndDate"};
   $endTime=$self->{"options"}->{"mmaEndTime"};
   $dbh=$self->{"localDbh"};
   $sens=$self->{"sensData"};
   $stationIdSql=$sens->{"stationIdSql"};

   # Get number of hours between start end enDdate
   # Used to calculate the average rain fall/h
   ($days, $hours, $minutes, $sec) 
           =main::Delta_DHMS(split(/-/o, $startDate) , split(/:/o, $startTime), 
                       split(/-/o, $endDate) , split(/:/o, $endTime)  );
   $hours=$days*24+$hours+ int(($minutes+1)/60);

   $refSensorIds=$self->{"sensObj"}->getSensIds($self->{"sensData"});
   $tableName=$self->{"sensData"}->{"tableName"};  
   
   # Build up hash with column names to omit from @mmaOmit 
   foreach $i (@{$sens->{"mmaOmit"}}){
   	$omit{$i}=1;
   }
   # iterate over all sensors given in %sensors
   foreach $i (@$refSensorIds){   # iterate over all sensIds of this sensor
      foreach $j (@{$self->{"sensData"}->{"mmaDBCol"}}) { # Iterate over all MMA db cols
         next if( $omit{$j} );
	 $j="`$j`" if( $j eq "range" ); # range is a keyword in MYSQL >= 5.1 so quote it to `range`
	 if( $main::useSqlSubQueries ){ # Global variable
	    # We may use subqueries for Min and Max. This is faster on
	    # MYSQL server >= 5.0
	    $sqlAvg="SELECT AVG(" . "$j" .  ")";
	    $sqlAvg.=" FROM " . "$tableName" . " WHERE ";
	    $sqlAvg.=" $stationIdSql AND ";
	    $sqlAvg.= " datetime >= \"$startDate $startTime\" AND datetime <= \"$endDate $endTime\" AND ";
	    $sqlAvg.=" sensid=$i";

	    $sqlTot="SELECT SUM(" . "$j" . ")";
	    $sqlTot.=" FROM " . "$tableName" . " WHERE ";
	    $sqlTot.=" $stationIdSql AND ";
	    $sqlTot.= " datetime >= \"$startDate $startTime\" AND datetime <= \"$endDate $endTime\" AND ";
	    $sqlTot.=" sensid=$i";

	    $sqlMin="SELECT datetime," . "$j" .
        	    " FROM " . "$tableName" . " WHERE " .
		    " datetime >= \"$startDate $startTime\" AND datetime <= \"$endDate $endTime\" AND " .
		    " $stationIdSql AND sensid=$i AND " .
		    " $j= ( SELECT MIN($j) FROM $tableName WHERE " .
	            " $stationIdSql AND " .
		    " datetime >= \"$startDate $startTime\" AND datetime <= \"$endDate $endTime\" AND " .
		    " sensid=$i ) LIMIT 1";
	   $sqlMax=$sqlMin;
	   $sqlMax=~s/MIN\(/MAX\(/o;
	    
	 }else{
	    # No Sql subqueries are allowed 
	    $sqlAvg="SELECT AVG(" . "$j" .  ")";
	    $sqlAvg.=" FROM " . "$tableName" . " WHERE ";
	    $sqlAvg.=" $stationIdSql AND ";
	    $sqlAvg.= " datetime >= \"$startDate $startTime\" AND datetime <= \"$endDate $endTime\" AND ";
	    $sqlAvg.=" sensid=$i";

	    $sqlTot="SELECT SUM(" . "$j" . ")";
	    $sqlTot.=" FROM " . "$tableName" . " WHERE ";
	    $sqlTot.=" $stationIdSql AND ";
	    $sqlTot.= " datetime >= \"$startDate $startTime\" AND datetime <= \"$endDate $endTime\" AND ";
	    $sqlTot.=" sensid=$i";


	    $sqlMin="SELECT datetime," . "$j" .
        	    " FROM " . "$tableName" . " WHERE " .
	            " $stationIdSql AND " .
		    " datetime >= \"$startDate $startTime\" AND datetime <= \"$endDate $endTime\" AND ";

            $sqlMax=$sqlMin;

	    $sqlMin.=" sensid=$i ORDER BY " . "$j" . " LIMIT 1";
	    #
	    $sqlMax.=" sensid=$i ORDER BY " . "$j" . " DESC LIMIT 1";
	 }

	 # Rainsensor Max and Min need special treatment
         # since we want the maximum 
         # for an hour not for a sensors data interval
	 #
         if( ($self->{"sensData"}->{"sensType"} eq "RA") || 
             ($self->{"sensData"}->{"sensType"} eq "LD")     ){	 
	    $sqlMax="SELECT datetime, SUM($j) AS HSUM" .
	            " FROM " . "$tableName" . " WHERE " .
		    " $stationIdSql AND " .
		    " datetime >= \"$startDate $startTime\" AND datetime <= \"$endDate $endTime\" AND (";
	    $sqlMin=$sqlMax;	    
	    $sqlMax.="sensid=$i ) GROUP BY LEFT(datetime, 13) ORDER BY HSUM DESC LIMIT 1";
	    $sqlMin.="sensid=$i ) GROUP BY LEFT(datetime, 13) ORDER BY HSUM ASC LIMIT 1";

	 }

	 #print "$sqlAvg <br>\n";
         # The average value for rain sensor is not calculated here. 
	 # Its calculated by getting the total rain in a period
	 # and dividing this value by the number of hours in the period
	 # This is done below.
	 $unitFactor=$self->{"sensData"}->{"unitfactor"}->{"$j"};
 	 if( ($self->{"sensData"}->{"sensType"} ne "RA") &&
 	     ($self->{"sensData"}->{"sensType"} ne "LD") ){
	    @res= $dbh->selectrow_array("$sqlAvg");
	    if( $#res>=0 ){
	       if( length($unitFactor) ){
		      $res[0]*=$unitFactor;
	       }
  	       # Store results. For average we round the value since it is a computed one
	       # and it is not compared against another existing (not calculated) value from 
	       # the database like it is done for min or max.
	       $res[0]=main::round($res[0], 2);
               $self->{"results"}->{"$i"}->{"mma"}->{"$j"}->{"avgValue"}=$res[0];
	    }
	 }
	 if( $self->{"sensData"}->{"mmaHasMin"} ){
   	    #print "* $sqlMin <br>\n";
	    @res= $dbh->selectrow_array("$sqlMin");
	    if( $#res>=0 ){
      	       if( length($unitFactor) ){
		   $res[1]*=$unitFactor;
	           $res[1]=main::round($res[1], 2);
	       }
               # Store results
	       ($tmp1, $tmp2)=split(/\s/o, $res[0]);
               $self->{"results"}->{"$i"}->{"mma"}->{"$j"}->{"minValue"}=$res[1];
               $self->{"results"}->{"$i"}->{"mma"}->{"$j"}->{"minDate"}=$tmp1;
               $self->{"results"}->{"$i"}->{"mma"}->{"$j"}->{"minTime"}=$tmp2;
	    }
	 }
	 #print "$sqlMax <br>\n";
	 @res= $dbh->selectrow_array("$sqlMax");
	 if( $#res>=0 ){
      	    if( length($unitFactor) ){
		   $res[1]*=$unitFactor;
	           $res[1]=main::round($res[1],2);
	    }
	    # Store results
	    ($tmp1, $tmp2)=split(/\s/o, $res[0]);
	    # Store results
            $self->{"results"}->{"$i"}->{"mma"}->{"$j"}->{"maxValue"}=$res[1];
            $self->{"results"}->{"$i"}->{"mma"}->{"$j"}->{"maxDate"}=$tmp1;
            $self->{"results"}->{"$i"}->{"mma"}->{"$j"}->{"maxTime"}=$tmp2;
	 }else{
	     # For rain sensor we set Max to 0 if there was no rain in the
	     # selected period of time. Just cosmetics. 
	     $self->{"results"}->{"$i"}->{"mma"}->{"$j"}->{"maxValue"}=0
	            if( $self->{"sensData"}->{"sensType"} eq "RA" );
	 }
	 
	 # Get total value; mainly for rain sensor
         if( $sens->{"gettotal"} ){
	    @res= $dbh->selectrow_array("$sqlTot");
      	    if( $#res>=0 ){
	       if( length($unitFactor) ){
	          $self->{"results"}->{"$i"}->{"mma"}->{"$j"}->{"total"}=
		      			       main::round($res[0]*$unitFactor,2 );
	       }else{
	          $self->{"results"}->{"$i"}->{"mma"}->{"$j"}->{"total"}=$res[0];
	       }
	       # For rain sensor we use the total value to calculate the average	   
	       if( $self->{"sensData"}->{"sensType"} eq "RA" ){
		  # Average value for rain by hour
        	  $self->{"results"}->{"$i"}->{"mma"}->{"$j"}->{"avgValue"}=
		                	main::round($res[0]*$unitFactor/$hours, 2);
	       }			     
	       if( $self->{"sensData"}->{"sensType"} eq "LD" ){
		  # Average value for rain by hour
        	  $self->{"results"}->{"$i"}->{"mma"}->{"$j"}->{"avgValue"}=
		                	main::round($res[0]*$unitFactor/$hours, 1);
	       }			     

	    }
	 }
      }
   }
}



# --------------------------------------------------------------------------
# Class simpleTable 
# Class that helps managing a table in HTML. It can print table header and 
# cells. You start with calling startTable() and end with endTable(). 
# The constructor needs the number of columns the table should have. 
# New cells are opened by calling newCol(). Rows are inserted
# automatically as needed (when given numer of cells have filled).
# To turn this off setthe paramter auto to 0  
# You can however also insert new rows manually by calling
# newRow(). This call will possibly issue empty cells to fill the currently open row
# and then start a new one. 
# --------------------------------------------------------------------------
package simpleTable;

#
# constructor of simpleTable
# Parameters are: Object ($self), 
# anonymous hash with one or more paramneters (cols,auto,fillEmptyCells)
# Attribute of table, eg 'border="1" cellspacing="2"' etc
#
sub new{
        my ($class) = shift;
	my ($para)  = shift;
	my ($attribs)=shift;
	my ($header)= shift;
        my ($self) = {};
	my ($i);
        bless $self, $class;

	$self->{"fillEmptyCells"}=0;
	# Enter parameters into ovbject
	foreach $i (keys(%{$para})){
	   $self->{$i}=${$para}{$i};
	}
		
	#$self->{"cols"}=$cols;		# Number of columns 		
	$self->{"attribs"}=$attribs;	# Table atributes
	$self->{"header"}=$header; 	# The table header
	
	$self->{"openCol"}=0;
	$self->{"openRow"}=0;
	$self->{"currentCol"}=0;
 
	return($self);
}

#
# Close open table row
#
sub closeRow{
   my ($self)=shift;
   my ($i);
   
   if( $self->{"openCol"} ){
   	print "</TD>";
	$self->{"openCol"}=0;
   }
   # Print empty cols to fill the row up to read the given total number of cols
   for($i=$self->{"currentCol"}; $i < $self->{"cols"}; $i++){
	if( $self->{"fillEmptyCells"} > 0 ){
   		print "<TD>&nbsp;</TD> ";
	}else{
		print "<TD></TD> ";
	}	
   }
  
   # Close Table row 	
   if( $self->{"openRow"} ){
   	print "</TR>\n";
        $self->{"openRow"}=0;	
   }
}


#
# Set Options to echoed for eaqch table row
#
sub setRowOptions {
   my($self)=shift;
   my($options)=shift;
   
   $self->{"rowOptions"}="$options";
}


#
# Set Options to echoed for each <tbody>
#
sub setTbodyOptions {
   my($self)=shift;
   my($options)=shift;
   
   $self->{"tbodyOptions"}="$options";
}


#
# Start a new Table row
#
sub openRow{
   my ($self)=shift;
   
   $self->closeRow() if( $self->{"openRow"} ); 
   # Start new row
   print "<TR";
   print " ", $self->{"rowOptions"} if( defined($self->{"rowOptions"}) );   
   print "> ";
   $self->{"openRow"}=1;	
   $self->{"currentCol"}=0;
}


#
#  Start new table row. Will close all missing columns of this table
# Rarameters: colspan for new row and colum attributes
#
sub newRow{
   my ($self)=shift;
   my ($span)=shift;
   my ($colParm)=shift;
   
   
   $self->openRow();
   $self->newCol($span, $colParm);
}

#
# Start new table column. If number of columns is bigger than max col number
# given in constructor, start automatically new row  
# Parameters are a span value and column attributes
#
sub newCol{
   my ($self)=shift;
   my ($span)=shift;
   my ($colParam)=shift; # Extra colum parameters like stylesheets
   
   # Start new col
   if( $self->{"auto"} && ($self->{"currentCol"} == $self->{"cols"}) ){
   	$self->closeRow();	
	$self->openRow();
   }else{
   	print "</TD>" if( $self->{"openCol"} );
   } 
   print "\n<TD"; 
   print " colspan=\"$span\"" if($span);
   print " $colParam" if( length($colParam) );
   print ">";  
   $self->{"openCol"}=1;	
   
   if( $span ){
       $self->{"currentCol"}+=$span;
   }else{
       $self->{"currentCol"}++;
   }
}


#
# Start table, print HTML table tag and header if defined
#
sub startTable{
   my ($self)=shift;
   my ($openRow)=shift;  # # if 0 no initial row will be opened
   my ($span)=shift;	   # Number of columns to span initially for first col
   
   $self->{"openCol"}=0;
   $self->{"openRow"}=0;
   $self->{"currentCol"}=0;
   
   print "<TABLE ", $self->{"attribs"}, ">\n";
   print $self->{"header"}, "\n"
		   	if( length($self->{"header"}));
   print "<TBODY";
   print " ", $self->{"tbodyOptions"}  if( defined($self->{"tbodyOptions"}) );  
   print ">\n";
   $self->newRow($span) if( $openRow );
}


#
# close a HTML table. Will close a open row and add missing columns
#
sub endTable{
   my ($self)=shift;
   
   $self->closeRow();
   print "</TBODY>\n</TABLE>\n";
}

#
# Return number of current Table column
#
sub getCurrentCol{
	my ($self)=shift;
	
	return $self->{"currentCol"};
}

#
# Return number Table columns
#
sub getMaxCol{
	my ($self)=shift;
	
	return $self->{"cols"};
}



# ----------------------------------------------------------------------------
#
# Statistics package which is used to collect more statistical data of the 
# sensors defined and display them in a table
#
package statistics;
#
# constructor of statistics
#
sub new{
        my ($class) = shift;
        my ($self) = {};
	my ($sensorData, $startDate, $startTime, 
	    $endDate, $endTime, $sampleTime, $dbh, $dstRange, $refNow, $refFirst)=@_;
        my ($ret, $aSens, $i, $doGust);
	
        bless $self, $class;

	$doGust=1;
        if( ref($sensorData) ){
	  #warn "**", join(", ", keys(%{$sensorData}));
	  #warn "# ", $sensorData->{"sensors"}->[3]->{"omit"}, "\n";
	  $aSens=$sensorData->getFirstSensor("statistics");
	  do{
	      if( $aSens->{"sensType"} eq "WI" ){
		  foreach $i (@{$aSens->{"omit"}}){
		    $doGust=0 if( $i eq "statgustspeed" );
		  }
	      }
	      $aSens=$sensorData->getNextSensor("statistics");
	  }while(defined($aSens));
        }
        
	# Store the date and time (in GMT) of the latest data set available
        ($self->{"lastDataYear"}, $self->{"lastDataMonth"}, $self->{"lastDataDay"}, 
	 $self->{"lastDataHour"}, $self->{"lastDataMinute"}, $self->{"lastDataSec"} )= @{$refNow};	   

        ($self->{"firstDataYear"}, $self->{"firstDataMonth"}, $self->{"firstDataDay"}, 
	 $self->{"firstDataHour"}, $self->{"firstDataMinute"}, $self->{"firstDataSec"} )= @{$refFirst};	   
	
	# We have to convert the time back to local time first to
	# adjust the date eg to the first of a month
	#print "new begin: Gmt: $startDate, $startTime -> $endDate, $endTime <br>\n";
	($self->{"locStartDate"}, $self->{"locStartTime"})=
	                       main::timeConvert($startDate, $startTime, "LOC");
	($self->{"locEndDate"}, $self->{"locEndTime"})=
	                       main::timeConvert($endDate, $endTime, "LOC");
	
	$self->{"sensorData"}=$sensorData; 
	$self->{"startDate"}=$startDate; 
	$self->{"endDate"}=$endDate;
	$self->{"startTime"}=$startTime;
	$self->{"endTime"}=$endTime;
	$self->{"sampleTime"}=$sampleTime; # Days, Weeks, Months or Years
	$self->{"dstRange"}=$dstRange;
        $self->{"defaultTime"}="00:00:00"; # Start of day local time
        $self->{"defaultEndTime"}="23:59:59"; # End of day local time
	
	# Types of sensors that are allowed for statistics display
	$self->{"allowedSensType"}={ "TH"=> "1", "RA"=>"1", "WI" => "1", "PR"=>"1" }; 
	# Sequence in which the statistics tab is filled with sensors
	$self->{"sensTypeSeq"}=[ "TH", "RA", "WI", "PR" ]; 
	
	# Definitions of column names for output and their "user" names
	# The definitions are dependent on the type of sensor and
	# one may define even sensor id specific like (no type field (eg TH) here):
	# $self->{"statSensCols"}->{"$sensid"}= ["T",  "H",   "frostdays"] 
	# In this case a definition for the "user" ColNames  has to exist as well
	# Names append with a "@" are MMA column names meaning for each of these 
	# columnames there is a minValue, maxValue, avgValue
	$self->{"statSensCols"}->{"TH"}    = ["T@",    "H@",   "frostdays", "icedays", "warmdays", "hotdays"];
	$self->{"statSensColNames"}->{"TH"}= ["T@", "H@", "Ft", "Et", "Wt", "Ht"];
	
	$self->{"statSensCols"}->{"RA"}    = ["diff@", "raindays",   "rainsum"];
	$self->{"statSensColNames"}->{"RA"}= ["R@", "Rt", "Sum"];

	if( $doGust ){
	  $self->{"statSensCols"}->{"WI"}    = ["speed@", "gustspeed@", "mainwinddir", "gustmainwinddir"];
	  $self->{"statSensColNames"}->{"WI"}= ["S@" ,  "B@",  "Hwr", "Bwr" ];
	}else{
	  $self->{"statSensCols"}->{"WI"}    = ["speed@", "mainwinddir"];
	  $self->{"statSensColNames"}->{"WI"}= ["S@", "Hwr"];
	}

	$self->{"statSensCols"}->{"PR"}    = ["P@"];
	$self->{"statSensColNames"}->{"PR"}= ["P@"];
	$self->{"tabCols"}=2; # Number of columns in table of non MMA values
	
	#print "new end: Gmt: $startDate, $startTime -> $endDate, $endTime <br>\n";

	$self->{"startDate"}=$startDate; 
	$self->{"endDate"}=$endDate;
	$self->{"startTime"}=$startTime; 
	$self->{"endTime"}=$endTime;
	
	$self->{"dateErrors"}=""; # Errors /Warnings from date manipulations
	
	$self->{"dateErrors"}=""; # Errors /Warnings from date manipulations
        $self->{"registerDateErrors"}=1;
	$self->normalizeDates(); # Make dates begin at eg first day of month, ...

        # Do not compile further date errors since this has been done in 
	# normalzedates already
	$self->{"registerDateErrors"}=0;
	$self->resetDateRange(); # Set work daterange to defaults
    
        $self->{"dbh"}=$dbh;
			
	return($self);
}


#
# Set link structure used in showNavigationPanel to
# create the day, week, month, year links
#
#
sub setPeriodData{
   my($self)=shift;
   my($refLinks)=shift;
   my($refPlinks)=shift;
   my($locEndDate)=shift;
   my($tmp1, $tmp2,$locEndDay,$locEndYear,$locEndMon);
   
   ($locEndYear,$locEndMon,$locEndDay)=split(/-/o, $locEndDate);
   
   # when statistcs mode is active we display calendar weeks, months,
   # and years. The links created above are simply a distance from one date
   # to another with a certain number of days in between. If eg a user selects 1 month 
   # from above the start and end date might be 15.01.2006->15.02.2006. This is 
   # correct for graphical display but for statistical display this would
   # result in two months beeing displayed (01 + 02) not one month which was what
   # the user selected (by clicking month-link). So we need to use
   # different distance values for the period (day, month, week, ..) links
   # to compensate this. Thats what %plinks is for.
   #
   $refPlinks->{"week"}={ "months" => 0, "days"   =>  7, "tag" => "1W"   };
   $refPlinks->{"week2"}={"months" => 0, "days"   =>  14, "tag" => "2W"   };
   $refPlinks->{"week3"}={"months" => 0, "days"   => 21, "tag" => "3W"   };

   # Get day number of month
   # Since in statistics mode monthsare calendar months when sampletime is 
   # /m,.*/ but else simply n*30days we have to make a difference here for the
   # month link.
   if( $self->{"sampleTime"} =~/^[dw]/o ) {
       $tmp1=0;
       $tmp2=0;
   }else{
       $tmp1=1;
       $tmp2=$locEndDay;
   }  
   $refPlinks->{"month"}={ "months" => (1-$tmp1), "days"   => $tmp2, "tag" => "1M" };
   $refPlinks->{"month2"}={"months" => (3-$tmp1), "days"   => 0, "tag" => "3M"   };
   $refPlinks->{"month3"}={"months" => (6-$tmp1), "days"   => 0, "tag" => "6M"   };

   # Get day number of year
   if( $sampleTime =~/^[dw]/o ) {
       $tmp1=0;
       $tmp2=0;
   }else{
       $tmp1=1;
       $tmp2=main::Day_of_Year($locEndYear,$locEndMon,$locEndDay);
   }  
   $refPlinks->{"year"}={ "months" => (1-$tmp1)*12, "days"   =>  $tmp2, "tag" => "1J" };
   $refPlinks->{"year2"}={"months" => (3-$tmp1)*12, "days"   => 0, "tag" => "3J"   };
   $refPlinks->{"year3"}={"months" => (5-$tmp1)*12, "days"   => 0, "tag" => "5J"   };
   $refPlinks->{"year4"}={"months" => (10-$tmp1)*12,"days"   => 0, "tag" => "10J"   };   
}


#
# Return possible Date errors/warnings as a string suitable for the user 
#
sub getDateErrors {
   my($self)=shift;
   my($result);
   
   $result=$self->{"dateErrors"};
   $self->{"dateErrors"}="";
   
   return( $result );
}


#
# Add an string to current date errors
#
sub addDateError{
   my($self)=shift;
   my($error)=shift;
   
   $self->{"dateErrors"}.=$error if( $self->{"registerDateErrors"} );
}


#
# Return references to the name of colums and their output names
# used in the display
# like "T" for a TH sensor and the output name "Temperature"
#
sub getSensStatCols {
   my($self)=shift;
   my($type)=shift;
   my($sensId)=shift;
   
   my($colName, $outName);
   
   # Look if there is a sensor id specific definition
   if( defined($self->{"statSensCols"}->{$sensId}) ){
       # The result are references to an array with the names
       $colName= $self->{"statSensCols"}->{$type}->{$sensId};
       $outNames=$self->{"statSensColNames"}->{$type}->{$sensId};
   }else{
       # return the default values depending only on the sensors type
       $colName= $self->{"statSensCols"}->{"$type"};
       $outNames=$self->{"statSensColNames"}->{"$type"};
   }
   return($colName, $outNames);
}


#
# Reset working daterange (currDate) to default
#
sub resetDateRange{
   my($self)=shift;
   
   $self->{"currStartDate"}=$self->{"startDate"}; 
   $self->{"currStartTime"}=$self->{"startTime"}; 
   $self->{"currEndDate"}=$self->{"startDate"}; # Start end and are initially equal
   $self->{"currEndTime"}=$self->{"startTime"};

   $self->{"locCurrStartDate"}=$self->{"locStartDate"}; 
   $self->{"locCurrStartTime"}=$self->{"locStartTime"}; 
   $self->{"locCurrEndDate"}=$self->{"locStartDate"}; # Start end and are initially equal
   $self->{"locCurrEndTime"}=$self->{"locStartTime"};
   $self->{"dateResetted"}=1; # Flag to know when we are at the initial date again
   $self->{"issueCompleteDaterange"}="1"; # Flag in addDeltaToDate to return the whole datrange in last run
   

   #print "resetDateRange loc: ",$self->{"locCurrStartDate"}, " " , $self->{"locCurrStartTime"}, ", ",
   #      $self->{"locCurrEndDate"}, " ", $self->{"locCurrEndTime"}, "<br>\n";  
   #print "resetDateRange gmt: ",$self->{"currStartDate"}, " " , $self->{"currStartTime"}, ", ",
   #      $self->{"currEndDate"}, " ", $self->{"currEndTime"}, "<br>\n";  
   
   # Add first delta sampleTime  value to endDate so start and end are no longer 
   # equal
   $self->addDeltaToDate(); # if( $self->{"sampleTime"} !~ /^d/o );

}


#
# Normalize date, so depending on sampleTime make Date the 1 of month or the 
# first day of the week or the first day of the year
#
sub normalizeDates{
    my($self)=shift;
    my($sampleTime, $sd, $ed, $st, $et);
    my($ds, $ms, $ys, $de, $me, $ye);
    my($defaultTime, $defaultEndTime);
 			
    $defaultTime=$self->{"defaultTime"};
    $defaultEndTime=$self->{"defaultEndTime"};
    $sampleTime=$self->{"sampleTime"};

    $sd=$self->{"locStartDate"}; 
    $st=$self->{"locStartTime"};
    $ed=$self->{"locEndDate"};
    $et=$self->{"locEndTime"};
 
    $checkEndDate=1; 

    #print "normalizeDates begin: Start:$sd, End:$ed , ST: $sampleTime<br>\n";  

    
    ($ys, $ms, $ds)=split(/-/o,$sd); 
    ($ye, $me, $de)=split(/-/o,$ed);
     
    
    if( $sampleTime =~ /[dwmy]/o ){  # set time to default for days, 
        $st=$defaultTime;        # weeks, months, years
	$et=$defaultEndTime;
    }
    
    if( $sampleTime =~ /[my]/o ){  # months and years range of stat data
       $ds="01";
       $ms="01" if( $sampleTime =~ /y/o );
       $sd="$ys-$ms-$ds";

       $me="12" if( $sampleTime =~ /y/o );
       $de=main::Days_in_Month($ye, $me);
       $ed="$ye-$me-$de";       

       # The result may be after the enddate given by the user
       # but we want whole years so this is ok 
       # So we set the new enddate to the end of the week found
       $ed="$ye-$me-$de"; 
       $self->{"locEndDate"} = "$ed";
       $self->{"locEndTime"} = "$et";    
       $checkEndDate=0; 
    }
    
    if( $sampleTime=~ /^w/o ){ # week display
       # Normalize date to start at a week and end at a week
        ($ys, $ms, $ds)=main::Add_Delta_Days(main::Monday_of_Week(main::Week_of_Year($ys, $ms, $ds)), 0);
	($ye, $me, $de)=main::Add_Delta_Days(main::Monday_of_Week(main::Week_of_Year($ye, $me, $de)), 0);  
	# Add 6 days to get last day of this week
	($ye, $me, $de)=main::Add_Delta_Days($ye, $me, $de, 6);
	
        # The result may be after the enddate given by the user
	# but we want whole weeks so this is ok 
	# So we set the new enddate to the end of the week found
	$sd="$ys-$ms-$ds";
	$ed="$ye-$me-$de";
	$checkEndDate=0; 
    }
    
    # Check if endDate is valid or after the date of last dataset
    # if its later, correct endDate to date of last dataset
    ($ed, $et)=$self->checkLimitEndDate($ed, $et, 0, $checkEndDate);
    ($sd, $st)=$self->checkLimitStartDate($sd, $st, 0);
    
    $self->{"locStartDate"} = "$sd"; 
    $self->{"locStartTime"} = "$st";
    $self->{"locEndDate"} = "$ed";
    $self->{"locEndTime"} = "$et";    

    # Keep local time values up to date
    ($self->{"startDate"}, $self->{"startTime"})=
	                   main::timeConvert($sd, $st, "GMT");
    ($self->{"endDate"}, $self->{"endTime"})=
	                   main::timeConvert($ed, $et, "GMT");
    
    #print "normalizeDates end: Start:$sd, $st End:$ed, $et <br>\n";  
    #print "normalizeDates gmt: ",$self->{"startDate"}, " " , $self->{"startTime"}, ", ",
    #     $self->{"endDate"}, " ", $self->{"endTime"}, "<br>\n";  
}


#
# Check if startDate is before the first date of a dataset
# if yes, then set the startDate to this first Date
#
sub checkLimitStartDate{
   my($self)=shift;
   my($date)=shift;
   my($time)=shift;
   my($isGMT)=shift;
   my($year, $month, $day, $hour, $minute, $second);
   my($tmp1, $tmp2, $tmp3, $tmp4);
   my($ey, $em, $ed, $eh, $emin, $es);
   my($locDate, $locTime, $locHour, $locMinute, $locSecond);

   # If not in GMT convert 
   if( ! $isGMT ){
      $locDate=$date; 
      $locTime=$time;
      ($date, $time)=main::timeConvert($date, $time, "GMT");
   }else{
      # Only used for error messages
      # Here we want the local time and date not GMT
      ($locDate, $locTime)=main::timeConvert($date, $time, "LOC");
   }


   # Values in GMT
   ($year,$month, $day)=split(/-/, $date);
   ($hour, $minute, $second)=split(/:/, $time);
   #
   # Values in local time
   ($locYear,$locMonth, $locDay)=split(/-/, $locDate);
   ($locHour, $locMinute, $locSecond)=split(/:/, $locTime);
    
   # We check if the start date is before the first exististing senorsvalues date
   # If yes, we use the first sensors date. 
   #print "* enddate in: $year,$month, $day $hour, $minute, $second <br>\n";   		      
   ($tmp1, $tmp2, $tmp3, $tmp4)=
          main::Delta_DHMS( $self->{"firstDataYear"}, $self->{"firstDataMonth"}, $self->{"firstDataDay"},
	                    $self->{"firstDataHour"}, $self->{"firstDataMinute"}, $self->{"firstDataSec"},
			    $year, $month, $day, $hour, $minute, $second
		      );
   # Set date of fisrt data entry to new startdate		      
   if( $tmp1 < 0 || $tmp2 < 0 || $tmp3 < 0 || $tmp4 < 0 ){
      $self->addDateError("Das f&uuml;r die Statistik gew&uuml;nschte Startdatum ($locDay.$locMonth.$locYear $locHour:$locMinute:$locSecond) liegt vor Datum des ersten existierenden Datensatzes.<br>\n");
      $date=$self->{"firstDataYear"} . "-" . $self->{"firstDataMonth"} . "-" . $self->{"firstDataDay"};
      $time=$self->{"firstDataHour"} . ":" . $self->{"firstDataMinute"} . ":" . $self->{"firstDataSec"};
   }

   # Possibly convert date/time back to local date/time
   if( ! $isGMT ){
      ($date, $time)=main::timeConvert($date, $time, "LOC");
   }
   return($date, $time);
}


#
# Check if endDate is beyond the last date of a dataset
# if yes, then set the endDate to this last Date
#
sub checkLimitEndDate{
   my($self)=shift;
   my($date)=shift;
   my($time)=shift;
   my($isGMT)=shift;
   my($checkEndDate)=shift;
   my($year, $month, $day, $hour, $minute, $second);
   my($tmp1, $tmp2, $tmp3, $tmp4);
   my($ey, $em, $ed, $eh, $emin, $es);
   my($locDate, $locTime, $locHour, $locMinute, $locSecond);

   # If not in GMT convert 
   if( ! $isGMT ){
      $locDate=$date; 
      $locTime=$time;
      ($date, $time)=main::timeConvert($date, $time, "GMT");
   }else{
      # Only used for error messages
      # Here we want the local time and date not GMT
      ($locDate, $locTime)=main::timeConvert($date, $time, "LOC");
   }
   
   # Values in GMT
   ($year,$month, $day)=split(/-/, $date);
   ($hour, $minute, $second)=split(/:/, $time);
   #
   # Values in local time
   ($locYear,$locMonth, $locDay)=split(/-/, $locDate);
   ($locHour, $locMinute, $locSecond)=split(/:/, $locTime);
    
   # Now we check if the date is after the given end date 
   # If yes, we use the end date
   # Values in GMT
   $tmp=$self->{"endDate"};
   ($ey, $em, $ed)=split(/-/o, $tmp);
   $tmp=$self->{"endTime"};
   ($eh, $emin, $es)=split(/:/o, $tmp);
   
   if( $checkEndDate ){
      ($tmp1, $tmp2, $tmp3, $tmp4)=
          main::Delta_DHMS(  $year, $month, $day, $hour, $minute, $second, 
	                     $ey, $em, $ed, $eh, $emin, $es  );
      # Check if current end Date is after the user defined 
      # EndDate. If yes, then correct endDate to user defined value
      # 
      if( $tmp1 < 0 || $tmp2 < 0 || $tmp3 < 0 || $tmp4 < 0 ){
	 $date="$ey-$em-$ed";
	 $time="$eh:$emin:$es";
	 $self->addDateError("Das f&uuml;r die Statistik ben&ouml;tigte Enddatum
($locDay.$locMonth.$locYear $locHour:$locMinute:$locSecond) ". 
	                     "liegt hinter gew&auml;hlten Enddatum.<br>\n");
      }	 

   }else{
      #print "Lastdate: ",  $self->{"lastDataYear"}, ", ", 
      #                    $self->{"lastDataMonth"}, ", ",  
      #			  $self->{"lastDataDay"},  ", ", 
      #	        	  $self->{"lastDataHour"},  ": ", 
      #			  $self->{"lastDataMinute"}, ": ",  
      #			  $self->{"lastDataSec"}, "<br>\n";

      # Now we check if the date is after the last exististing senorsvalues date
      # If yes, we use the last sensors date. This usually happens when the user selects
      # eg a year statistics display of the current year and since this year is not yet over
      # there is no data for some part of the year
      #print "* CheckEnddate in: $year,$month, $day $hour, $minute, $second <br>\n";   		      
      ($tmp1, $tmp2, $tmp3, $tmp4)=
             main::Delta_DHMS(  $year, $month, $day, $hour, $minute, $second, 
	        	  $self->{"lastDataYear"}, $self->{"lastDataMonth"}, $self->{"lastDataDay"},
	        	  $self->{"lastDataHour"}, $self->{"lastDataMinute"}, $self->{"lastDataSec"},
			 );
      # Set date of last data entry to new enddate		      
      if( $tmp1 < 0 || $tmp2 < 0 || $tmp3 < 0 || $tmp4 < 0 ){
	 $self->addDateError("Das f&uuml;r die Statistik ben&ouml;tigte Enddatum " .
	                     "($locDay.$locMonth.$locYear $locHour:$locMinute:$locSecond) " .
	                     "liegt hinter dem Datum des letzten Datensatzes.<br>\n");
	 $date=$self->{"lastDataYear"} . "-" . $self->{"lastDataMonth"} . "-" . $self->{"lastDataDay"};
	 $time=$self->{"lastDataHour"} . ":" . $self->{"lastDataMinute"} . ":" . $self->{"lastDataSec"};
      }

   } 

   # Possibly convert date/time back to local date/time
   if( ! $isGMT ){
      ($date, $time)=main::timeConvert($date, $time, "LOC");
   }
   #print "* CheckEnddate out: $date, $time <br>\n";
   return($date, $time);
}


#
# Add a delta value (day, week, month or year) to
# the current start and end date
#
sub addDeltaToDate{
   my($self)=shift;
   my($sampleTime, $sd, $ed, $st, $et, $isStart);
   my($ds, $ms, $ys, $de, $me, $ye);
   my($endYear, $endMonth, $endDay, $abort);
   
   
   # ==0 means we have run throughthe whole daterange and 
   # finally issued the "extra" complete daterange so 
   # now we are done until the next resetDaterange call.
   return(-1) if( $self->{"issueCompleteDaterange"}==0 );
   
   $sampleTime=$self->{"sampleTime"};
   $sd=$self->{"locCurrStartDate"}; 
   $st=$self->{"locCurrStartTime"};
   $ed=$self->{"locCurrEndDate"};
   $et=$self->{"locCurrEndTime"};

   #print "addDeltaToDate begin: Start:$sd, $st End:$ed, $et <br>\n";  
   #
   # If we are called for the first time we have to create an
   # initial endDate for the first date range. Prior to this
   # the running (curr*) start and end date/times are equal.
   if( $self->{"dateResetted"} ){
       $self->{"dateResetted"}=0;
       $isStart=1;    # Start and Enddate are equal (initial call)
   }else{
       $isStart=0;
   }
   
    
   ($ys, $ms, $ds)=split(/-/o,$sd);   # Workdates
   ($ye, $me, $de)=split(/-/o,$ed);

   # Set default endtime (again).
   $et=$self->{"defaultEndTime"}; 
   
   if( $sampleTime =~ /^d/ ){
      # Add one day to current startdate if start and end are different
      if( !$isStart ){
         ($ys, $ms, $ds)=main::Add_Delta_Days($ys,$ms,$ds, 1);
         $ye=$ys; $me=$ms, $de=$ds; # Start and End day are always equal in this mode
         $st=$self->{"defaultStartTime"};
      }	   
   }elsif( $sampleTime =~ /^w/ ){
      if( !$isStart ) {
         # Add 7 days to current startdate if start and end are different
         $st=$self->{"defaultStartTime"};
         ($ys, $ms, $ds)=main::Add_Delta_Days($ys,$ms,$ds, 7) 
      }
      # Add 6 days to startdate to get end: startDay+6 == 7 days
      ($ye, $me, $de)=main::Add_Delta_Days($ys,$ms,$ds, 6); 
      $st=$self->{"defaultStartTime"};
      #
   }elsif( $sampleTime =~ /^m/ ){
      if( $isStart ) {
         # Set end time to end of day if called first time
      }else{
         # Add one month if we are not called for the first time
         $ms++; if( $ms > 12 ){ $ms=1; $ys++;}
         $me++; if( $me > 12 ){ $me=1; $ye++;}
         $ds="01";
         $st=$self->{"defaultStartTime"};
      }	 
      $de=main::Days_in_Month($ye, $me);
   }elsif( $sampleTime =~ /^y/ ){
      # Add one year to current startdate if not called first time
      # Make the enddate the last day of startYear
      if( $isStart ){
	 $me="12";  # Set to last Day in year
	 $de="31";
      }else{
         # Add one year to current start/end-date if not called first time
	 $ds="01";
	 $ms="01";
	 $ys++;
	 $ye++;
         $st=$self->{"defaultStartTime"};
      }	 
   }else{
       warn "$0: Illegal sampleTime value: $sampleTime in addDeltaToDate\n";
   }
   
   # Keep possibly modified start end end local time values    
   $self->{"locCurrStartTime"}=$st;
   $self->{"locCurrEndTime"}=$et;
   $ed="$ye-$me-$de";
   $sd="$ys-$ms-$ds";
   
   #print "+++ $ed, $et, $ye, $me, $de <br>\n";
   
   # Get the definite End date
   ($endYear, $endMonth, $endDay)=split(/-/o, $self->{"locEndDate"} );
   #print "+ locEndDate: $endYear, $endMonth, $endDay <br>\n"; 

   # Now cpossibly correct enddate to date of latest dataset.
   ($ed, $et)=$self->checkLimitEndDate($ed, $et, 0, 1);
   #print "++* $ed, $et, $ye, $me, $de <br>\n";
  
   # Check if startDate is not before the very first sensors date
   #($sd, $st)=$self->checkLimitStartDate($sd, $st, 0);
   # print "*** $ed, $et <br>\n";
   ($ye, $me, $de)=split(/-/, $ed);  

   # Store new local start and end date
   $self->{"locCurrStartDate"}="$sd";
   $self->{"locCurrStartTime"}="$st";
   $self->{"locCurrEndDate"}="$ed";
   $self->{"locCurrEndTime"}="$et";
   
   # Keep GMT time values up to date
   ($self->{"currStartDate"}, $self->{"currStartTime"})=
	                  main::timeConvert($sd, $st, "GMT");
   ($self->{"currEndDate"}, $self->{"currEndTime"})=
	                main::timeConvert($ed, $et, "GMT");
   #print "     +* $ye, $me, $de,,  $endYear, $endMonth, $endDay <br>\n";
   # Check if end is reached:: startDate > endDate
   if( main::Delta_Days($ys, $ms, $ds,  $endYear, $endMonth, $endDay) >= 0 ){      
      #print "addDeltaToDate end: Start:$ys-$ms-$ds $st,  End:$ye-$me-$de $et<br>\n";
      #print "-------------------<br>\n";        
      return(0);
   }else{
      # At this point we have travelled from startdate to enddate
      # As a last daterange we now return the complete date range
      if( $self->{"issueCompleteDaterange"} ){   # Complete range has not been issued 
          $self->{"issueCompleteDaterange"}=0;   # since last reset in resetDateRange
	  $self->{"currStartDate"}=$self->{"startDate"};
	  $self->{"currStartTime"}=$self->{"startTime"};
	  $self->{"currEndDate"}=$self->{"endDate"};
	  $self->{"currEndTime"}=$self->{"endTime"};
	  $self->{"locCurrStartDate"}=$self->{"locStartDate"};
	  $self->{"locCurrStartTime"}=$self->{"locStartTime"};
	  $self->{"locCurrEndDate"}=$self->{"locEndDate"};
	  $self->{"locCurrEndTime"}=$self->{"locEndTime"};
	  
	  return(1);
      }
      #print "addDeltaToDate abort: Start:$ys-$ms-$ds,  End:$ye-$me-$de <br>\n";
      #print "-------------------<br>\n";  
      return(-1);
   }
}


#
# Check if a sensor type is allowed in statistics displays
#
sub checkIfTypeAllowed{
   my($self)=shift;
   my($sensType)=shift;
   
   if( $self->{"allowedSensType"}->{$sensType} >= "1" ){
      return(1); 
   }else{
      return(0);
   }
}


#
# get number of rain days in a certain period of time
#
sub getRainDays{
   my($self)=shift;
   my($refSensor)=shift;
   my($refSensIds);
   my($i, $j, $tmp, $sum, $dbh, $sth, $ref, $result, $sql, $sampleTime);
   my($startDateTime, $endDateTime, $unitFactor);
   my($locStartDateTime, $locEndDateTime);
   my($sqlDateZone, $sqlDateZone1, %rainDistribution);
   my($firstDay, $lastDay);
  
   
   $refSensIds=$refSensor->{"sensIds"};
   $dbh=$self->{"dbh"};
   $sampleTime=$self->{"sampleTime"};
   $startDateTime=$self->{"currStartDate"} . " " . $self->{"currStartTime"};
   $endDateTime=$self->{"currEndDate"} . " " . $self->{"currEndTime"};
   $locStartDateTime=$self->{"locCurrStartDate"} . " " . $self->{"locCurrStartTime"};
   $locEndDateTime=$self->{"locCurrEndDate"} . " " . $self->{"locCurrEndTime"};

   ($sqlDateZone, $sqlDateZone1)=
          main::sqlGmtToLoc($self->{"currStartDate"}, $self->{"currEndDate"},
	                    "rain", $self->{"dstRange"}, $self->{"defaultTime"} );			    
   
   foreach $i (@{$refSensIds}){
      #warn "++ $i\n";
      if( $sampleTime =~/^[dwmy]/ ){ # days, weeks, months, year
                                     # the sql query is always the same here    
           $sql="SELECT $sqlDateZone AS loctime, sum(diff) FROM rain WHERE " 
	        . $refSensor->{"stationIdSql"} . " AND " .
	         "sensid=$i AND diff != 0 AND " .
		 "datetime >= '$startDateTime' AND datetime <= '$endDateTime'" .
		 " GROUP by loctime ORDER by loctime";  
      }    
      #warn "Sql: $sql <br>\n";
      $ref=$dbh->selectall_arrayref($sql);
      $result=$#{$ref} +1;  # Number of rows in result hash
      $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->{"stats"}->{"raindays"}=$result;
      
      # Factor for rain sensor values (1/1000)
      $unitFactor=$refSensor->{"unitfactor"}->{"diff"};

      # Calculate Rain sum in current daterange
      $sum=0;
      $firstDay="";
      $lastDay="";
      #
      for( $j =0; $j <= $#{$ref} ; $j++) {
	  $tmp=$ref->[$j]->[1] * $unitFactor;
	  $sum+=$tmp;  # The "sum(diff)" - col from above
	  #
	  # First and last rainday determination
	  if( $tmp > 0 ){
	     	$firstDay=$ref->[$j]->[0] if( !length($firstDay) );  # date 
	        $lastDay=$ref->[$j]->[0];
	  }
	  
	  # get rainsum distribution 
	  if( $tmp < 2 ){                   # < 2mm per day
	      $rainDistribution{"02"}++;    
	  }elsif( $tmp >=2 && $tmp < 5 ){   # 2-5mm per day    
	      $rainDistribution{"05"}++; 
	  }elsif( $tmp >=5 && $tmp < 10 ){  # 5-10mm per day 
	      $rainDistribution{"10"}++; 
	  }elsif( $tmp >=10 && $tmp < 20 ){ # 10-20mm per day 
	      $rainDistribution{"20"}++; 
	  }else{
	      $rainDistribution{"bigger-20"}++; # > 20
	  }    
      }   	    

      # Remove time from date
      $firstDay=~s/\s.*$//o;
      $lastDay=~s/\s.*$//o;

      # Total of Rain
      $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->{"stats"}->{"rainsum"}=
            main::round($sum, 2);

      # First and last raindays
      $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->
                                      {"stats"}->{"raindays-dates"}->[0]=$firstDay;
      $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->
                                      {"stats"}->{"raindays-dates"}->[1]=$lastDay;
      
      # Number of raindays with rainfall of x,y,z,...
      $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->
                                      {"stats"}->{"raindistribution"}=\%rainDistribution;

      #print "Rain days ($locStartDateTime->$locEndDateTime): $result,  sum: $sum \n";
   }
}


#
# get number of ice days in a certain period of time
# Ice days are days where the temp climbs not >0 C the whole day long
#
sub getIceDays{
   my($self)=shift;
   my($refSensor)=shift;
   my($refSensIds);
   my($i, $j, $dbh, $sth, $ref, $result, $sql, $sampleTime);
   my($startDateTime, $endDateTime);
   my($locStartDateTime, $locEndDateTime);
   my($sqlDateZone, $sqlDateZone1);
   my($firstDay, $lastDay);
   
   $refSensIds=$refSensor->{"sensIds"};
   $dbh=$self->{"dbh"};
   $sampleTime=$self->{"sampleTime"};
   $startDateTime=$self->{"currStartDate"} . " " . $self->{"currStartTime"};
   $endDateTime=$self->{"currEndDate"} . " " . $self->{"currEndTime"};
   $locStartDateTime=$self->{"locCurrStartDate"} . " " . $self->{"locCurrStartTime"};
   $locEndDateTime=$self->{"locCurrEndDate"} . " " . $self->{"locCurrEndTime"};

   ($sqlDateZone, $sqlDateZone1)=
          main::sqlGmtToLoc($self->{"currStartDate"}, $self->{"currEndDate"},
	                    "th_sensors", $self->{"dstRange"}, $self->{"defaultTime"} );

   foreach $i (@{$refSensIds}){
      #warn "++ $i\n";
      if( $sampleTime =~/^[dwmy]/ ){ # days, weeks, months, year
                                     # the sql query is always the same here    
	   # We calculate ice days by counting  each sensor temp value and calculationg the
	   # SIGN value for each temp value in the daterange grouped by days.
	   # If the number of values in the daterange is as large as the negativ sum of the SIGN values
	   # of each temp value, the temp never was > 0 since in this case sign(T) would have not
	   # have been -1 for each of the T-values but 0 or 1 depending on the real temp value.
	   # Putting it another way: The number of sign(T) - values with results -1 has to be 
	   # as large as the number of T-values measured for a day saying that all these values 
	   # were < 0  
           $sql="SELECT $sqlDateZone AS loctime, COUNT(T) + sum(sign(T)) AS ISUM FROM th_sensors WHERE " 
	         . $refSensor->{"stationIdSql"} . " AND " .
	         "sensid=$i AND " .
		 "datetime >= '$startDateTime' AND datetime <= '$endDateTime'" .
		 " GROUP by loctime ORDER BY loctime";  
      }    

      #warn "Sql: $sql <br>\n";
      $ref=$dbh->selectall_arrayref($sql);
      $result=0;
      $firstDay="";
      $lastDay="";
      # Find number of values with a "ISUM"-column with value 0 which represent an ice day
      for($j=0; $j<= $#{$ref}; $j++) {
	 if( $ref->[$j]->[1] == 0 ){ # $j->[1] -> Colum ISUM from above 
            $result++;
	    $firstDay=$ref->[$j]->[0] if( !length($firstDay) );  # date 
	    $lastDay=$ref->[$j]->[0];
	 }
      }
      
      # Remove time from date
      $firstDay=~s/\s.*$//o;
      $lastDay=~s/\s.*$//o;
      #
      #print "Ice days ($startDateTime->$endDateTime): $result\n";
      #print "$firstDay, $lastDay <br>\n";
      
      $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->{"stats"}->{"icedays"}=$result;
      # Save date of first and last ice day
      $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->
                                      {"stats"}->{"icedays-dates"}->[0]=$firstDay;
      $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->
                                      {"stats"}->{"icedays-dates"}->[1]=$lastDay;
   }
}


#
# get number of frost days in a certain period of time
# a frostday is a day where the temperature is at least one time < 0 C
#
sub getFrostDays{
   my($self)=shift;
   my($refSensor)=shift;
   my($refSensIds);
   my($i, $dbh, $sth, $ref, $result, $sql, $sampleTime);
   my($startDateTime, $endDateTime);
   my($locStartDateTime, $locEndDateTime);
   my($sqlDateZone, $sqlDateZone1);
   my($firstDay, $lastDay);
   
   $refSensIds=$refSensor->{"sensIds"};
   $dbh=$self->{"dbh"};
   $sampleTime=$self->{"sampleTime"};
   $startDateTime=$self->{"currStartDate"} . " " . $self->{"currStartTime"};
   $endDateTime=$self->{"currEndDate"} . " " . $self->{"currEndTime"};
   $locStartDateTime=$self->{"locCurrStartDate"} . " " . $self->{"locCurrStartTime"};
   $locEndDateTime=$self->{"locCurrEndDate"} . " " . $self->{"locCurrEndTime"};

   ($sqlDateZone, $sqlDateZone1)=
          main::sqlGmtToLoc($self->{"currStartDate"}, $self->{"currEndDate"},
	                    "th_sensors", $self->{"dstRange"}, $self->{"defaultTime"} );

   foreach $i (@{$refSensIds}){
      #warn "++ $i\n";
      if( $sampleTime =~/^[dwmy]/ ){ # days, weeks, months, year
                                     # the sql query is always the same here    
           $sql="SELECT $sqlDateZone AS loctime, T FROM th_sensors WHERE "
	         . $refSensor->{"stationIdSql"} . " AND " .
	         "sensid=$i AND T < 0 AND " .
		 "datetime >= '$startDateTime' AND datetime <= '$endDateTime'" .
		 " GROUP by loctime ORDER BY loctime";  
      }    
      
      #warn "Sql: $sql \n";
      $ref=$dbh->selectall_arrayref($sql);
      $result=$#{$ref} +1;  # Number of rows in result hash

      # Determine first and last entry meaning first/last frostday 
      $firstDay=$ref->[0]->[0];
      $lastDay=$ref->[$#{$ref}]->[0];
      
      # Remove time from date
      $firstDay=~s/\s.*$//o;
      $lastDay=~s/\s.*$//o;

      #print "Frost days ($startDateTime->$endDateTime): $result\n";

      $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->{"stats"}->{"frostdays"}=$result;

      $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->
                                      {"stats"}->{"frostdays-dates"}->[0]=$firstDay;
      $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->
                                      {"stats"}->{"frostdays-dates"}->[1]=$lastDay;

   }
}


#
# get number of days in a certain period of time
# with at least a temperature of >= $minTemp
# Warm days have a temp > 20
# Hot  days have a temp > 30
#
sub getTempDays{
   my($self)=shift;
   my($refSensor)=shift;
   my($minTemp)=shift;
   my($resultName)=shift;
   my($refSensIds);
   my($i, $dbh, $sth, $ref, $result, $sql, $sampleTime);
   my($startDateTime, $endDateTime);
   my($locStartDateTime, $locEndDateTime);
   my($sqlDateZone, $sqlDateZone1);
   my($firstDay, $lastDay);
   
   $refSensIds=$refSensor->{"sensIds"};
   $dbh=$self->{"dbh"};
   $sampleTime=$self->{"sampleTime"};
   $startDateTime=$self->{"currStartDate"} . " " . $self->{"currStartTime"};
   $endDateTime=$self->{"currEndDate"} . " " . $self->{"currEndTime"};
   $locStartDateTime=$self->{"locCurrStartDate"} . " " . $self->{"locCurrStartTime"};
   $locEndDateTime=$self->{"locCurrEndDate"} . " " . $self->{"locCurrEndTime"};

   ($sqlDateZone, $sqlDateZone1)=
          main::sqlGmtToLoc($self->{"currStartDate"}, $self->{"currEndDate"},
	                    "th_sensors", $self->{"dstRange"}, $self->{"defaultTime"} );

   foreach $i (@{$refSensIds}){
      #warn "++ $i\n";
      if( $sampleTime =~/^[dwmy]/ ){ # days, weeks, months, year
                                     # the sql query is always the same here    
           $sql="SELECT $sqlDateZone AS loctime, T FROM th_sensors WHERE " 
	         . $refSensor->{"stationIdSql"} . " AND " .
	         "sensid=$i AND T >= $minTemp AND " .
		 "datetime >= '$startDateTime' AND datetime <= '$endDateTime'" .
		 " GROUP by loctime ORDER BY loctime";  
      }    
      #warn "Sql: $sql \n";
      $ref=$dbh->selectall_arrayref($sql);
      $result=$#{$ref} +1;  # Number of rows in result hash

      # Determine first and last entry meaning first/last day with temp <x> 
      $firstDay=$ref->[0]->[0];
      $lastDay=$ref->[$#{$ref}]->[0];
      
      # Remove time from date
      $firstDay=~s/\s.*$//o;
      $lastDay=~s/\s.*$//o;

      #print "Frost days ($locStartDateTime->$locEndDateTime): $result\n";

      $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->{"stats"}->{"$resultName"}=$result;

      $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->
                                      {"stats"}->{"${resultName}-dates"}->[0]=$firstDay;
      $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->
                                      {"stats"}->{"${resultName}-dates"}->[1]=$lastDay;
   }
}

#
# helper routine for getWindData()
# determine the main wind direction either for regular wind ($windGust==0)
# or for wind gusts ($windGust == 1)
# returns resulting string eg "WSW"
#
sub getMainWinddir{
   my($self)=shift;
   my($sqlDateZone, $startDateTime, $endDateTime, $sensId, $sampleTime, $windGust)=@_;
   my($wdSql, $sql, $angle, $tmp, $i, $j, $k, $ref, $dbh);
   my(@wr)=main::getWindDirectionList();
   
   if( $windGust ){ # Get data for wind gusts or for regular wind ?
      $angle="gustangle";
      $speed="gustspeed";
   }else{
      $angle="angle";
      $speed="speed";
   }
   
   $dbh=$self->{"dbh"};
   
   # Initialize SQL staement to count the number of data entries for
   # each wind direction. In the result the is for each of the possible 16 
   # winddirections one column containing the number of dataentries for this
   # column
   $wdSql="SELECT $sqlDateZone AS loctime, " .
          "SUM(IF($angle>=0     AND $angle < 22.5 OR $angle >= 337.5,  1, 0)) AS N,   " .
          "SUM(IF($angle>=22.5  AND $angle < 45,    1, 0)) AS NNO, " .
          "SUM(IF($angle>=45    AND $angle < 67.5,  1, 0)) AS NO,  " .
          "SUM(IF($angle>=67.5  AND $angle < 90,    1, 0)) AS O,   " .
          "SUM(IF($angle>=90    AND $angle < 112.5, 1, 0)) AS OSO, " .
          "SUM(IF($angle>=112.5 AND $angle < 135,   1, 0)) AS SO,  " .
          "SUM(IF($angle>=135   AND $angle < 157.5, 1, 0)) AS SSO, " .
          "SUM(IF($angle>=157.5 AND $angle < 180,   1, 0)) AS S  , " .
          "SUM(IF($angle>=180   AND $angle < 202.5, 1, 0)) AS SSW, " .
          "SUM(IF($angle>=202.5 AND $angle < 225,   1, 0)) AS SW,  " .
          "SUM(IF($angle>=225   AND $angle < 247.5, 1, 0)) AS WSW, " .
          "SUM(IF($angle>=247.5 AND $angle < 270,   1, 0)) AS W,   " .
          "SUM(IF($angle>=270   AND $angle < 292.5, 1, 0)) AS WNW, " .
          "SUM(IF($angle>=292.5 AND $angle < 315,   1, 0)) AS NW, " .
          "SUM(IF($angle>=315   AND $angle < 337.5, 1, 0)) AS NNW  ";

    # Now find out which was the main winddirection in this period of time      
    # We use only entries with speed >= Bft 1 which is >= 1.9 km/h
    #
    $sql=$wdSql . "FROM wind WHERE " . 
      	    "sensid=$sensId AND $speed >= 1.9 AND " .
	    "datetime >= '$startDateTime' AND datetime <= '$endDateTime' ";

    if( $sampleTime =~/^[d]/ ){ 
         $sql.="GROUP by LEFT($sqlDateZone, 10)";  
    }elsif(  $sampleTime =~/^[w]/ ){
         $sql.="GROUP BY CONCAT(YEAR($sqlDateZone), '-', WEEK($sqlDateZone))";  
    }elsif(  $sampleTime =~/^[m]/ ){
         $sql.="GROUP by LEFT($sqlDateZone, 7)";  
    }elsif(  $sampleTime =~/^[y]/ ){
         $sql.="GROUP by LEFT($sqlDateZone, 4)";  
    }else{
          warn "Illegal sampleTime \"$sampleTime\" in getWindData()\n"; 
    }    
    # Execute SQL statement
    #warn "Sql: $sql <br>\n";
    $ref=$dbh->selectall_arrayref($sql);
      
    # Find Maximum of values of one row. The index of this column 
    # is then the main winddirection of the period in @wr
    $tmp=0;
    $k="";
    for($j=1; $j <=$#{$ref->[0]}; $j++){
       if( $ref->[0]->[$j] > $tmp ){
	    $k=$j;                # Keep index in Mind
	    $tmp=$ref->[0]->[$j]; 
       }
    }
    # Get Name of main windDir 
    $tmp="-";
    if( length($k) ){
        $tmp=$wr[$k];
    }	
    return($tmp);
}


#
# get main winddirection and wind speed statistics by timeperiod
#
sub getWindData{
   my($self)=shift;
   my($refSensor)=shift;
   my($refSensIds);
   my($i, $j, $k, $tmp, $tmp1, $dbh, $sth, $ref, $result, $sql, $wdSql, $sampleTime, $windGust);
   my($startDateTime, $endDateTime, $unitFactor, $speedCols);
   my($locStartDateTime, $locEndDateTime);
   my($sqlDateZone, $sqlDateZone1, %rainDistribution);
   my($firstDay, $lastDay);
   my(@bf)=main::getWindSpeedList();
   my(@bfCount)= (0,0,0,0,0,0,0,0,0,0,0,0,0);     
   my(@bfCount1)= (0,0,0,0,0,0,0,0,0,0,0,0,0);     
   
   $windGust=1; # Do collect windgust information if wanted by config
   foreach $i (@{$refSensor->{"omit"}}){
	$windGust=0  if( $i == "gustspeed" ); 	# windgust has been marked as to "omit" 
   }						# so do not collect windgust stats
   
   if( $windGust){
      $speedCols="max(speed), max(gustspeed) ";
   }else{
      $speedCols="max(speed) ";
   }
   
   $refSensIds=$refSensor->{"sensIds"};
   $dbh=$self->{"dbh"};
   $sampleTime=$self->{"sampleTime"};
   $startDateTime=$self->{"currStartDate"} . " " . $self->{"currStartTime"};
   $endDateTime=$self->{"currEndDate"} . " " . $self->{"currEndTime"};
   $locStartDateTime=$self->{"locCurrStartDate"} . " " . $self->{"locCurrStartTime"};
   $locEndDateTime=$self->{"locCurrEndDate"} . " " . $self->{"locCurrEndTime"};

   ($sqlDateZone, $sqlDateZone1)=
          main::sqlGmtToLoc($self->{"currStartDate"}, $self->{"currEndDate"},
	                    "wind", $self->{"dstRange"}, $self->{"defaultTime"} );			    
   
   
   foreach $i (@{$refSensIds}){
      #warn "++ $i\n";
      #
      # First get the maximum daily speed in the timeperiod and
      # count how many times a certain bf value was reached. this info
      # is stored in @bfCount 
      #
      $sql="SELECT $sqlDateZone AS loctime, $speedCols FROM wind WHERE " 
	    . $refSensor->{"stationIdSql"} . " AND " .
	    "sensid=$i AND " .
	    "datetime >= '$startDateTime' AND datetime <= '$endDateTime' ";

      if( $sampleTime =~/^[dwmy]/ ){ 
         $sql.="GROUP by LEFT($sqlDateZone, 10)";  
      #}elsif(  $sampleTime =~/^[w]/ ){
      #   $sql.="GROUP BY CONCAT(YEAR($sqlDateZone), '-', WEEK($sqlDateZone))";  
      #}elsif(  $sampleTime =~/^[m]/ ){
      #   $sql.="GROUP by LEFT(loctime, 7)";  
      #}elsif(  $sampleTime =~/^[y]/ ){
      #   $sql.="GROUP by LEFT(loctime,4)";  
      }else{
          warn "Illegal sampleTime \"$sampleTime\" in getWindData()\n"; 
      }    
          
      #warn "* Sql: $sql <br>\n";
      $ref=$dbh->selectall_arrayref($sql);
      #
      foreach $k (@{$ref}) {  # Iterate over all rows found (one for each day)
	 $tmp=$k->[1]; # The max speed
	 $tmp1=$k->[2] if( $windGust);
         #
	 # Find beaufort value for max speed and increment counter for this bf value
	 for($j=0; $j<=$#bf; $j++){
             if ($tmp<$bf[$j]) {
                     $bfCount[$j]++;
		     last;
             }
	 }
	 # Find beaufort value for max gustspeed and increment counter for this bf value
	 if( $windGust ){
	    for($j=0; $j<=$#bf; $j++){
                if ($tmp1<$bf[$j]) {
                     $bfCount1[$j]++;
		     last;
                }
	    }
	 }
      }
      # Store result
      $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->{"stats"}->{"bfstats"}=\@bfCount;
      $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->{"stats"}->{"gustbfstats"}=\@bfCount1;

      #print "WindData: $locStartDateTime->$locEndDateTime <br>\n";
      #for($k=0; $k<=$#bfCount; $k++){
      #     print "BF: $k, days: $bfCount[$k] <br>\n";
      #}
      
      # Determine main winddirection for wind and windgusts
      $tmp=$self->getMainWinddir($sqlDateZone, $startDateTime, $endDateTime, $i, $sampleTime, 0);
      $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->{"stats"}->{"mainwinddir"}=$tmp;
      if( $windGust ){
	 $tmp=$self->getMainWinddir($sqlDateZone, $startDateTime, $endDateTime, $i, $sampleTime, 1);
	 $self->{"results"}->{"$locStartDateTime->$locEndDateTime"}->{$refSensor->{"configId"}}->{"$i"}->{"stats"}->{"gustmainwinddir"}=$tmp;
      }
  }
}


#
# Get MMA values for all statistics sensors defined
#
sub getMMA{
    my($self)=shift;
    my($refSensor)=shift;
    my($dataManager, $sensorData, $dbh);

    $sensorData=$self->{"sensorData"};
    $dbh=$self->{"dbh"};

    $startDateTime=$self->{"locCurrStartDate"} . " " . $self->{"locCurrStartTime"};
    $endDateTime=$self->{"locCurrEndDate"} . " " . $self->{"locCurrEndTime"};
    #print "getMMa loc: $startDateTime, $endDateTime <br>\n";
    #print "getMMA gmt: ", $self->{"currStartDate"}, " ",$self->{"currStartTime"}, ", ",
    #                      $self->{"currEndDate"}, " ",$self->{"currEndTime"}, "<br>\n";

    # Create a new Data Object for one sensor.
    $dataManager=dataManager->new($dbh, $sensorData, $refSensor, 
 			   $self->{"dstRange"} );

    # Set options needed for the work the dataManger Class does
    $dataManager->setOptions( {"sampleTime"=>$self->{"sampleTime"},
	 		      "startDate" => $self->{"currStartDate"},
	 		      "startTime" => $self->{"currStartTime"},
	 		      "endDate" => $self->{"currEndDate"},
	 		      "endTime" => $self->{"currEndTime"},
			      "mmaStartDate"=>$self->{"currStartDate"},
			      "mmaStartTime"=>$self->{"currStartTime"},
			      "mmaEndDate"  =>$self->{"currEndDate"},
			      "mmaEndTime"  =>$self->{"currEndTime"} , 
			      });

      $dataManager->checkVirtMma($refSensor);
      
      # Extract MMA values of Sensors
      # The are stored in 
      # $dataManager->{"results"}->{<sensid>}->{"mma"}->{<mmaDBColName>}->
      #  ...->{"minValue"},  ...->{"minDate"}, ...->{"minTime"}
      #  ...->{"maxValue"},  ...->{"maxDate"}, ...->{"maxTime"}
      #  ...->{"avgValue"}
      $dataManager->prepareSensData(1); 
            
      # Src Structure is: $dataManager->{"results"}->{"sensId"}->{"mma"}->{"T"}->{"avgValue"} 
      #  Copy from  $dataManager->{"results"}->{"sensId"}  to
      #  $self->{"results"}->{"$startDateTime->$endDateTime"}->{$refSensor->{"configId"}}->{"sensId"}
      foreach $i (keys(%{$dataManager->{"results"}})){         
	 $self->{"results"}->{"$startDateTime->$endDateTime"}->{$refSensor->{"configId"}}->{$i}->{"stats"} =
	                                    $dataManager->{"results"}->{$i}->{"mma"};
	 #print "+ $i:", $self->{"results"}->{"$startDateTime->$endDateTime"}->{$refSensor->{"configId"}}->{$i}->{"stats"}->{"T"}->{"minValue"}, "<br>";
	 #print "+ $i:", $self->{"results"}->{"$startDateTime->$endDateTime"}->{$refSensor->{"configId"}}->{$i}->{"stats"}->{"H"}->{"minValue"}, "<br>";
      }
}


#
# Run statistic procedures from startdate to endDate and print results
#
sub getPrintStats{
  my($self)=shift;
  my($terminate);
  my($sensorData, $dbh, $refSensor, $startDateTime, $endDateTime, $dateRange);
  my($rowCount);
    
  $sensorData=$self->{"sensorData"};
  $dbh=$self->{"dbh"};

  # Printer output table  header
  $rowCount=$self->printStatsTableHead(); # Returns always 0
  
  $terminate=0;
  do{   # Iterate over complete daterange
        #
	#print "+++ ", $self->{"locCurrStartDate"} . ", ". $self->{"locCurrEndDate"}, "<br>\n";
	#print "+++ ",  $refSensor->{"sensType"}, ",", @{$refSensor->{"sensIds"}}, "<br>\n";
	$startDateTime=$self->{"locCurrStartDate"} . " " . $self->{"locCurrStartTime"};
	$endDateTime=$self->{"locCurrEndDate"} . " " . $self->{"locCurrEndTime"};

        # Enter daterange in List of processed daterangeds
	$dateRange="$startDateTime->$endDateTime";
	$self->{"datetimeList"}->[$#{$self->{"datetimeList"}}+1]=$dateRange;

        $refSensor=$sensorData->getFirstSensor("statistics");	

	# Print first date/link column of each row.
	# If we print the row with the complete range (terminate==1)
	# we only do this if there are more than 1 rows of data
	# terminate: 0: next daterange, 1: last daterange, -1: end of range 
	if( $terminate == 0 || ($terminate == 1 && $rowCount > 1 ) ){
	   # print first date column with links
	   $self->printStatsFirstCol($dateRange, $terminate);
	}   

        do{  #iterate over all defined sensors
	     #
	     # Now run all subs that aquire data for the current date range
	     # The subs should use $self->{curr[start|end]Date} values
	     #print "# ", $sensorData->{"sensorCount"}, " \n";
	     #print "Statistics: ", $refSensor->{"statistics"}, "<br>\n";
	     # Skip sensor types like WD or others 
	     if(  $self->checkIfTypeAllowed($refSensor->{"sensType"}) ){     
                  # print $refSensor->{"sensType"}, ":", $refSensor->{"sensIds"}->[0], " \n";
		  $self->getMMA($refSensor);

		  if( $refSensor->{"sensType"} =~ /RA/o ){
		       $self->getRainDays($refSensor);
		  }elsif( $refSensor->{"sensType"} =~ /TH/o ){
		       $self->getIceDays($refSensor);
		       $self->getFrostDays($refSensor);
		       $self->getTempDays($refSensor, "20", "warmdays" );
		       $self->getTempDays($refSensor, "30", "hotdays" );
		  }elsif( $refSensor->{"sensType"} =~ /WI/o ){
		       $self->getWindData($refSensor);
		  }
	   }
	     
	     $refSensor=$sensorData->getNextSensor("statistics");
	     #
	}while( defined(%{$refSensor}) );

	# Print statistics values for one sensors with all its sensIds
	# If we print the row with the complete range (terminate==1)
	# we only do this if there are more than 1 rows of data
	# terminate: 0: next daterange, 1: last daterange, -1: end of range 
	if( $terminate == 0 || ($terminate == 1 && $rowCount > 1 ) ){
	   # print all stat cols of all sensors of one datetime
	   $rowCount=$self->printStatAllSensId($dateRange, $terminate);
	}
	 
	# Increment start/end date by "sampleTime" value
	$terminate=$self->addDeltaToDate();   
  }until($terminate< 0);

  # End table for statistics
  $self->printStatsTableTail();

   print '<FONT class="statTabHeader2">',
           "<br>Hinweis: Interessante Zusatzinformationen zu vielen Statistikdaten ",
           "(z.B. zu Min, Max, Rtg, ... -Werten ) erhalten Sie als Tooltip ",
           "indem Sie mit der Maus &uuml;ber den entsprechenden Wert fahren.\n";
           '</FONT>';

  # Reset date range for evaluation to initial values
  $self->resetDateRange(); 
}


#
# Reformat a date like 2006-01-24
#
sub dateFormat {
   my($self)=shift;
   my($date)=shift;
   my($dateTime)=shift;
   my($dateOnly, $time, $year, $month, $day,
       $hour, $minute, $second );
   
   ($dateOnly, $time)=split(/\s+/o, $date);   

   ($year,$month, $day)=split(/-/o, $dateOnly);
   ($hour, $minute, $second)=split(/:/o, $time);
   
   # int will remove a possibly existing 0 in the number
   $day="0" .   int($day) if( $day < 10 );
   $month="0" . int($month) if( $month < 10 );
   
   if( $dateTime ){
       return("$day.$month.$year $time"); 
   }else{	
       return("$day.$month.$year");      
   }    
}


#
# Reformat a Range of date1 to date2 into one string to be printed
# depending on sample time the results will differ
#
sub dateRangeFormat {
   my($self)=shift;
   my($date1)=shift;
   my($date2)=shift;
   my($sampleTime)=shift;
   my($fullDate)=shift;
   
   my($dateOnly1, $dateOnly2);
   
   $dateOnly1=$self->dateFormat($date1, 0);
   $dateOnly2=$self->dateFormat($date2, 0);
   
   if( $sampleTime =~ /d/ ){
        if( $fullDate ){
           return("$dateOnly1 -><br>$dateOnly2");
	}else{
	   return($dateOnly1);
	}
   }elsif( $sampleTime =~ /[mwy]/ ){
        return("$dateOnly1 -><br>&nbsp;&nbsp;&nbsp; $dateOnly2");
   }else{
      warn "Illegal sampleTime \"$sampleTime\" in statistics::dateRangeFormat \n";
   }
}


#
#  Format the tooltip into a string
#
sub toolTipFormat{
    my($self)=shift;
    my($refData)=shift; # The statistics data, the anonymous stats hash
    my($col)=shift;     #  value name like raindays-dates, icedays-dates
                        #  or T, H, ... for MMA
    my($baseCol)=shift; #  raindays, icedays  or  minValue, maxValue ... for MMA   
    my($type)=shift;
    my($h, $tip,  $tcol, $ref, $old);
    my($date, $time, $low, $high);
    my(@bfNames)=main::getShortWindSpeedNameList();
    my(@bfSpeeds)=main::getWindSpeedList();
    
    $tip=""; # No tip is the default
    if( $type == 1 ){ # Data like raindays, icedays ...
       if( length($refData->{"$col"}->[0]) ){
	  $h=$refData->{"$col"}->[0];  # Startdate
	  $h=$self->dateFormat($h,0);
	  $tip="Erster Tag: $h \n";

	  $h=$refData->{"$col"}->[1];  # Lastdate
	  $h=$self->dateFormat($h);
	  $tip.="Letzter Tag: $h";
       }  
       if( $baseCol eq "raindays" ){ #we want to add the rain amount distribution here
	  $tip.="\n\nRegentage nach Menge/Tag: \n";
	  $ref=$refData->{"raindistribution"};
	  $old="01";
	  # Build up tooltip string for raindistrib
	  # $i is the upper limit like 02, 05, 10, 20 l/day
	  # one entry is "bigger" for the days with rain more than 
	  # the lagest entry like "20"
	  foreach $i (sort(keys(%{$ref}))) {
	     if( $i !~ /bigger/o ){
		$tip.="$old-$i mm/Tag: ". $ref->{"$i"} . " T;";
		$tip.="\n";
		$old=$i;
	     }else{
		# Remove bigger keeping the number value 
		$old=$i; $old=~s/bigger-//;  
		$tip.=" > $old mm/Tag: " . $ref->{"$i"} . "T;";
	     }
	  }
       # Data for the wind sensor showing how many days with which wind speed in BF 
       }elsif( $baseCol eq "mainwinddir" ){
           $tmp=$refData->{"bfstats"};
	   $tip="Windst&auml;rke-Maxima nach Tagen: \n";
           for($i=0; $i<=$#{$tmp}; $i++){
	      if( $tmp->[$i] ){
	         if( $i==$#bfSpeeds ){
		    $low=" > $bfSpeeds[$i-1]";
		    $high="";
		 }else{ 
		    $low= $i==0?"0-":$bfSpeeds[$i-1] . "-";
		    $high=$bfSpeeds[$i];
		 }
	         $tip.="$i ($bfNames[$i], ${low}${high} Km/h):  " . $tmp->[$i] . " T; \n";
	      }
	   } 
       }elsif( $baseCol eq "gustmainwinddir" ){
           $tmp=$refData->{"gustbfstats"};
	   $tip="Windb&ouml;en-Maxima nach Tagen: \n";
           for($i=0; $i<=$#{$tmp}; $i++){
	      if( $tmp->[$i] ){
	         if( $i==$#bfSpeeds ){
		    $low=" > $bfSpeeds[$i-1]";
		    $high="";
		 }else{ 
		    $low= $i==0?0:$bfSpeeds[$i-1] . "-";
		    $high=$bfSpeeds[$i];
		 }
	         $tip.="$i ($bfNames[$i], ${low}${high} Km/h):  " . $tmp->[$i] . " T; \n";
	      }
	   } 
       }       
    }elsif( $type == 0 ){ # Min, Max Avg   
       if( $baseCol !~ /Avg/io ){
	  $baseCol=~s/Value/Date/o;  # replace eg minValue to minDate
	  $tcol=$baseCol;
	  $tcol=~s/Date/Time/o;  # replace eg minDate to MinTime
	  $date=$refData->{"$col"}->{"$baseCol"};
	  $time=$refData->{"$col"}->{"$tcol"};
	  # MMA dates are in GMT
	  ($date, $time)= main::timeConvert($date, $time, "LOC");
	  
	  $h=$self->dateFormat( "$date $time", 1 );  
	  $tip="Min-Datum: $h" if($baseCol =~ /Min/io ); 
	  $tip="Max-Datum: $h" if($baseCol =~ /Max/io ); 
	   
       }
    }
    return($tip);   
}


#
# Print Header line of statisticstable 
# with the sensor names in it
#
sub printStatsTableHead{
   my($self)=shift;
   my($sampleTime, $sensorData,$type, $sensorCounter,$refSensor, $statTab, $j, $sensId);
   
   $sampleTime=$self->{"sampleTime"};
   $sensorData=$self->{"sensorData"};
   # Get real Names of sensors from database if any
   # Result is in $refSensor->{"sensorDbNames"}->[$sensId]="name"
   $sensorData->getSensorNames($self->{"dbh"});
   
   $sensorCounter=0;

   # Iterate over all *types* of sensors defined for output
   for($j=0; $j <= $#{$self->{"sensTypeSeq"}}; $j++){ 
      $type=$self->{"sensTypeSeq"}->[$j];

      # Find all sensor entries of the given type
      $refSensor=$sensorData->getFirstSensorOfType($type, "statistics");

      # Count the number of sensors to be printed  
      while( defined(%{$refSensor}) ){
	 $sensorCounter+=($#{$refSensor->{"sensIds"}} +1)
        	if( !length($refSensor->{"statistics"}) || $refSensor->{"statistics"} != 0 );
	 $refSensor=$sensorData->getNextSensorOfType($type, "statistics" );
      }
   }
   
   # Title
   print "<h4>Statistische Daten ...";
   print main::helpLink(-1, "?", "statisticDisplay", 1);
   print "</h4>";
   
   # Start New Table
   $statTab=simpleTable->new({"cols"=>$sensorCounter+1, "auto"=>"0","fillEmptyCells"=>"1"}, 
            'border="1" cellpadding="1" cellspacing="1"' );
	    
   # Store Table handle
   $self->{"tableHandles"}->{"stattab"}=$statTab;
   	    
   $statTab->setTbodyOptions('valign="top", class="statTabBg"');
   $statTab->startTable(0, 0);
   $statTab->newCol(0, "class=\"statTabHeader1\"" );
   print "Datum:";
   
   # Iterate over all *types* of sensors defined for output
   for($j=0; $j <= $#{$self->{"sensTypeSeq"}}; $j++){ 
      $type=$self->{"sensTypeSeq"}->[$j];

      # Print names of sensors in table
      $refSensor=$sensorData->getFirstSensorOfType($type, "statistics");

      #
      # Print Row Headers.
      while( defined(%{$refSensor}) ){
	 if( !length($refSensor->{"statistics"}) || $refSensor->{"statistics"} != 0 ){
            for($i=0; $i<=$#{$refSensor->{"sensIds"}}; $i++){
		$statTab->newCol(0, "class=\"statTabHeader1\"");  
		$sensId=$refSensor->{"sensIds"}->[$i];
		if( length($refSensor->{"sensorDbNames"}->[$sensId]) ){
	           print $refSensor->{"sensorDbNames"}->[$sensId], ":";
		}else{
	           print $sensId;
		}	
	    }
	 }
	 $refSensor=$sensorData->getNextSensorOfType($type, "statistics");
      }
   }
   $self->{"outputTableRowCount"}=0;
   return(0);
}


#
# Terminate Stats Table
#
sub printStatsTableTail{
   my($self)=shift;
   my($statTable);
   
   $statTable=$self->{"tableHandles"}->{"stattab"};
   
   $statTable->endTable();
}


#
# Determine a sample time for the graphics links depending on the current sample time
# If e.g. a user looks a a statistics display in sections of whole years 
# it is useful to say that the graphics display for one such section (a year)
# should be displayed by day avereage values not by original data.
#
sub selectGfxSampleTime{
   my($self)=shift;
   my($sampleTime)=shift;
   my($gfxSampleTime);
   
   # Select a well suited sample time for graphics link depending on current
   # settings
   if( $sampleTime=~/^y/o ){
       $gfxSampleTime="d,Avg"; 
   }elsif($sampleTime=~/^m/o  ){
       $gfxSampleTime="d,Avg"; 
   }elsif($sampleTime=~/^w/o  ){
       $gfxSampleTime=""; 
   }else{
       $gfxSampleTime="";
   }
   
   return($gfxSampleTime);
}


#
#
# print first column of each data Row containing date and links
#
sub printStatsFirstCol {
   my($self)=shift;
   my($dateRange)=shift;
   my($lastRow)=shift;         # if this is the last Row
   my($dateStart, $dateEnd, $tmp, $tmp1, $tmp2, $gmtStartDateTime, $gmtEndDateTime, $formattedDateRange,
      %links, $url, $sampleTime, $gfxSampleTime, $linkTab, $statTab);
   
   $sampleTime=$self->{"sampleTime"};
     
   # Select a well suited sample time for graphics link depending on current
   # settings
   $gfxSampleTime=$self->selectGfxSampleTime($sampleTime);
   if( length($gfxSampleTime) ){
      $gfxSampleTime=";st=$gfxSampleTime;stuser=1";
   }

   $statTab=$self->{"tableHandles"}->{"stattab"};
   
   ($dateStart, $dateEnd)=split(/->/, $dateRange);
   
   # The last row is printed in another style, its the "summary" row
   if( !$lastRow ){ 
       $statTab->newRow(0, 'class="statTabValue1"');
       $formattedDateRange=$self->dateRangeFormat($dateStart, $dateEnd, $sampleTime, 0);      
   }else{
       $statTab->newRow(0, 'class="statTabValue1lastRow"');
       $formattedDateRange=$self->dateRangeFormat($dateStart, $dateEnd, $sampleTime, 1);      
   }

   ($tmp1, $tmp2)=split(/\s+/, $dateStart); # Split date and time
   ($tmp1, $tmp2)=main::timeConvert($tmp1, $tmp2, "GMT");
   $gmtStartDateTime="${tmp1}_${tmp2}";
   ($tmp1, $tmp2)=split(/\s+/, $dateEnd); # Split date and time
   ($tmp1, $tmp2)=main::timeConvert($tmp1, $tmp2, "GMT");
   $gmtEndDateTime="${tmp1}_${tmp2}";

   # print date range
   print $formattedDateRange;
   print "<br>\n";

   # Create URLs that shows the graphics for the daterange in question in
   # a new window.
   # Create more links that show the current daterange with smaller sampleTimes
   # Create two kind of links for each item: in current and in new window
   #
   $url=$main::scriptUrl . "?sd=$gmtStartDateTime;ed=$gmtEndDateTime";
   $links{"graphics"}="${url}$gfxSampleTime";
   $links{"days"}="$url;statMode=1;st=d,Avg;stuser=1";
   $links{"weeks"}="$url;statMode=1;st=w,Avg;stuser=1";
   $links{"months"}="$url;statMode=1;st=m,Avg;stuser=1";
   $links{"years"}="$url;statMode=1;st=y,Avg;stuser=1";

   # Create a table to arrange the links
   # The first col is empty just to get an indent
   #
   if( $sampleTime !~ /d/o ){
      $tmp="&nbsp;&nbsp;&nbsp;" 
   }else{
      $tmp="&nbsp;" 
   }
   $linkTab=simpleTable->new({"cols"=>4, "auto"=>"0","fillEmptyCells"=>"1"}, 
         'border="0" cellpadding="0" cellspacing="1"' );
   $linkTab->setTbodyOptions('valign="top"');
   $linkTab->setTbodyOptions('class="linkTabValue"');
   $linkTab->startTable(0, 0);
   $linkTab->newCol();

   print "$tmp"; $linkTab->newCol();
   print main::a({href=>$links{"graphics"}, target=>"_blank"}, "&iota;&Iota;&iota;");
   $linkTab->newRow();
   #
   # Print links for months, weeks and days, in new and current window
   if( $sampleTime=~/^y/o ){
      print "$tmp"; $linkTab->newCol();
      print main::a({href=>$links{"months"}, target=>"_blank"}, "[m]&raquo; ");
      $linkTab->newCol();
      print main::a({href=>$links{"weeks"},  target=>"_blank"}, "[w]&raquo; ");
      $linkTab->newCol();
      print main::a({href=>$links{"days"},   target=>"_blank"}, "[d]&raquo; ");

      $linkTab->newRow();  print "$tmp"; $linkTab->newCol();
      print main::a({href=>$links{"months"}}, "[m]");
      $linkTab->newCol();
      print main::a({href=>$links{"weeks"}}, "[w]");
      $linkTab->newCol();
      print main::a({href=>$links{"days"}}, "[d]");

   # Print links for weeks and days, in new and current window      
   }elsif( $sampleTime =~ /^m/ ){
      print "$tmp"; $linkTab->newCol();
      print main::a({href=>$links{"weeks"},  target=>"_blank"}, "[w]&raquo; ");
      $linkTab->newCol();
      print main::a({href=>$links{"days"},   target=>"_blank"}, "[d]&raquo; ");

      $linkTab->newRow(); print "$tmp";$linkTab->newCol();

      print main::a({href=>$links{"weeks"}}, "[w]");
      $linkTab->newCol();
      print main::a({href=>$links{"days"}}, "[d]");

   # Print links for days, in new and current window
   }elsif( $sampleTime =~ /^w/ ){
      print "$tmp";$linkTab->newCol();
      print main::a( {href=>$links{"days"}, target=>"_blank"}, "[d]&raquo; ");
      $linkTab->newRow(); print "$tmp";$linkTab->newCol();
      print main::a( {href=>$links{"days"}}, "[d]");
   }      
   $linkTab->endTable();   
}


#
# Print statistics colums for all sesnorids of one sensor
#
sub printStatAllSensId {
   my($self)=shift;
   my($dateRange)=shift;
   my($last)=shift;
   my($i, $j, $type, $sensId, $sensType, $refSensor, $sensorData, $statTab, $output);
   
   $output=0;
   $sensorData=$self->{"sensorData"};
   $statTab=$self->{"tableHandles"}->{"stattab"};
   
   # Handle sensor statistics output in predefined sequence depending on sensorType
   for($j=0; $j <= $#{$self->{"sensTypeSeq"}}; $j++){ 
      $type=$self->{"sensTypeSeq"}->[$j];

      $refSensor=$sensorData->getFirstSensorOfType($type, "statistics" );
      $sensType=$refSensor->{"sensType"};
      #
      # Print Row Headers.
      while( defined(%{$refSensor}) ){
	 if( !length($refSensor->{"statistics"}) || $refSensor->{"statistics"} != 0 ){
            for($i=0; $i<=$#{$refSensor->{"sensIds"}}; $i++){
		if( !$last ){
		   $statTab->newCol(0, "class=\"statTabHeader1\"");  
		}else{
		   $statTab->newCol(0, 'class="statTabValue1lastRow"');
		}
		$sensId=$refSensor->{"sensIds"}->[$i];

        	$self->printStatOneSensCol($dateRange, $refSensor, $sensId, $sensType );
		$output=1;
	    }
	 }
	 $refSensor=$sensorData->getNextSensorOfType($type, "statistics");
      }
   }
   $self->{"outputTableRowCount"}++ if( $output ); # Increase output row count
   return($self->{"outputTableRowCount"});
}


#
# Print statistical data of one sensor and one sensid
# into the output table.
#
sub printStatOneSensCol{
   my($self)=shift;
   my($dateRange)=shift;
   my($refSensor)=shift;
   my($sensId)=shift;
   my($sensType)=shift;
   my($frameTab, $sensTab, $colCount, $i, $j, $col, 
      $colname, $firstNonMMA, $tmp,  $colIdx, $tabCols,
      $sensTabFormatting, $title, $jsTitle, $tmp1, $tmp2);
   my($gmtStartDateTime, $gmtEndDateTime, $startTime,$dateStart, $dateEnd,
      $refCols, $refColNames, $colCount, $firstNonMMA, $tabCol, $colIdx,
      $title, $sampleTime, $gfxSampleTime, $countMma);   
   
   $statTab=$self->{"tableHandles"}->{"stattab"};

   $sampleTime=$self->{"sampleTime"};

   # Select a well suited sample time for graphics link depending on current
   # settings
   $gfxSampleTime=$self->selectGfxSampleTime($sampleTime);
   if( length($gfxSampleTime) ){
      $gfxSampleTime=";st=$gfxSampleTime;stuser=1";
   }

   
   ($dateStart, $dateEnd)=split(/->/, $dateRange);

   ($tmp1, $tmp2)=split(/\s+/, $dateStart); # Split date and time
   ($tmp1, $tmp2)=main::timeConvert($tmp1, $tmp2, "GMT");
   $gmtStartDateTime="${tmp1}_${tmp2}";
   ($tmp1, $tmp2)=split(/\s+/, $dateEnd); # Split date and time
   ($tmp1, $tmp2)=main::timeConvert($tmp1, $tmp2, "GMT");
   $gmtEndDateTime="${tmp1}_${tmp2}";

   
   # Padding and spacing for the tables with data
   $sensTabFormatting='cellpadding="1" cellspacing="3"';
   
   #print "$sensType, $sensId\n";
   
   # Get columns to be printed for this specific sensor
   ($refCols, $refColNames)=$self->getSensStatCols($sensType, $sendId); 
   
   # Another table to force the MMA and NON-MMA tables to align horizontally 
   $frameTab=simpleTable->new({"cols"=>2, "auto"=>"0","fillEmptyCells"=>"0"}, 
                   'border="0" cellpadding="0" cellspacing="0"' );
   $frameTab->setTbodyOptions('align="left" valign="top"');
   $frameTab->startTable(0, 0);
   $frameTab->newCol(0, 'align="left"');

   # Table for MMA values 
   $countMma=0;
   # Find number of sensor colums for MMA printout (eg. "T" + "H" == 2)
   for($i=0; $i<=$#{$refCols}; $i++){
      $countMma++ if( $refCols->[$i] =~ /\@$/o );
   }
   $sensTab=simpleTable->new({"cols"=>$countMma+1, "auto"=>"1","fillEmptyCells"=>"0"}, 
                             'border="0"' . $sensTabFormatting );
   $sensTab->startTable(0, 0);
   $sensTab->newCol(0);
  
   
   #
   # Now print Names of Colum Headers
   # Create an URL that shows the graphics for the daterange in question in
   # a new window.
   $url=$main::scriptUrl . "?";
   $url.="pl=" . $refSensor->{"sensType"} . ${$refSensor}{"typeSerial"};
   $url.=";sd=$gmtStartDateTime;ed=$gmtEndDateTime";
   $url.=$gfxSampleTime;
   print main::a({-class=>"statTabHeader2", href=>$url, target=>"_blank"}, "&iota;&Iota;&iota;");

   for( $i=0; $i<= $#{$refCols}; $i++){
       $col=$refCols->[$i];
       if( $col =~ /\@$/o ){
	  $colName=$refColNames->[$i];
	  $colName=~s/\@$//o;
	  $colName.=":";
	  $col=~s/\@$//o;
	    
          $sensTab->newCol(0, 'class="statTabHeader2"');
	  print "$colName";
       }
   }     

   # Now print the Rows, the min, the max and the average row
   for($j=0; $j<=2; $j++){
      $tmp="Min" if( $j == 0 );
      $tmp="Max" if( $j == 1 );
      $tmp="Avg" if( $j == 2 );
      $sensTab->newCol(0, 'class="statTabHeader2"');
      # print Name of row header like Min or Max
      print "$tmp";
      
      if( $tmp eq "Min" && $refSensor->{"mmaHasMin"} == 0){
         for($i=0; $i < $countMma; $i++) {         
	    $sensTab->newCol(0, "class=\"statTabValue2\"");
	    print "&nbsp;-";
	 }
      }else{
         #
         # Now print the values for one sensor col like Min of "T" and "H"
         for( $i=0; $i<= $#{$refCols}; $i++){
	     $col=$refCols->[$i];
	     if( $col =~ /\@$/o ){
	        $col=~s/\@$//o;

	        $tmp="minValue" if( $j ==0 );
	        $tmp="maxValue" if( $j ==1 );
	        $tmp="avgValue" if( $j ==2 );

	        # Format tooltip to contain eg first and last iceday
	        ($title)=$self->toolTipFormat($self->{"results"}->{"$dateRange"}->
						{$refSensor->{"configId"}}->
	                                        {"$sensId"}->{"stats"}, $col, $tmp, 0);
	     
                $sensTab->newCol(0, "title=\"$title\" class=\"statTabValue2\"");
                #print "# $col, $tmp#;\n";
	        print $self->{"results"}->{"$dateRange"}->{$refSensor->{"configId"}}->{"$sensId"}->{"stats"}->{$col}->{"$tmp"};
	     }
         }    
      }
   }       
   $sensTab->endTable(); 
   $frameTab->newCol(0);


   #
   # Next print the table with non MMA values
   # First determine how many colums there are to be printed
   # Since MMA is done we omit these data
   $colCount=0;
   $firstNonMMA=-1;
   for($i=0; $i<= $#{$refCols}; $i++){
      if( $refCols->[$i]!~/\@$/o ){
      	  $firstNonMMA=$i if( $firstNonMMA < 0 );
	  $colCount++;
      }	  
   }
   #
   $tabCols=$self->{"tabCols"}; # Get number of columns to use for NON MMA values
   $colIdx=$firstNonMMA;  # Index of first value that is not a MMA column
   # Create table with "non"  MMA values
   $sensTab=simpleTable->new({ "cols"=>$tabCols, "auto"=>"0","fillEmptyCells"=>"1"},                             'border="0"' . $sensTabFormatting );
   $sensTab->startTable(0, 0);
   #
   while($colIdx < $colCount+$firstNonMMA ){    
      $sensTab->newRow();
      #
      # print the Header for the table with the "non" MMA values
      for( $i=$colIdx; $i<$colIdx+$tabCols && $i<= $#{$refCols}; $i++){
	  $col=$refCols->[$i];
	  if( $col !~ /\@$/o ){
	     $sensTab->newCol(0, "align=right class=\"statTabHeader2\"");
	     $colName=$refColNames->[$i];
	     print $colName, ":"; 
	  }
      }
      $sensTab->newRow();

      #
      # print the values for the table with the "non" MMA values
      for( $i=$colIdx; $i<$colIdx+$tabCols && $i<= $#{$refCols}; $i++){
	  $col=$refCols->[$i];
	  if( $col !~ /\@$/o ){
	     $colName=$refColNames->[$i];
	     
	     # Format tooltip to contain eg first and last iceday
	     $title=$self->toolTipFormat($self->{"results"}->{"$dateRange"}->{$refSensor->{"configId"}}->
	                               {"$sensId"}->{"stats"}, "${col}-dates", $col, 1);

	     $sensTab->newCol(0, "align=right title=\"$title\" class=\"statTabValue2\"");
	     print $self->{"results"}->{"$dateRange"}->{$refSensor->{"configId"}}->{"$sensId"}->{"stats"}->{$col};
	  }
      }
      $colIdx+=$tabCols;      
   }
   $sensTab->endTable();   
   $frameTab->endTable();
}


#--------------------------------------------------------------------------
package main;

#
#  Connect to database and return databasehandle
#
sub connectDb{
   my($dsn, $dbh);

   # Connect to database
   #
   $dsn = "DBI:$driver:database=$database;host=$dbServer;port=$defaultPort";
   if( ! ($dbh = DBI->connect($dsn, $dbUser, $dbPassword,
        { 'RaiseError' => 1, 'AutoCommit' => 1, 'PrintError' => 1 })) ) {
       $errMsg="Cannot Connect to \"$dsn\" as $dbUser\n";
       return(0);
   }
   return($dbh);
}


#
# Close connection to database
#
sub closeDb{
  my($dbh)=@_;

  $dbh->disconnect();
}


#
# find out start *or* end of DST time
# function relies on Timezone() from the Date::Calc package
#
sub checkDst{
   my($step, $startDate, $addOne)=@_;
   my( $year,$month,$day, $hour,$min,$sec);
   my( $oldYear,$oldMonth,$oldDay, $oldHour,$oldMin,$oldSec);
   my($D_y,$D_m,$D_d, $Dh,$Dm,$Ds, $dst); 
   my($tmp1, $tmp2, $status);
   my($stepDay, $stepH, $dayCount);
   
   ($tmp1, $tmp2)=split(/\s/o, $startDate);
   ($year,$month,$day)=split(/-/o, $tmp1);
   ($hour,$min,$sec)=split(/:/o, $tmp2);
   
   #print "** Step: $step  <br>\n";
   #print "* Startdate: $year, $month, $day - $hour, $min, $sec <br>\n";
   
   $dayCount=0;
   # If != 0 $addDays will be added to startDate and h:m:s will
   # be reset to 00:00:00
   if( $addOne ){
	($year,$month,$day, $hour,$min,$sec) =
             Add_Delta_DHMS($year,$month,$day, $hour,$min,$sec,
                            $addOne, 0,0,0);  # + one day 
	$hour=$min=$sec=0;		    
   }			    
   
   # Check current DST status
   ($D_y,$D_m,$D_d, $Dh,$Dm,$Ds, $dst) = 
              Timezone(Date_to_Time($year,$month,$day, $hour,$min,$sec));
   $status=$dst;
   
   if( $step=~/day/i ){
   	$stepDay=1;
	$stepH=0;
   }else{
   	$stepDay=0;
	$stepH=1;
   }
   
   # Now iterate over current date adding a day or an hour in
   # each run and check if dst flag changed
   while($dst==$status && $dayCount<=366 && (
    $oldYear!=$year || $oldMonth!=$month || $oldDay!=$day ||
    $oldHour!=$hour || $oldMin!=$min || $oldSec!=$sec  )      ){	      

    #print "* Olddate: $dayCount; $oldYear, $oldMonth, $oldDay - $oldHour, $oldMin, $oldSec <br>\n";

	$oldYear=$year; $oldMonth=$month; $oldDay=$day;
	$oldHour=$hour; $oldMin=$min; $oldSec=$sec;
   	
	($year,$month,$day, $hour,$min,$sec) =
             Add_Delta_DHMS($year,$month,$day, $hour,$min,$sec,
                            $stepDay,$stepH,0,0);

	# Check again status of DST
   	($D_y,$D_m,$D_d, $Dh,$Dm,$Ds, $dst) = 
              Timezone(Mktime($year,$month,$day, $hour,$min,$sec));
	
        #print "* status-dst: $status, $dst <br>\n";

	# If we step in days and $dst changed we 
	# now investigate the excat hour of the change
	# We check at most one year. dayCount is used for this check
	$dayCount++ if($step =~ /day/io );
	if( $status!=$dst && ($step =~ /day/io) ){

                #print "+ Found DST change in days ";
    		#print "$year,$month,$day: $dst <br>\n";
		($year,$month,$day, $hour,$min,$sec) =
        	     Add_Delta_DHMS($year,$month,$day, $hour,$min,$sec,
                        	    -1,0,0,0);
		# Found day, now check hour
		return(checkDst("Hour", "$year-$month-$day $hour:$min:$sec", 0));
		
	}elsif($status!=$dst && $step =~ /hour/io ){
		$tmp1=sprintf("%04d-%02d-%02d %02d:%02d:%02d", 
				$year,$month,$day, $hour,$min,$sec);
		return(($tmp1, $dst, $D_d*24+$Dh));
	}else{
		$status=$dst;
	}
   }# End of while
   
   # We get here only if there was no dst change found in 366 days
   if( $step =~ /day/io ){ 
      # Get Difference in between local time and GMT
      ($D_y,$D_m,$D_d, $Dh,$Dm,$Ds, $dst) = Timezone();
      return(" ", "nodst", $D_d*24+$Dh);
   }else{
   	print "Invalid control flow in checkdst(). Stop\n";
	die;
   }
}



#
# get dst start *and* end using checkDst()
#
sub getDSTStartEnd{
   my($year)=shift;
   my($tmp1, $dst, $tmp2, $dstStart, $deltaIsDst, $dstEnd, $deltaNoDst);
   
   if( !$timeIsGMT ){
      # Look for start or end of DST depending on what mode
      # the startDate is in 
      ($tmp1, $dst, $tmp2)=checkDst("day", $year. "-01-01 00:00:00", 0);
      if( $dst !~ /nodst/io ){
	 #print "* GMT<->local difference: $tmp2 <br>\n";
	 if( $dst){
		 $dstStart=$tmp1;
		 $deltaIsDst=$tmp2;	
	 }else{
		 $dstEnd=$tmp1;
		 $deltaNoDst=$tmp2;
	 }
	 # Now search from a day after the first change in DST 
	 # found above and look for end or start of dst
	($tmp1, $dst, $tmp2)=checkDst("day", $tmp1, 1);
	 if( $dst){
		 $dstStart=$tmp1;
		 $deltaIsDst=$tmp2;	
	 }else{
		 $dstEnd=$tmp1;
		 $deltaNoDst=$tmp2;
	 }
      }else{
   	$deltaIsDst=$tmp2;
	$deltaNoDst=$tmp2; 
	$dstStart="1900-01-01";
	$dstEnd=$dstStart;
      }
   }else{ # Local time is in GMT so there is no delta
   	$deltaIsDst=0;
	$deltaNoDst=0;
	$dstStart="1900-01-01";
	$dstEnd=$dstStart;
   }
   #warn "*** $dstStart,$dstEnd, $deltaIsDst, $deltaNoDst \n";
   return(($dstStart,$dstEnd, $deltaIsDst, $deltaNoDst)); 
}



# convert a local time and date to a date in GMT. This routine needs the 
# glocal variable $theTimeOffset which describes how many hours the difference
# between local and GMT time is. 
# The variable target can be LOC or GMT giving the destination time zone

sub timeConvert{
   my($date, $time, $target)=@_;
   my(@d, @nd, $offset);

   if( !$timeIsGMT && length($date) ){
	   @d=(split(/-/o, $date), split(/:/o, $time) );
	   if( $target eq "GMT" ){
   		@nd=Gmtime(Mktime($d[0], $d[1], $d[2], $d[3], $d[4], $d[5]));
	   }else{
   		@nd=Localtime(Date_to_Time($d[0], $d[1], $d[2], $d[3], $d[4], $d[5]));
	   }
	   $nd[1]="0$nd[1]" if($nd[1] <10); 
	   $nd[2]="0$nd[2]" if($nd[2] <10); 
	   $nd[3]="0$nd[3]" if($nd[3] <10); 
	   $nd[4]="0$nd[4]" if($nd[4] <10); 
	   $nd[5]="0$nd[5]" if($nd[5] <10); 
	   
	   return(("$nd[0]-$nd[1]-$nd[2]",  "$nd[3]:$nd[4]:$nd[5]"));			
   }else{
   	return(($date, $time));
   }	   
}


#
# check if day, month year are valid values (eg month: 1..12)
#
sub checkOneDate{
   my($year, $month, $day, $hour, $min, $sec, $fYear)=@_;
   my($valid)=1;
   my($tmp, $errStr);

   $errStr="";
   
   # Startdate is OK?
   if( !check_date($year,$month, $day) ){
	if( $year < 1900 ){ $year=$fYear; $valid=0; $errStr.="Illegale Jahresangabe: $year .<br>"; }
	if( $month > 12 ){ $month=12; $valid=0;	$errStr.="Illegale Montasangabe: $month .<br>";}
	if( $month < 1 ){ $month=1; $valid=0; $errStr.="Illegale Monatsangabe: $month .<br>";}
	if( $day < 1 ){ $day=1;	$valid=0; $errStr.="Illegale Tagesangabe: $month .<br>";}
	
	$tmp=Days_in_Month($year, $month);
	if( $day > $tmp ){ $day=$tmp; $valid=0;	}	
   }
   if( !check_time($hour, $min, $sec) ){
   	if( $hour<0 || $hour > 23){ $hour="00";	$valid=0; $errStr.="Illegale Stundenangabe: $hour .<br>"}
   	if( $min<0 || $min > 59){ $min="00"; $valid=0; $errStr.="Illegale Minutenangabe: $min .<br>"}
   	if( $sec<0 || $sec > 59){ $sec="00"; $valid=0; $errStr.="Illegale Sekundenangabe: $sec .<br>"}
   }

   return($year, $month, $day, $hour, $min, $sec, $valid, $errStr);
}

#
# Check and correct given start end end date for correctnes
# Function needs start-Date, end-Date, todays-Date
#
sub checkDate{
  my($firstYear, $firstMon, $firstDay, $startDate, $startTime, 
  	$endDate, $endTime, $sampleTime, $refNow, $refFirst, $statisticsMode) =@_; 
  my($startYear,$startMon, $startDay, $startHour, $startMin, $startSec,
     $endYear, $endMon, $endDay, $endHour, $endMin, $endSec);
  my($nowDay, $nowMon, $nowYear, $nowHour, $nowMin, $nowSec);   
  my($tmpDay, $tmpMon, $tmpYear);
  my($valid)=1;
  my($tmp, $tmp1, $tmp2, $tmp3, $tmp4, $errStr);
  my($locStartDay, $locStartMon, $locStartDay, $locStartHour, $locStartMin, $locStartSec);
  my($locEndDay, $locEndMon, $locEndDay, $locEndHour, $locEndMin, $locStartSec);

  #print "<br>*** $startDate, $startTime ->  $endDate, $endTime <br>\n";
  $errStr="";

  ($startYear,$startMon, $startDay)=split(/-/o, $startDate);
  ($startHour, $startMin, $startSec)=split(/:/o, $startTime);

  ($endYear,$endMon, $endDay)=split(/-/o, $endDate);
  ($endHour, $endMin, $endSec)=split(/:/o, $endTime);

  # Current date in GMT
  ($nowYear, $nowMon, $nowDay, $nowHour, $nowMin, $nowSec)=Today_and_Now(1);
  

  # Startdate is OK?
  ($startYear, $startMon, $startDay, $startHour, $startMin, $startSec, $tmp, $tmp1)=
       checkOneDate($startYear, $startMon, $startDay, 
	       $startHour, $startMin, $startSec, $firstYear);
  if( !$tmp ){
     $valid=0;
     $errStr.="$tmp1";
  }

  # Enddate is OK?
  ($endYear, $endMon, $endDay, $endHour, $endMin, $endSec, $tmp, $tmp1)=
       checkOneDate($endYear, $endMon, $endDay, 
	       $endHour, $endMin, $endSec, $firstYear);
  if( !$tmp ){
     $valid=0;
     $errStr.="$tmp1";
  }

  # Now check the date range, if $startDate is > $endDate
  ($tmp1, $tmp2, $tmp3, $tmp4)=
  Delta_DHMS( $startYear, $startMon, $startDay, $startHour, $startMin, $startSec,
		  $endYear, $endMon, $endDay, $endHour, $endMin, $endSec);
  if( $tmp1 < 0 || $tmp2 < 0 || $tmp3 < 0 || $tmp4 < 0 ){
       # swap the two date entries so "start" comes bevor "end"
       $tmpDay=$endDay; $tmpMon=$endMon; $tmpYear=$endYear;
       $endYear=$startYear; $endMon=$startMon; $endDay=$startDay;
       $startYear=$tmpYear; $startMon=$tmpMon; $startDay=$tmpDay;

       $tmp1=$endHour; $tmp2=$endMin, $tmp3=$endSec;
       $endHour=$startHour; $endMin=$startMin, $endSec=$startSec;
       $startHour=$tmp1; $startMin=$tmp2; $startSec=$tmp3;
       $valid=0;
  }
  
  # Convert startdate, enddate into local time for error messages
  ($tmp1, $tmp2)=main::timeConvert("$startYear-$startMon-$startDay", 
                                   "$startHour:$startMin:$startSec", "LOC");
  ($locStartYear, $locStartMon, $locStartDay)=split(/-/o, $tmp1);
  ($locStartHour, $locStartMin, $locStartSec)=split(/:/o, $tmp2);
  #
  ($tmp1, $tmp2)=main::timeConvert("$endYear-$endMon-$endDay", 
                                   "$endHour:$endMin:$endSec", "LOC");
  ($locEndYear, $locEndMon, $locEndDay)=split(/-/o, $tmp1);
  ($locEndHour, $locEndMin, $locEndSec)=split(/:/o, $tmp2);
  
  # In statisticsMode we have special date settings as 
  # we have calendar weeks and calendar months not just weeks
  # and months. 
  # So the start and end date have usually to be modified by 
  # simply creating an instance of statistics and then getting
  # the modified dates.
  if( $statisticsMode ){
      $startDate="$startYear-$startMon-$startDay";
      $startTime="$startHour:$startMin:$startSec";
      $endDate="$endYear-$endMon-$endDay";
      $endTime="$endHour:$endMin:$endSec";
      # Create an instance of statistics Class and let it 
      # set the start and end dates as it would do, some parameters 
      # are not important here and simple dummies ($tmp)
      $statisticsMode=statistics->new($tmp, $startDate, $startTime, 
                            $endDate, $endTime,  $sampleTime, $tmp, $tmp, 
			    $refNow, $refFirst );
      #
      # Split up modified values again 
      ($startYear,$startMon, $startDay)=split(/-/o, $statisticsMode->{"startDate"} );
      ($startHour, $startMin, $startSec)=split(/:/o, $startTime=$statisticsMode->{"startTime"} );

      ($endYear,$endMon, $endDay)=split(/-/o, $statisticsMode->{"endDate"} );
      ($endHour, $endMin, $endSec)=split(/:/o, $statisticsMode->{"endTime"} );

      # Get error/Warning messages from date modifications in statistics package
      $errStr.=$statisticsMode->getDateErrors();
      $valid=0 if( length($errStr) );
  }

				   
  # Check if start or  end date is after today
  # and possibly set endDate to today
  # check only date not time, since endtime is usually the end
  # of the current day (23:59:59) but not the current time
  ($tmp1, $tmp2, $tmp3, $tmp4)=
  Delta_DHMS( $endYear, $endMon, $endDay, $endHour, $endMin, $endSec,
		 $nowYear, $nowMon, $nowDay, $nowHour, $nowMin, $nowSec );
  if( $tmp1 *24+$tmp1 <= -24 ){
       $errStr.="Das angegebene Enddatum ".
                "($locEndDay.$locEndMon.$locEndYear $locEndHour:$locEndMin:$locEndSec) " .
		" liegt in der Zukunft.<br>";       
       $endYear=$nowYear; $endMon=$nowMon; $endDay=$nowDay;
       $valid=0;
  }

  # check if start is before first entry
  if(Delta_Days( $firstYear, $firstMon, $firstDay,
	      $startYear, $startMon, $startDay) < 0 ){
       $errStr.="Das angegebene Startdatum ". 
                "($locStartDay.$locStartMon.$locStartYear $locStartHour:$locStartMin:$locStartSec) " .
		"liegt vor dem ersten Datenbankeintrag.<br>";
       $startYear=$firstYear; $startMon=$firstMon; $startDay=$firstDay;
       $valid=0;
  }

  # Check if startdate is before now
  ($tmp1, $tmp2, $tmp3, $tmp4)=
    Delta_DHMS( $startYear, $startMon, $startDay, $startHour, $startMin, $startSec,
	      $nowYear, $nowMon, $nowDay, $nowHour, $nowMin, $nowSec);

  if( $tmp1 < 0 || $tmp2 < 0 || $tmp3 < 0 || $tmp4 < 0 ){
       $errStr.="Das angegebene Startdatum " .
                "($locStartDay.$locStartMon.$locStartYear $locStartHour:$locStartMin:$locStartSec) " .
		"liegt in der Zukunft.<br>";
       $startYear=$nowYear; $startMon=$nowMon; $startDay=$nowDay;
       $startHour=0; $startMin=0; $startSec=0;
       $valid=0;
  }

  $startDate=sprintf("%04d-%02d-%02d", $startYear,$startMon, $startDay);
  $startTime=sprintf("%02d:%02d:%02d", $startHour,$startMin, $startSec);
  $endDate=sprintf("%04d-%02d-%02d", $endYear,$endMon, $endDay);
  $endTime=sprintf("%02d:%02d:%02d", $endHour,$endMin, $endSec);

  return(($startDate,$startTime, $endDate, $endTime, $valid, $errStr));
}


#
# Add one or more CGI-Parameters to an URL
#
sub addUrlParm{
   my($url, @param)=@_;
   my($i, $param);

   for($i=0; $i<=$#param; $i++){
      $param=$param[$i];
      next if( !length($param) );
      if( $url=~/\?[a-zA-Z]/ ){
   	   $url="$url;$param";
      }else{
   	   $url="$url?$param";
      }
   }
   return($url);
}


#
# Find closest match of data set in table to given date and extract
# given colums. This function may be called to extract a value at a 
# certain past time, or it may be called to extract the sum of EXACTLY
# ONE value since a past time up to now. This is needed for the
# rain sensor to calculate eg the rain that fell in the last 48h
# In this case as said @cols may contain exactly ONE colum name!
# The function return 0 on failure else 1.
#
sub findRowDateMatch{
   my($date, 		# Reference date (eg: now()) in: y,mo,d,h,mi,s
      $hoffset,		# Offset in hours
      $moffset,		# Offset in minutes
      $refResults,	# reference to array with results
      $table,		# Name of table
      $stationId,	# Id of weather station
      $sensId,		# The sensors id
      $sum,		# Return Sum of col vals (for rain) or single value
      @cols)=@_;	# database colums to get

   my($i, $j, $sql, $result1Ref, $result2Ref, $id, $offset);
   my(@date1, @date2, @rDate, $rTime, $refResult, $dateRef);
   my($dateStr,$year, $month,$day, $h, $m, $s, $cols, $tmp1, $tmp2); 
   
   $offset=($hoffset*60)+$moffset;
   # Contruct reference date in textual form like in mysql db: 
   # "2004-01-18 08:59:00"
   ($year, $month,$day, $h, $m, $s)=split(/\s*,\s*/, $date);
   $dateStr=sprintf("%04d-%02d-%02d %02d:%02d:%02d", $year, $month, 
                                                    $day, $h, $m, $s);
   $cols=join(",", @cols);
   $cols=~s/datetime,//;  # Will be added below
   $sql="SELECT id,datetime, $cols FROM $table ";
   $sql.="WHERE ${table}.stationid = $stationId AND ${table}.sensid=$sensId AND ${table}.datetime >= " . 
         "\"$dateStr\" - INTERVAL $offset MINUTE " .
	 "ORDER by datetime ASC LIMIT 1";
	 
   #print "Date: $date <br>\n";
   #print "*** $sql <br>\n";
   # Get Dataset that mysq finds close to the given date
   $result1Ref=$dbh->selectrow_hashref($sql);
   
   # There was no matching row, so we simply fetch the latest existing one
   if( !defined($result1Ref) ){ 
   	$sql="SELECT id,datetime, $cols FROM $table ";
	$sql.="WHERE stationid = $stationId AND sensid=$sensId ORDER by datetime desc LIMIT 1";
        #print "**+ $sql <br>\n";
	$result1Ref=$dbh->selectrow_hashref($sql);
	return(0) if( !defined($result1Ref) );
   }
   # Convert Date and time field of row found into array suitable for Date:Calc
   ($tmp1,$tmp2)=split(/\s/o, $result1Ref->{"datetime"});
   @date1=( split(/-/o,$tmp1), split(/:/o, $tmp2) );
   
   # Now get the row that comes right before the one retrieved above
   # Its id col must be at least 1 smaller with the same sensor id value.
   $id=$result1Ref->{"id"};
   $sql="SELECT id,datetime,$cols FROM $table ";
   $sql.="WHERE stationid = $stationId  AND sensid=$sensId AND id < $id ORDER BY id desc LIMIT 1";
   #print "*** $sql <br>\n";

   $result2Ref=$dbh->selectrow_hashref($sql);
   return(0) if( !defined($result2Ref) );	 
   ($tmp1,$tmp2)=split(/\s/, $result2Ref->{"datetime"});
   @date2=( split(/-/o, $tmp1), split(/:/o, $tmp2) );
   
   # Now find out which of both dates is closer to the reference date
   # First subtract given number of hours from reference date   
   @rDate=Add_Delta_DHMS($year, $month,$day, $h, $m, $s, 0, 0, -1*$offset, 0);
   $rTime=Date_to_Time(@rDate);
   
   #print "+ @date1;; @date2 <br>\n";
   # For the rain table we may never lock back past now-offset, so skip the
   # comparison of the two dates in this case and use the first one
   if( $table !~ /rain/io ){   
      if( abs($rTime-Date_to_Time(@date1)) >
          abs($rTime-Date_to_Time(@date2))
        ){
        $refResult=$result2Ref;
        $dateRef=\@date2;
      }else{
        $refResult=$result1Ref;
        $dateRef=\@date1;
      }
   }else{
        $refResult=$result1Ref;
        $dateRef=\@date1;      
   }
    
   # print "dateNow: $date; RefDate: @rDate; Row_date: @$dateRef; Offset: $offset <br>\n";
   # If the offset (eg now-20min) is less then 20min for a T7H-value 
   # we allow an error of 75% of the offset for the date in a row found and the
   # date wanted (now-offset==$rTime).
   if( $table =~ /th/io && $offset <= 30 ){ 
      if( abs($rTime-Date_to_Time(@{$dateRef})) >  int(0.75*$offset*60) ){
           return(0);
      }
   # In case we are looking for rain values we allow only rows that are closer
   # to "now" than the given offset time. So rows with a date older than 
   # now -offset are rejected because this would lead to wrong values for 
   # rainsum values. 
   }elsif( $table =~/rain/io ) {
      $tmp1=$rTime-Date_to_Time(@{$dateRef});
      #print "* (now-offset)...rowdate found (min, h): ", $tmp1/60, ", h: ", $tmp1/60/60, " <br>\n";
      if( $tmp1 > 0 ){
           #print ":$table, returned<br>\n";
	   return(0);
      }    
   # For all other situations the error between the referenztime wanted and the
   # and the row found we allow an error of no more than 30min.   
   }else{
      if( abs($rTime-Date_to_Time(@{$dateRef})) >  30*60 ){
           return(0);
      }
   }   

   # Debug:
   #print $refResult->{"date"} ." " . $refResult->{"time"} . "\n";

   # if sums were requested we need to sum up all values from the row found 
   # ($resultRef) up to now
   if( $sum ){
     return(0) if( $#cols >=1 );
     $j="SUM(" . $cols[$#cols] . ")"; 
     $cols[$#cols]="$j";
     $sql="SELECT $j FROM $table ";
     $sql.="WHERE  stationid = $stationId AND id >= " . $refResult->{"id"} . " AND ";
     $sql.="sensid=$sensId AND datetime<=" . 
           "\"$dateStr\"";
     # Get Dataset that mysq finds close to the given date
     $refResult=$dbh->selectrow_hashref($sql);
     #print "-> $sql <br>\n";
     return(0) if( !defined($refResult) );
   }

   
   # Enter Results of row that was closest to given time
   for($i=0; $i<=$#cols; $i++){
   	$refResults->[$i]=$refResult->{$cols[$i]};
	# Debug:
	#print "$cols[$i]: $refResult->{$cols[$i]} \n";
   }
   return(1); # OK
}



#
# Get latest values from sensors for all sensors given in \%$sens
#
sub getLatestValues{
   my($dbh) =shift;
   my($sensorData)=shift;
   my($sens)=shift;
   my(@now)=@_;
   my($i, $j, $k, $l, $sql, $sth, $table, @res, @res1);
   my($dbcols, $qdbcols, @dbCols, $tmp, $tmp1, $tmp2, $stationId);
   my($ret, $sum, @cols, $hour, $minute,$unitFactor, $dbColName,
      $midnightDate, $midnightTime, $midnightDateGMT, $midnightTimeGMT, $dayEndTime);

   my($station, $sensorId);

   
   foreach $i (keys(%{$sens})){
      $table=${$sens}{$i}->{"table"};
      # compile list of db colums to be selected
      # And enter each value in array @dbcols (needed below)
      $dbcols="";
      $qdbcols="";
      undef(@dbCols);
      for($j=0; $j<=$#{${$sens}{$i}->{"getDbcols"}}; $j++){
      		$tmp=${$sens}{$i}->{"getDbcols"}[$j];
		$dbcols.="$tmp," ;
		$qdbcols.="`$tmp`," ; # Quoted version of column names for SQL-statement
		push(@dbCols, $tmp); 
      }
      chop($dbcols);  # Remove last ","
      chop($qdbcols);  
      $stationId=$sens->{"$i"}->{"stationId"};  # Id of weather station

      # Iterate over all sensorIds of one sensortype
      foreach $j ( @{${$sens}{$i}->{"sensorids"}} ){
	 $dbColName=$dbcols;
	 # The sensorids defined by the user in latest_th[] may be of the format
	 # sensorId.stationid. Here we have to split both values to get the right data
	 ($sensorId, $station)=split(/\./o, $j, 2);
	 $stationId=$station if( length($station) );
         # Only start sql query if there are dbcols to be retrieved by the sensors
	 # description and if this value is != "-" (rainsensor). The rainsensor is
	 # handled differently below
      	 if( length($dbcols) && $dbcols ne "-" ){
	    $sql="SELECT $qdbcols FROM $table WHERE stationid = $stationId AND sensid=$sensorId";
	    #$sql.=" ORDER by datetime DESC,id DESC LIMIT 2";
	    $sql.=" ORDER by datetime DESC LIMIT 2";
	    # Query database for min, max and average of sensor
	    $sth = $dbh->prepare($sql);
	    $sth->execute;
	    # Fetch the latest rows. We need two for values that encode a difference
	    # like the rain sensor
	    @res= $sth->fetchrow_array;
#	    @res1=$sth->fetchrow_array if( ${$sens}{$i}->{"type"}=~/RA/o );
	 }
	 # if there is a datediff value given, than we need to fetch
	 # the latest entry and the first one of the date given in
	 # datediff. This is needed eg for calculating how much rain
	 # fell "today"
	 if( ${$sens}{$i}->{"datediff"} ){
	    $dbColName=${$sens}{$i}->{"dbcolName"};
	    $unitFactor=${$sens}{$i}->{"unitfactor"}->{"$dbColName"};

            $midnightDate=${$sens}{$i}->{"datediff"};  # date of day for which to calculate sum
	    $midnightTime="00:00:00";                  # starting from midnight
	    $dayEndTime="23:59:59";		       # Day end time
	    #
	    # Since the database stores dates in GMT we have to calculate what GMT time 
	    # corresponds to the local time "midnight" 
      	    ($midnightDateGMT, $midnightTimeGMT)=timeConvert($midnightDate, $midnightTime, "GMT");
	    # Now calculate what GMT time corresponds to local time "end of day"
      	    ($midnightDate, $dayEndTime)=timeConvert($midnightDate, $dayEndTime, "GMT");
    
	    # Now select data that is between midnight(GMT) and end of day(GMT)
      	    $sql="SELECT SUM($dbColName) AS \"SUM\" FROM $table WHERE stationid = $stationId AND" .
	         " datetime>=\"$midnightDateGMT $midnightTimeGMT\" AND" .
	         " LEFT(datetime,10) <=\"$midnightDate $dayEndTime\" AND sensid=$sensorId";
	    @res=$dbh->selectrow_array($sql);
            $tmp=$res[0] * $unitFactor;
            $tmp=int($tmp*100)/100;
    	    ${$sens}{$i}->{"sensorval"}->{"$j"}->[0]->{$dbColName}=$tmp;
	 }
	 if( $#res >=0 ){
	    # if not the rain sensor enter the results in hash
	    # for the rain sensor this has been done above
	    if( ! ${$sens}{$i}->{"datediff"} ){
               # Store results in sensor hash. Both results res and res1 are stored
	       # in index [0] and [1] respectively. Each value is stored in a
	       # hash with the db column name for this value like ...->[0]->{P}=1013
	       for($k=0; $k <= $#dbCols; $k++){
	    	   if(${$sens}{$i}->{"unitfactor"}->{$dbCols[$k]} ){
		      $tmp=$res[$k] * ${$sens}{$i}->{"unitfactor"}->{$dbCols[$k]};
		      $tmp=int($tmp*100)/100;
		      ${$sens}{$i}->{"sensorval"}->{"$j"}->[0]->{$dbCols[$k]}=$tmp;
		      				
		   }else{
		      ${$sens}{$i}->{"sensorval"}->{"$j"}->[0]->{$dbCols[$k]}=$res[$k];
		   }
	       }
	    }
	 }else{
            warn "Error getting latest values running \"$sql\"\n";
	 }
	 
         # Determine trendData, eg rain in last h, last 12 hrs and last 24 hrs
	 if( length($dbColName) && $dbColName ne "-" ){
	    #@now=Today_and_Now(0);
            $tmp1=0;
	    @cols=split(/\s*,\s*/, $dbColName);
	    foreach $k ( @{${$sens}{$i}->{"trendData"}} ){
	       if( $k !~ /:/o ){
	          $hour=$k; $hour=~s/h$//o;
		  $minute=0;
	       }else{
	          # sensid, minutes = split()
		  ($tmp, $minute)=split(/\s*:\s*/o, $k);
		  next if( $tmp ne $sensorId );  
		  $hour=0; 	       	  
	       }
	       #warn "*** Sensor: $j, Offset: $k, Date: ", join(",", @now), " <br>\n";
	       #warn "*** DbCols: $dbcols <br>\n";
	       
	       undef @res;
	       $sum=0;
	       $sum=1 if( ${$sens}{$i}->{"type"}=~/RA/o );
	       $ret=findRowDateMatch( join(",", @now), $hour, $minute, \@res, $table, $stationId, $sensorId, 
	    			   $sum, @cols  );
	       if( $ret ){
		   # The values are stored in:
		   # $i: eg "rain"
		   # ${$sens}{$i}->{"trendDataValues"}->{id}->{colname}->[counter++]
		   for($l=0; $l<=$#cols; $l++){ #      {id}->{valuetype}->{counter]=...
		       $tmp=$cols[$l];			 # Name of column
		       if( $tmp =~ /diff/o ){
		       		$res[$l]*=${$sens}{$i}->{"unitfactor"}->{"diff"};
				$res[$l]=round($res[$l], 2);
				$tmp="-";	# rainsensor column Name
		       }
		       ${$sens}{$i}->{"trendDataValues"}->{$j}->{$tmp}->[$tmp1]=$res[$l];
		       #print "*** $i, $j:trend: ",${$sens}{$i}->{"trendDataValues"}->{$j}->{$tmp}->[$tmp1], " <-<br>\n";
		       #print  $res[$l];
		   }    
		   $tmp1++;
	       }else{   # No data were found so we enter "novalidvalue" as a result
		  for($l=0; $l<=$#cols; $l++){ #     
		     $tmp=$cols[$l];	       # Name of column
		     $tmp2="novalidvalue";
		     if( $tmp =~ /diff/o ){
			 $tmp="-";	# rainsensor column Name
			 $tmp2=0;
		     }
	             ${$sens}{$i}->{"trendDataValues"}->{$j}->{$tmp}->[$tmp1]=$tmp2;
		  }   
	          $tmp1++;
	       }
	    }
	 }   
      }#foreach $j
   }
}


#
# convert wind variance to a plus/minus value
#
sub windVar{
   my($refSensorVal)=shift;
   my($id)=shift;
   my($refLatestSens)=shift;
   my($colname)=shift; 

   return( $refSensorVal->{$id}->[0]->{"range"}/2 );

}


#
# Return the list of windspeed values for the beaufort scale
#
sub getWindSpeedList{
   return( (1.9,  7.4,  13,  20.4, 29.6, 40.7, 51.9, 63, 75.9, 88.9, 103.7, 118.5, 999)  );
}


#
# Return the list of winddirection names in angles of 22.5 from 0..337.5
#
sub getWindDirectionList{
   return( ("N","NNO","NO","ONO","O","OSO","SO","SSO","S","SSW","SW","WSW","W","WNW","NW","NNW") );
}


#
# Return the list of windspeed names for the beaufort scale corresponding to getwindSpeedList 
#
sub getWindSpeedNameList{
   return( ("Windstille", "leiser Zug", "leichte Brise", "schwache Brise", "m&auml;&szlig;ige Brise",
            "frische Brise", "starker Wind", "steifer Wind", "st&uuml;rmischer Wind",
	    "Sturm","schwerer Sturm","orkanartiger Sturm","Orkan") );
}


#
# Return list of abbreviated name list
#
sub getShortWindSpeedNameList{
   return( ("Windst.", "ls. Zug", "l. Brise", "s. Brise", "m.Brise",
            "f.Brise", "stk.Wind", "stf.Wind", "st&uuml;.Wind",
	    "Sturm","s. Sturm","o. Sturm", "Orkan") );
}


sub windDir2 {
	my($refSensorVal)=shift;
	my($id)=shift;
        my($refLatestSens)=shift;
	my($colname)=shift; 
	my($staerke,$richtung,$breite);
	my(@wr, $w, $path);

	$staerke=$refSensorVal->{$id}->[0]->{"speed"};
	$richtung=$refSensorVal->{$id}->[0]->{"angle"};
	$breite=$refSensorVal->{$id}->[0]->{"range"};

	@wr=getWindDirectionList();
        $w=int($richtung/22.5+0.5);
        if ($w ==16) {$w=0;}
	#return "$wr[$w], $richtung";
	# tommy: Windrose icon
	if( $refLatestSens->{"wind"}->{"latestWindRose"} ){
	   $path=$refLatestSens->{"wind"}->{"latestWindRoseUrl"};
	   return "$wr[$w], $richtung" . lc(" <img src='$path/$wr[$w].png'>");
	}else{
	   return "$wr[$w], $richtung";
	}
#        print "Windstaerke: $staerke Richtung: $richtung ( $wr[$w] ) Breite: $breite\n";

}

# Helper for windSpeed() with only the relevant parameters
sub doWindSpeed{
	my($staerke, $windSpeedType)=@_;
	my(@bf, @bfn, $i, $kmh);

	if( $windSpeedType == 1 ){ # speed is in knots
		$kmh=$staerke/$kmhToKnots; # convert back tp km/h
	}else{
		$kmh=$staerke;
	}
	#print "*** $staerke, $windSpeedType, $kmh <br>\n";

	@bf=getWindSpeedList();
	@bfn=getWindSpeedNameList();
             
        $i=0;
	for($i=0; $i<=$#bf; $i++){
                if ($kmh < $bf[$i]) {
                        last;
                }
        }
	return( ($i,$bfn[$i]) );
}

sub windSpeed {
	my($refSensorVal)=shift;
	my($id)=shift;
   	my($refLatestSens)=shift;
   	my($colname)=shift; # speed or gustspeed
	my($staerke, $richtung, $breite);
	my($f1, $ff, $bf, $bfStr, $kts);
	
	$f1="<FONT size=\"-1\">";
        $ff='</FONT>';

	$staerke=$refSensorVal->{$id}->[0]->{$colname};
	$richtung=$refSensorVal->{$id}->[0]->{"angle"};
	$breite=$refSensorVal->{$id}->[0]->{"range"};


	($bf,$bfStr)=doWindSpeed($staerke, $refLatestSens->{"wind"}->{"windSpeedType"});
	
	if( $refLatestSens->{"wind"}->{"windSpeedType"} == "10" ){
	    $kts=$staerke*$kmhToKnots;
	    $kts=int(100*$kts)/100;
	    return "$bf $f1($bfStr)$ff, $kts Kn, $staerke";
		
	}else{
	    return "$bf $f1($bfStr)$ff, $staerke";
	}
}


#
# the usual log 10 logarithmus instead of log e
#
sub log10{
   my($x)=shift;
   
   return( log($x) / log(10) );
}


#
# calculate  dewpoint from relative humidity and temperature
#
sub doDewPoint {
   my($t, $r)=@_;        # Temp and rel humidity
   my($dd, $sdd, $a, $b, $td, $v);
   
   if( $t >= 0 ){
   	$a=7.5; $b=237.3;
   }else{
   	$a=7.6; $b=240.7;
   }
   # see http://www.wettermail.de/wetter/feuchte.html
   # sdd: Saettigungsdampfdruck
   # dd: Dampfdruck
   # td: Taupunkt
   $sdd=6.1078 * 10.0**(($a*$t)/($b+$t));  # Magnusformel
   $dd=($r/100.0) * $sdd;
   if( $dd ){
      $v=log10(($dd/6.1078));
   }else{
      $v=0;
   }
   $td=($b*$v)/($a-$v);
   return( round($td, 2) );
}	


#
# calculate dew point
#
sub dewPoint{
   my($refSensorVal)=shift;
   my($id)=shift;
   my($refLatestSens)=shift;
   my($colname)=shift; 
   my($t, $r);
   
   # Simplify access to temp and hum
   $r=$refSensorVal->{$id}->[0]->{"H"};
   $t=$refSensorVal->{$id}->[0]->{"T"};

   if( $latest_do->{"th"}->{"$id"} =~ /dewpoint/i ){
	return doDewPoint($t, $r);   
   }else{
   	return( "novalidvalue" );   
   }   
}

#
# calculate  absolute himidity
#
sub doAbsHumidity{
   my($t,$r)=@_;  # temp and humidity
   my($dd, $a, $b, $ah);
   
   if( $t >= 0 ){
   	$a=7.5; $b=237.3;
   }else{
   	$a=7.6; $b=240.7;
   }
   # see http://www.sfdrs.ch/sendungen/meteo/lexikon/
   # sdd: Saettigungsdampfdruck
   # dd: Dampfdruck
   # td: Taupunkt
   $sdd=6.1078 * 10.0**(($a*$t)/($b+$t));  # Magnusformel
   $dd=($r/100.0) * $sdd;
   $ah=216.68*($dd/($t+273.15));

   return( round($ah, 2) );
}


#
# calculate absolute humidity
#
sub absHumidity{
   my($refSensorVal)=shift;
   my($id)=shift;
   my($refLatestSens)=shift;
   my($colname)=shift; 
   my($t, $r);

   # Simplify access to temp and hum
   $r=$refSensorVal->{$id}->[0]->{"H"};
   $t=$refSensorVal->{$id}->[0]->{"T"};
   #$p=${$refLatestSens}{"pressure"}->{"sensorval"}->{20}->[0]->{"P"};


   if( $latest_do->{"th"}->{"$id"} =~ /abshum/i ){
   	return( doAbsHumidity($t, $r) );   
   }else{
   	return( "novalidvalue" );
   }	
}


#
# calculate  dewpoint from relative humidity and temperature
# see: http://www.sfdrs.ch/sendungen/meteo/lexikon/
# see http://www.msc.ec.gc.ca/education/windchill/science_equations_e.cfm
# see http://meteo.lcd.lu/papers/windchill/newwindchill.html
# see http://www.moehnesee-wetter.de/infos/wetter_faq.html
# each formula is somehow different ... :-)
#
sub doWindChill {
   my($t, $v, $windSpeedType)=@_;
   my($chill);

   # The formula below is based on F and mp/h instead of C and km/h
   #$v=$v*0.62137119;  # Km/h -> mp/h
   #$t=1.8*$t+32;      # C -> F
   
   
   if( $windSpeedType == 1 ){ 
        # speed is in knots, have to convert it to km/h first
   	$v/=$main::kmhToKnots;
   }
   
   $chill= $t;
   # Formula only valid if $v > 1.4m/s (3mph)
   if( $t <= 11 ){
      if( $v >= 5 ) {
	 # This formula is only valid if $t <=11 und $v >= 5
	 # see: http://de.wikipedia.org/wiki/Windchill
	 $chill=13.12 + 0.6215*$t - 11.37 * $v**0.16 + 0.3965*$t * $v**0.16;
	 # Another formula:
	 # This formula is only valid if $t < 33
	 #$chill= 33 + (0.478+(0.237*sqrt($v))-0.0124*$v)*($t-33);
      }
   }
   $chill=round($chill, 2);

   return($chill);
}

   
#
# calculate wind chill 
#
sub windChill{
   my($refSensorVal)=shift;
   my($id)=shift;
   my($refLatestSens)=shift;
   my($colname)=shift; 
   my($t, $v, $tempId, $res);

   # check if user configured display of windchill for this sensor id in global $latest_do->{}
   $tempId=$latest_do->{"wind"}->{"$id"};   # == eg "WindChill(30),DewPoint"
   $tempId=~s/.*windchill\(([0-9.]+)\).*$/\1/i; 
   # Simplify access to windspeed and hum
   if( $main::latestWindChillUseGustSpeed ){
      $v=${$refLatestSens}{"wind"}->{"sensorval"}->{$id}->[0]->{"gustspeed"};  
   }else{
      $v=${$refLatestSens}{"wind"}->{"sensorval"}->{$id}->[0]->{"speed"};
   }
   $t=${$refLatestSens}{"temp"}->{"sensorval"}->{$tempId}->[0]->{"T"};

   if( $v <=0 ){
	return( "-" );
   }else{
	$res= doWindChill($t, $v, $refLatestSens->{"wind"}->{"windSpeedType"});
	return ($res);   
   }	
}


#
#
# Get Sum of yesterday's errors for a sensor
#
sub getSensErr{
    my($sensorId, $stationId, $table)=@_;
    my($year, $month, $day, $h, $m, $s, $now, $yesterday, 
       $sql, $sth, @errors, $errors);

    ($year, $month, $day, $h, $m, $s)=Today_and_Now(1);    
    $now=sprintf("%04d-%02d-%02d %02d:%02d:%02d\n", $year, $month, 
                                                    $day, $h, $m, $s);
    ($year, $month, $day, $h, $m, $s)=
    	Add_Delta_DHMS(Today_and_Now(1), 0,-$latestAlertHours, 0, 0);
    $yesterday=sprintf("%04d-%02d-%02d %02d:%02d:%02d\n", $year, $month, 
                                                    $day, $h, $m, $s);

    $sql="SELECT COUNT(ok) FROM $table WHERE ok=0 AND " .
         "stationid REGEXP $stationId AND sensid=$sensorId AND ".
         "datetime>=\"$yesterday\" AND datetime<=\"$now\"";

    $sth=$dbh->prepare($sql);

    $sth->execute;
    @errors=$sth->fetchrow_array;
    $errors=@errors[0];

    return($errors);
}



#
# Print out the latest data values fetched before from the database
# All values are in a hash to which a reference is passed to this function
#
sub printLatestData{
   my($refLatestSens)=shift;    # is a Reference to hash
   my($stype)=shift;
   my($latestTab)=shift;
   my($sens, $id, $i, $j, $k, $dateDiff, $tmp, $tmp1, $tmp2, @val1, @val2);
   my($name, $colCount, $colName, $referenceValue, $stationId);
   my($f1, $f2, $f3, $fc, $fcc, $err, $faktor, $dbType, $table);
   my($station, $sensorId);
   
   $fc='<FONT color="##">';
   $fcc="</FONT>";

   $sens=$refLatestSens->{$stype};
   $stationId=$sens->{"stationId"};
   $table=$sens->{"table"};   # Table of sensor to be printed

   # Get type name in database for internal type of sensor
   $dbType=main::mapTypeName2DbName($stype);
   $dbType="UNKNOWN" if( !defined($dbType) ); # will lead to failure of select below


   $dateDiff=$sens->{"datediff"};
   # Iterate over all sensorids from the type $i
   for($j=0; $j<= $#{$sens->{"sensorids"}}; $j++ ){
      # Get values (raw row) from databse table
      $latestTab->newRow() if( $j >0 );

      $id=$sens->{"sensorids"}->[$j];
      # The sensorids defined by the user in latest_th[] may be of the format
      # sensorId.stationid. Here we have to split both values to get the right data
      ($sensorId, $station)=split(/\./o, $id, 2);
      $stationId=$station if( length($station) );

      $name=$dbh->selectrow_array(
          "SELECT name FROM sensor_descr WHERE stationid = $stationId AND " .
	  "sensid=$sensorId AND type='$dbType'"  
	);

      if( !length($name) ){
      	$name="<FONT class=\"latestRowHeader\" id $sensorId </FONT>";
      }
      
      # Get errors from database for this sensor
      $err=getSensErr($sensorId, $stationId, $table) if( $latestAlertErrCount );
      if ($latestAlertErrCount && $err > $latestAlertErrCount){
        print "<FONT class=\"latestRowHeader\" color=$latestAlertColor>","$name \($err\)",":</FONT>";
      }else{
        print "<FONT class=\"latestRowHeader\">","$name",":</FONT>";
      }
      
      $latestTab->newCol();

      # Iterate over all database columns (values) to be printed for that sensor
      $colCount=$#{$sens->{"dbcols"}};
      $kCount=0;
      for($k=0; $k <= $colCount; $k++ ){
	     # store value to print
	     $colName=$sens->{"dbcols"}[$k];
	     next if( $latest_omit{$id} eq $colName );
	     $latestTab->newCol() if( $kCount>0 );
	     $kCount++;

	     $tmp1=$sens->{"sensorval"}->{$id}->[0]->{$colName};
	     # check if there is an converter for this value defined
	     if( $sens->{"converter"}->[$k] ){
	     	 $tmp=$sens->{"converter"}->[$k];
		 # call converter
		 $tmp1=&$tmp($sens->{"sensorval"}, $id, $refLatestSens, $colName);
	     }
	     $referenceValue=$tmp1;  # Keep The value to print in mind. Its used for
	     			     # the output of the trenData below.
	     		
	     # Don't print value ?
	     if( $tmp1 eq "novalidvalue" ){
	     	print "&nbsp;";
		next;
	     }

	     # Print Name of value if any
	     print '<FONT class="latestTabText">', 
	            $sens->{"valuename"}->[$k], ": ",
		    '</FONT>'
	                        if(length($sens->{"valuename"}->[$k]));
	     
	    	    
	     if ($sens->{"factor"}->[$k] gt '' ){
		$faktor=$sens->{"sensorval"}->{$id}->[0]->{"factor"};
			$tmp1*=$faktor;
             }
	     if( !length($dateDiff) ){
	 	 print '<FONT class="latestTabText">', $tmp1,
		 " ", $sens->{"sensorunits"}->[$k],
		 '</FONT>' ;
	     }else{
		 # This is the rain sensor
		 $tmp=$sens->{"dbcolName"};
		 $tmp2=$sens->{"sensorval"}->{"$id"}->[0]->{$tmp};

		 # Colorize printed value if wanted
		 if( $sens->{"sensorcolor"}->[$k] && $tmp2 != 0 ){
		 	$tmp=$fc;
			$tmp=~s/##/$sens->{"sensorcolor"}->[$k]/;
	 	 	print '<FONT class="latestTabText">',
				$tmp,$tmp2, $fcc,
				'</FONT>';
		 }else{
	 	 	print '<FONT class="latestTabText">', 
				$tmp2,'</FONT>'; 
		 }
		 print '<FONT class="latestTabText">', " ",
		       $sens->{"sensorunits"}->[$k], 
		       '</FONT>';
	     }

	     # User specified threshhold values for trend data
	     # display. See below.
	     $f1=$sens->{"trendThreshold"}->{"$colName"}->[0];
	     $f2=$sens->{"trendThreshold"}->{"$colName"}->[1];
	     $f3=$sens->{"trendThreshold"}->{"$colName"}->[2];
   
	     # For sensors like temp, pressure print a tendency symbol (arrow up
	     # or arrow down) if there is a trend visible for this value
	     if( $sens->{"trendThreshold"}->{"$colName"}->[0] && 
	         length($sens->{"trendDataValues"}->{$id}->{"$colName"}->[0]) &&
		  $sens->{"trendDataValues"}->{$id}->{"$colName"}->[0] ne "novalidvalue" ){
                 #warn "*** $id:",$sens->{"trendThreshold"}->[$k],":",$referenceValue,":",
                 #         $sens->{"trendDataValues"}->{$id}->{"$colName"}->[0], ":", $sens->{"trendThreshold"}->[$k], "\n";
		 $tmp=$referenceValue - $sens->{"trendDataValues"}->{$id}->{"$colName"}->[0];
		 $tmp= round($tmp, 2);
		 $tmp1=abs($tmp);
		 #$tmp1=int($tmp1*100+0.5)/100;

		 #print " >$referenceValue : $colName,", $sens->{"trendDataValues"}->{$id}->{"$colName"}->[0], " \n";
		 #print " >$tmp1, $f1, $f2, $f3< ";
		 $i=-1;
		 if( $tmp1 >= $f1){
		      if( $tmp1 >= $f1 && $tmp1 < $f2 ){
			      $i=0;
			      $tmp2= ($tmp>=0)? $sens->{"trendSymbUp"}->[$i]: $sens->{"trendSymbDown"}->[$i];
		      }elsif( $tmp1 >= $f2 && $tmp1 < $f3 ){
		      	      $i=1;
			      $tmp2= ($tmp>=0)? $sens->{"trendSymbUp"}->[$i]: $sens->{"trendSymbDown"}->[$i];
		      }elsif( $tmp1 >=$f3 ){
		      	      $i=2;
			      $tmp2= ($tmp>=0)? $sens->{"trendSymbUp"}->[$i]: $sens->{"trendSymbDown"}->[$i];
		      } 

		      # What is to be printed ?
		      $tmp="+$tmp" if( $tmp >0);
		      if( $sens->{"trendSymbMode"} eq "symbol" ){
		         print '<FONT class="latestTabText">',
			 	" &nbsp;$tmp2",
				'<FONT>';
		      }elsif( $sens->{"trendSymbMode"} eq "symbol+value" && $i >= 0 ){
		      	 print '<FONT class="latestTabText">',
			 	"&nbsp;$tmp2 &nbsp;",
				'<FONT>';
			 print "<FONT class=\"latestTabText\" color=\"", $sens->{"trendSymbTextCol"}->[$i], "\" size=\"", 
			                                           $sens->{"trendSymbTextSize"}, "\">";
			 print "($tmp) </Font>\n";
		      }elsif( $sens->{"trendSymbMode"} eq "value" && $i >= 0 ){
			 print "<FONT class=\"latestTabText\" color=\"", $sens->{"trendSymbTextCol"}->[$i], "\" size=\"", 
			                                           $sens->{"trendSymbTextSize"}, "\">";
			 print " &nbsp;($tmp) </Font>\n";
		      }
		 }
	     }
      }

      # Now print trendData like rain in last h, last 12h, last 24h
      # Because we want to print difference values (current sensor value -
      # sensors value eg 12 hours ago) we need this reference value i.e. the current value
      # This values is stored above in $referenceValue. This however will ONLY WORK this
      # way if for this sensor we print only ONE Last value and then the trendData. This 
      # condition holds for pressure and rain sinve there only one value is printed in the 
      # latest data. If someone wants to implement some day trendData for a sensor with
      # more than one value the simple referenceValue trick will not do the job.
      for($k=0; $k <= $#{$sens->{"trendData"}}; $k++ ){
	$colName=$sens->{"getDbcols"}->[0];
        # Decide if we want to display several trendData values
	if( $sens->{"trendDataDisplay"} ){
	     $latestTab->newCol();       
	     if( length($sens->{"trendData"}->[$k])){
		     $tmp=$sens->{"trendDataValues"}->{$id}->{"$colName"}->[$k];
		     $tmp="+$tmp" if( $tmp > 0 );
		     if( length($dateDiff) ){	# Rain sensor ?
			     $tmp=$sens->{"trendDataValues"}->{$id}->{"$colName"}->[$k];
			     #print "id: $id; colName: $colName; k: $k; tmp: $tmp <br>\n";
			     if( $sens->{"sensorcolor"}->[0] && $tmp != 0 ){
	 	 		$tmp="$fc $tmp $fcc";
				$tmp=~s/##/$sens->{"sensorcolor"}->[0]/;
			     }   
			     print '<FONT class="latestTabText">',
			     	   "(", $sens->{"trendData"}->[$k], ":)&nbsp; ", $tmp,
				     " ", $sens->{"trendDataUnits"}->{"$colName"},
				    '</FONT>';
		     }else{
     #		print "*** $id: $referenceValue, $k, ". $sens->{"trendDataValues"}->{$id}->{"$colName"}->[$k] . "\n";
			     $tmp=$referenceValue - $sens->{"trendDataValues"}->{$id}->{"$colName"}->[$k];
			     $tmp="+$tmp" if( $tmp > 0 );
			     print '<FONT class="latestTabText">',
			           "(", $sens->{"trendData"}->[$k], ":)&nbsp; ", $tmp,
				     " ", $sens->{"trendDataUnits"}->{"$colName"},
				   '</FONT>';
		     }		
	     }
	}
      }	
   }
}


#
# print maximum, minimum, average values in textual
# (html) presentation
#
sub printMmaValues{
   my($dataManager)=shift; 
   my($refSensor)=shift;
   my($width)=shift;
   my($height)=shift;
   my($fs)=shift;         # Fontsize decrease
   my($plotsSelected)=shift;  # print MMA values for virtual sensors
   my($sampleTime)=shift;

   my($i, $j, $k, $tmp, $tmp1, $sensorName, $col, $colName, $colValue, $sensId, $refMma);
   my($min, $max, $avg, $minDate, $minUnit, $maxDate, $maxUnit,
      $minTime, $maxTime, $avgUnit, $tot, $totUnit, $hasMin);
   my($printVirt, @d); 
   my(%omit);  
   
   
   # Print table header 
   print "<TABLE $width $height " . ' border="1" cellspacing="0" cellpadding="1"> ',
      '<THEAD>',
      "<TR><TH class=\"mmaTabHeader\"><FONT size=$fs>Sensor</FONT></TH> ".
      "<TH class=\"mmaTabHeader\"><FONT size=$fs>Min</FONT></TH> " .
      "<TH class=\"mmaTabHeader\"><FONT size=$fs>Max</FONT></TH> ". 
      "<TH class=\"mmaTabHeader\"><FONT size=$fs>Avg</FONT></TH> ";

   
   if( defined($refSensor->{"gettotal"}) ){
	print "<TH class=\"mmaTabHeader\"><FONT size=$fs>Tot</FONT></TH></TR></THEAD> <TBODY>\n";
   }else{
	print '</TR></THEAD> <TBODY>', "\n";
   }
   
   # Build up hash with column names to omit from @mmaOmit 
   foreach $i (@{$refSensor->{"mmaOmit"}}){
   	$omit{$i}=1;
   }

   # Iterate over all sensor ids of this sensor
   for($i=0; $i<= $#{$refSensor->{"sensIds"}}; $i++){
      $hasMin=$refSensor->{"mmaHasMin"};
      
      $sensId=$refSensor->{"sensIds"}->[$i];

      # Use sensor name from database if possible
      $sensorName=$refSensor->{"sensorDbNames"}->["$sensId"];      
      $sensorName="(id: $sensId)" if( !length($sensorName) );
      
      $refMma=$dataManager->{"results"}->{$sensId}->{"mma"};
      
      $k=$#{$refSensor->{"mmaDBCol"}};
      
      # Iterate over all columns for MMA output
      for($j=0; $j<= $k; $j++){
   	$col=$refSensor->{"mmaDBCol"}->[$j];
	next if( $omit{$col} );
	$colName=$refSensor->{"mmaNames"}->[$j];
	$colValue=$refMma->{"$col"}->{"minValue"};
	
	#print "\n<TR>\n";
	#print "<TD class=\"mmaTabRowHeader\"><FONT size=$fs>", 
	#      "$colName", "</FONT></TD> ";
	      
        # Minimum value for current sensor
	if( $hasMin ){
	   $min=    $refMma->{"$col"}->{"minValue"};
	   $minDate=$refMma->{"$col"}->{"minDate"};
	   $minTime=$refMma->{"$col"}->{"minTime"};
	   $minUnit=$refSensor->{"mmaUnits"}->[$j];
   	   ($minDate, $minTime)=timeConvert($minDate, $minTime, "LOC");
	   @d=split(/-/, $minDate );
	   $minDate="$d[2]-$d[1]-$d[0]";
	}else{
	   $min="&nbsp; - &nbsp;";
	   $minDate="";
	   $minTime="";
	   $minUnit="";
	}   


        # Maximum value for current sensor
	$max=    $refMma->{"$col"}->{"maxValue"};
	$maxDate=$refMma->{"$col"}->{"maxDate"};
	$maxTime=$refMma->{"$col"}->{"maxTime"};
	$maxUnit=$refSensor->{"mmaUnits"}->[$j];
   	if( defined($maxDate ) ){ 
	   ($maxDate, $maxTime)=timeConvert($maxDate, $maxTime, "LOC");
	   @d=split(/-/, $maxDate );
	   $maxDate="$d[2]-$d[1]-$d[0]";
	}else{
	   $maxDate="";
	   $maxTime="";
	}
	      
        # Average value for current sensor
	$avg=    $refMma->{"$col"}->{"avgValue"};
	$avgUnit=$refSensor->{"mmaUnits"}->[$j];
	
	# Total value mainly for rain sensor
	if( defined($refSensor->{"gettotal"})){
	   $tot=    $refMma->{"$col"}->{"total"};
	   $totUnit=$refSensor->{"totalUnit"};
	}

	# For wind sensor also print speed in BF units and in textual form
	$maxExtraTxt="";
	$avgExtraTxt="";
	if( $refSensor->{"sensType"}=~/^W[A-Z]/ && 
		$col =~ /speed/io  ){
	    ($tmp, $tmp1)=doWindSpeed($max, $refSensor->{"windSpeedType"});
	    $maxExtraTxt=" $tmp ($tmp1), ";	

	    ($tmp, $tmp1)=doWindSpeed($avg, $refSensor->{"windSpeedType"});
	    $avgExtraTxt=" $tmp ($tmp1), ";	
	}

	# Now print the values into a table
	print "\n<TR>\n";
	if( $k ){
	   # Print Name of Column together with Name of sensor if there are 
	   # multiple columns like temp, feuchte  to be printed for a sensor
	   print "<TD class=\"mmaTabRowHeader\"><FONT size=$fs>", $colName, "<br>", 
	         "($sensorName)", "</FONT></TD>";
	}else{
	   print "<TD class=\"mmaTabRowHeader\"><FONT size=$fs>", $sensorName, "</FONT></TD>";
	}
	print "<TD class=\"mmaTabText\"><FONT size=$fs>", "$min", " ", $minUnit, "</FONT><BR>",
		      "<FONT size=$fs>", $minDate,  "&nbsp; ",
		      $minTime, "</FONT>",
	      "</TD>\n";
	
	# For rain sensor when there is no rain and so no max-date
	if( length($maxDate) ){
  	   print "<TD class=\"mmaTabText\"><FONT size=$fs>", $maxExtraTxt, "$max", " ", $maxUnit, "</FONT><BR>",
		      "<FONT size=$fs>", $maxDate,  "&nbsp; ",
		      $maxTime, "</FONT>",
	      "</TD>\n";
	}else{
  	   print "<TD class=\"mmaTabText\"><FONT size=$fs>", $maxExtraTxt, "$max", " ", $maxUnit, "</FONT>",
	         "</TD>\n";
	   
	}

	print "<TD class=\"mmaTabText\"><FONT size=$fs>", $avgExtraTxt, "$avg", " ", $avgUnit, "</FONT>",
	      "</TD>\n";
	
        if( defined($refSensor->{"gettotal"}) ){
	   print "<TD class=\"mmaTabText\"><FONT size=$fs>", "$tot", " ", $totUnit, "</FONT>",
		 "</TD>\n";
	
	}
	print "</TR>\n";      	
      }
   }
   
   
   # The user may have selected that the mma start and end dates are
   # different from the start and end dates for the sensor display. 
   # This is a problem for mma values of virtual sensors since we only 
   # extracted the values needed for display the graphics but not for the 
   # possible larger timerange of mmaStart and -end dates. So we omit 
   # the mma values of virtual sensors if the user selected a mma
   # daterange that is different from the date range for graphics display
   $printVirt=1;
   if( $dataManager->{"options"}->{"mmaStartDate"} ne $dataManager->{"options"}->{"startDate"} ||
       $dataManager->{"options"}->{"mmaStartTime"} ne $dataManager->{"options"}->{"startTime"} ){
      $printVirt=0;
   }
   if( $sampleTime =~ /^.+,Min/ || $sampleTime =~ /^.+,Max/ ){
      $printVirt=0;
   }

   #
   # Now print MMA values of virtual Sensors
   #
   # Iterate over all virtual sensors defined
   if( $printVirt ){
      foreach $i (sort(keys(%{$refSensor->{"virtSens"}}))){
	  next if( ! $refSensor->{"virtSens"}->{$i}->{"active"} );
	  next if( $refSensor->{"virtSens"}->{$i}->{"active"} && 
	  	    ($refSensor->{"virtSens"}->{$i}->{"doPrintMma"} == 0) );
	  next if( !$plotsSelected && 
	           $refSensor->{"virtSens"}->{$i}->{"doPrintMma"} == 1 ); 

	  # Iterate over all sensor IDs of this virtual sensor
	  for($j=0; $j<= $#{$refSensor->{"sensIds"}}; $j++){
	     $sensId=$refSensor->{"sensIds"}->[$j];

	     # Use sensor name from database if possible
	     $sensorName=$refSensor->{"sensorDbNames"}->["$sensId"];      
	     $sensorName="(id: $sensId)" if( !length($sensorName) );
	     
	     #
	     # Iterate over all output values of virtual sensor "$i"
	     foreach $k (sort(keys(%{$dataManager->{"results"}->{"virtSens"}->{"$i"}->{$sensId}->{"mma"}}))){
		$min=$dataManager->{"results"}->{"virtSens"}->{"$i"}->{$sensId}->{"mma"}->{"$k"}->{"minValue"};
		$minDate=$dataManager->{"results"}->{"virtSens"}->{"$i"}->{$sensId}->{"mma"}->{"$k"}->{"minDate"};
		$minTime=$dataManager->{"results"}->{"virtSens"}->{"$i"}->{$sensId}->{"mma"}->{"$k"}->{"minTime"};
		$minUnit=$refSensor->{"virtSens"}->{"$i"}->{"out"}->{"$k"};
		@d=split(/-/, $minDate );
		$minDate="$d[2]-$d[1]-$d[0]";

		$max=$dataManager->{"results"}->{"virtSens"}->{"$i"}->{$sensId}->{"mma"}->{"$k"}->{"maxValue"};
		$maxDate=$dataManager->{"results"}->{"virtSens"}->{"$i"}->{$sensId}->{"mma"}->{"$k"}->{"maxDate"};
		$maxTime=$dataManager->{"results"}->{"virtSens"}->{"$i"}->{$sensId}->{"mma"}->{"$k"}->{"maxTime"};
		$maxUnit=$refSensor->{"virtSens"}->{"$i"}->{"out"}->{"$k"};
		@d=split(/-/, $maxDate );
		$maxDate="$d[2]-$d[1]-$d[0]";

		$avg=$dataManager->{"results"}->{"virtSens"}->{"$i"}->{$sensId}->{"mma"}->{"$k"}->{"avgValue"};
		$avgUnit=$refSensor->{"virtSens"}->{"$i"}->{"out"}->{"$k"};

		print "\n<TR>\n";
		print "<TD class=\"mmaVirtTabRowHeader\"><FONT size=$fs>", "$k<br>($sensorName)", "</FONT></TD>";

		print "<TD class=\"mmaVirtTabText\"><FONT size=$fs>", "$min", " ", $minUnit, "</FONT><BR>",
			    "<FONT size=$fs>", $minDate,  "&nbsp; ",
			    $minTime, "</FONT>",
		    "</TD>\n";

		print "<TD class=\"mmaVirtTabText\"><FONT size=$fs>", "$max", " ", $maxUnit, "</FONT><BR>",
			    "<FONT size=$fs>", $maxDate,  "&nbsp; ",
			    $maxTime, "</FONT>",
		    "</TD>\n";

		print "<TD class=\"mmaVirtTabText\"><FONT size=$fs>", "$avg", " ", $avgUnit, "</FONT>",
		    "</TD>\n";
		print "</TR>\n";
	     }# $k
	  }# $j

      }# $i   
   }
   
   print '</TBODY> </TABLE>', "\n";
}



#
# Print a link to stdout for accessing help to a subject
# The links point to this script with CGI Param help=$subject
#
sub helpLink{
   my($size)=shift;
   my($symbol)=shift;
   my($subject)=shift;
   my($mode)=shift;
   my($str);
   
   $str="";
   $str.="<FONT size=\"$size\">" if( $size );
   $str.= "<a target=blank title=\"Hilfe\" href=\"${scriptUrl}?help=$subject\">$symbol</a>";
   $str.="</FONT>" if( $size );
   
   if( $mode ){
   	return($str);
   }else{
   	print $str;
   }	
}

sub printHelp{
   my($subject)=shift;
   my($help, $helpScaling, $helpDisplayPeriod, 
      $helpQuickNavi, $helpMMA, $helpSampleTime, $helpLatest, $helpSubject,
      $helpStatistics);
   my(@h, $i, $tmp);   
   my(@bfNames)=main::getWindSpeedNameList();
   my(@bfSpeeds)=main::getWindSpeedList();
   

   # Define help text available....
   #
   $helpScaling= <<EOF
Mit Hilfe der Skalierung ist es möglich die dargestellten Bilder
um den anzugebenden Faktor zu vergößern oder zu verkleinern. Bei einem 
Faktor größer 1 wird das Bild vergrößert dargestellt, ist der Faktor 
kleiner als 1 wird das Bild verkleinert. Der Skalierungsmodus (x, y, x+y)   
gibt an in welcher Achse das Bild skaliert werden soll. Die X-Achse ist die 
Zeitachse auf der y-Achse wird der jeweilige Wert dargestellt. Über "x"  kann also
die Zeitachse vergrößert/verkleinert dargestellt werden, über "y" die Wertachse. 
Über "x+y" werden beide Achsen vergrößert/verkleinert.
<p> Nach Eingabe des Skalierungs-Modus und des Faktors muß der Anzeigen-Knopf
gedrückt werden, um die Anzeige mit der gewählten Skalierung neu aufzubauen.
EOF
;


   $helpDisplayPeriod=<<EOF
Durch Eingabe des Anfangs- und Enddatums wird der zeitliche Bereich festgelegt,
für den Wetter-Daten dargestellt werden sollen. Eine fehlerhafte Eingabe 
wie z.B. die Eingabe eines Datums in der Zukunft, wird automatisch
korrigiert.  Die Eingabe wird durch Drücken des Anzeigen-Knopfs abgeschlossen.
Bei den meisten Web-Browsern ist stattdessen auch das Drücken der Enter-Taste auf der 
Tastatur möglich. Die Eingabe der Daten erfolgt immer in der lokalen Zeit (die Daten in der 
Datenbank sind in GMT-Zeit gespeichert). Falls die Darstellung nicht die gewünschte Periode enthält, 
sondern Abweichungen in der Zeit, so sollte überprüft werden, ob der Rechner, auf dem das Skript arbeitet
eine korrekte Zeitzonenkonfiguration hat. Die Zeitzone sollte mit dem Verwaltungswerkzeug des entsprechenden 
Systems eingestellt werden. In der Regel steht die Zeitzonenkonfiguration in der Datei /etc/localtime, einer 
Kopie einer der Dateien unter /usr/share/zoneinfo.

<p>Um direkt (z.B. als Bookmark in einem Web-Browser) direkt eine bestimmte Zeitperiode darstellen zu
können, is es möglich dem Skript verschiedene  URL-Parameter zu übergeben, die eine Darstellung 
von z.B Daten der letzten drei Tage oder der letzten 6 Stunden bewirkt.  Der Parameter 
"days=n" bewirkt z.B. , das die letzten n Tage datgestellt werden. Für n muß die gewünschte 
Zahl an Tagen eingesetzt werden. Der parameter "hours=n" bewirkt, das vom aktuellen Datum aus gerechnet 
die letzten n Stunden dargestellt werden. Hier muß für n die gewünschte Zahl an Stunden eingesetzt werden. 
Die Skript-Url zu Darstellung von z.B. der Daten der letzen 6 Stunden sieht prinzipiell wie folgt aus:

http://myserver.home.org/wetter.cgi?hours=6

wobei hier myserver.home.org der Name des Web-Servers ist, auf dem das Skript gestartet wird.
EOF
;


   $helpQuickNavi=<<EOF
Mit Hilfe der im Quicknavigations-Bereich dargestellten Links kann auf einfache 
Weise mit einem Klick ein anderer Darstellungszeitraum gewählt werden. Der
Quicknavigations-Bereich ist somit eine Alternative zur textuellen Eingabe des
Start- und Enddatums im Bereich "Darstellungszeitraum".
<p> Der Vorteil des Quicknavigationsbereichs, besteht darin, das durch die Auswahl 
nur eines Links automatisch der entsprechende Darstellungszeitraum ausgewählt und
dargestellt wird. Möglich ist auf diese Weise zum einen die Auswahl eines bestimmten Zeitraums 
für die Darstellung (z.B. 1 Tag, 1 Woche, 1 Monat) sowie die Navigation innerhalb des
gewählten Zeitraums (letzter/nächster Tag/Woche/Monat).  Die
Zeitbereiche Tag, Woche und Monat 
sind durch "T", "W", "M" abgekürzt. 

<P>Durch Anwahl eines der Links in der ganz links stehenden Spalte wird der Zeitraum
für die Darstellung ausgewählt. Durch Klick auf z.B. "1T" wird ein Tag an Daten dargestellt. 
Durch Klick auf z.B. 3M wird der Zeitbereich von 3 Monaten dargestellt jeweils ausgehend vom 
aktuellen Enddatum.

<P>Mit den Kürzeln der beiden weiteren Spalten der Form -1T, +1T, -1W, +1W, -1M, +1M usw. kann der 
dargestellte Zeitbereich (Anfang und Ende) um die angegebene Zeit verschoben werden. Wird z.B. 
+1W angeklickt, wird die nächste Woche des dargestellten Bereichs angezeigt, sprich das bisherige 
Anfangs und Enddatum wird um 1 Woche verschoben. Durch Klick auf einen negativen Wert wie z.B. 
-6M wird das Zeitfenster rückwärts um die angegebene Spanne (hier: 6 Monate) verschoben.

<P> Die Anwahl der +/- Links verändeert also immer nur das Start-End-Datum, nicht jedoch den 
angezeigten Zeitraum, der über die links stehenden T,W,M -Links bestimmt werden kann.
EOF
;

$helpSensorGraphics=<<EOF
Die Darstellung von Daten kann sowohl in graphischer als auch in tabellrischer 
Form  erfolgen.  Welche Sensoren überhaupt dargestellt werden, legt der Administrator in der
Konfiguration des Skripts fest (siehe REAME des Skripts). 
Beim Aufruf des Skripts werden die Daten der so 
konfigurierten Sensoren zunächst in graphischer Form in einer Übersicht dargestellt.
In der Übersicht werden die Graphiken aller Sensoren in verkleinerter Datstellungen 
angezeigt.

<p>Von dieser Übersicht aus, kann mit einem Klick auf die Graphik eine normal große 
Detailansicht des oder der in dieser einen Graphik dargestellten Sensoren erfolgen. 
Dies erfolgt in einem neuen Fenster. Sollen die Daten anstelle der graphischen 
Darstellung als Tabelle ausgegeben werden, so genügt ein Klick auf den unter der 
Graphik befindlichen Verweis "Als Tabelle...". In der tabellarischen Darstellung
werden die der Graphik zugrunde liegenden Daten ausgegeben. Dabei kann es sich um
reale Sensordaten (z.B. Temperatur, Feuchete) oder um Daten virtueller Sensoren
(s.u.) handeln. Zudem werden noch Daten anderer Sensoren mit ausgegeben, die zur
Berechnung der virtuellen Sensorwerte benötigt wurden. So wird z.B. in der Ausgabe für
einen Temperatur/Feuchte Sensor, in der auch die Windchilltemperatur mit
dargestellt ist, auch die Windgeschwindigkeit mit ausgegeben, da diese zur
Berechnung der Windchilltemperatur benötigt wird.

<p>Grundsätzlich können zwei verschiedene Arten von Sensoren dargestellt werden. Zum einen 
sind dies Daten der realen Sensoren, also z.B. Temperatur, Windgeschwindigkeit
oder Luftdruck. Darüber hinaus ist auch die Darstellung "virtueller" Sensoren möglich.
Als virtueller Sensor werden hier solche Daten bezeichnet, die aus den realen
Sensordaten berechnet werden, für die es aber keinen eignen realen Sensor 
zur Messung des Werts gibt. Beispiele sind die Windchilltemperatur, der Taupunkt 
und die absolute Luftfeuchte.

<p>Für virtuelle Sensoren gelten einige Sonderregeln:

<p>Unter den Sensorgraphiken wird immer eine Tabelle mit den maximalen und minimalen
sowie den Durchschnittswerten des dargestellten Sensors ausgegeben. Werden in einer
Graphik auch virtuelle Sensoren dargestellt, so werden auch für diese virtuellen
Sensoren in der Tabelle die Minima, Maxima und der
Durchschnitt der Datenwerte ausgegeben. Zur Kennzeichnung, das es sich hierbei um virtuelle
Sensoren handelt, erfolgt die Ausgabe jedoch in grauer Schrift. Das gleiche gilt
für die tabellarische Darstellung der Daten selbst. Auch hier werden die Daten
virtueller Sensoren zur Kennzeichnung in grauer Schrift dargestellt.

<p>Eine weitere Sonderregel besteht darin, das Daten virtueller Sensoren nur auf
Basis der Originaldaten oder auf Basis von Tages-, Wochen-, Montas- oder
Jahresdurchschnitten angezeigt werden können. Was nicht geht, ist die Darstellung
der Minima, Maxima für Tage, Wochen,Monate oder Jahre. Wird also zunächst der
Punkt "Nutze für die Darstellung: Mittelwerte auf Tagesbasis" und dann einer der
Punkte "Nutze für die Darstellung: Minima/Maxima" angewählt, so werden nur die
entsprechenden Daten realer Sensoren angezeigt. Virtuelle Sensoren werden hier
ausgeblendet und sind weder in der Graphik noch in der tabellarischen Datenansicht
oder der Anzeige
der Minimum/Maximum/Average-Tabelle sichtbar. Falls in diesem Fall in einer Graphik
ausschließlich virtuelle Sensoren dargestellt wurden, erfolgt keinerlei 
Graphikanzeige. Stattdessen wird eine Warnung ausgegeben, das keine Daten für 
die Darstellung zur Verfügung stehen.
EOF
;

   $helpMMA=<<EOF
Mit Hilfe der Minimum, Maximum, Average (kurz: MMA) Links können in den Graphiken
neben den eigentlichen Messwertkurven zusätzliche Kurven für das  
Minimum, Maximum und den Durchschnitt (Link "MMA") oder nur für den 
Durchschnitt (Link: "--A") der 
Sensorwerte dargestellt werden.  
Die Bestimmung der MMA-Werte kann dabei über verschiedene Zeiträume erfolgen, 
die auch verschieden vom aktuellen Darstellungszeitraum sein dürfen. Der Zeitraum für die 
MMA-Bestimmung wird über die Links "Zeige MMA aktuell/Monat/alles" bestimmt. 
"Aktuell" meint dabei das der aktuelle Darstellungszeitraum auch für die 
Bestimmung der MMA-Werte verwendet wird. "Monat" bedeutet, das die Zeit 
von einem Monat vor dem Ende des aktuellen Darstellungszeitraums bis zum 
aktuellen Endedatum für die Bestimmung der MMA-Werte verwendet wird. Hierbei handelt 
es sich normalerweise nicht um einen  Kalendermonat, sondern um den 
Zeitraum der letzten 30 Tage. "Alles" schließlich 
besagt, das alle verfügbaren Daten zur MMA-Bestimmung herangezogen werden. 
<p> Über den Link "Keine MMA-Anzeige" wird die Darstellung der MMA-Werte 
in den Graphiken abgeschaltet.
EOF
;

   $helpTableView=<<EOF
In diesem Dialog werden die Daten eines oder mehrerer Sensoren aus einer
graphischen Darstellung in textueller Form als Tabelle dargestellt. Es werden also die Daten
angezeigt, die zur Darstellung der jeweiligen Graphik verwendet werden. Die Minima/Maxima der 
jeweiligen Werte werden durch farbliche Hinterlegung dargestellt.

<p>Werte, die keine originären Sensordaten darstellen, sondern aus Sensordaten 
berechnet wurden (wie z.B. Windchill) werden in grauer Schrift dargestellt.  Auch für diese Werte von 
virtuellen Sensoren werden Minima und Maxima farblich gekennzeichnet.

<p>Ebenfalls grau werden solche Daten dargestellt, die nicht zum dargestellten Sensor gehören.
Werden also beipsielsweise  Temperatur und Feuchte Daten eines Sensors  dargestellt, und zudem 
die Windchill-Temperatur für diesen Sensor, so wird auch die Windgeschwindigkeit mit bei den Daten 
des Temperatur/Feuchte Sensors ausgegeben da sie zur Berechnung des Windchills verwendet wurde,
obwohl sie ja nicht zum dargestellten Temp/Feuchte-Sensor gehört. Um dies deutlich zu machen wird 
der Text grau gedruckt. Für diese Werte erfolgt keine Darstellung der Minima/Maxima
EOF
;   
 
   $helpSampleTime=<<EOF
Im Normalfall werden die von der Wetterstation gesammelten Daten direkt zur 
Darstellung verwendet. Dies bedeutet, daß z.B. für die Temperaturdarstellung
an einem Tag  alle an diesem Tag gesammelten Daten des Sensors zur Darstellung 
verwendet werden. Dadurch ergibt sich ein recht genaues Bild der 
Meßwertentwicklung für diesen Tag. 
<p>
Es gibt jedoch Gründe, anstelle der Originaldaten z.B. Mittelwerte über Stunden oder auch Tage
zu verwenden. Zum einen wird durch eine solche Maßnahme bei der Visualisierung von Daten über größere 
Zeiträume hinweg die Menge der Daten reduziert, d.h. die Darstellung kann schneller abgeschlossen werden.
Zum anderen kann es auch sein, daß man weniger an einer sehr detaillierten 
Wertedarstellung  interessiert ist, sondern eher an Tendenzen über längere Zeiträume
hinweg,  die auf Mittelwerten/Minima/Maxima der Originaldaten des  Sensors
basieren. 
<p>
Um die Darstellung schneller ausführen zu können, kann der Administrator des Skripts
in der Konfiguration die Variable \$doAutoBaseData (aktueller Wert: $doAutoBaseData Tage) 
auf einen Wert setzen,
der verschieden von 0 sein muß und die Zahl der Tage angibt, ab 
der in einer Darstellung anstelle der Originaldaten automatisch Mittelwerte auf Stundenbasis zur Anzeige 
verwendet werden. Auch in einem solchen Fall hat der Benutzer immer die Möglichkeit 
sich die Originaldaten anzeigen zu lassen.
<p>

Darüber hinaus kann der Benutzer auch andere Angaben für die Datenbais auswählen.
Dies erfolgt mit den Zeitbasis-Links "Mittelwerte auf Stundenbasis", 
"Mittelwerte auf Tagesbasis", 
"Monatsbasis" bzw. "Jahresbasis" möglich.   Neben der Darstellung von Mittelwerten kann
anschließend über die dann zusätzlich sichtbaren Links  "Mittelwerte/Minima/Maxima"
auch zwischen der Darstellung  von  Mittelwerten (Default), Minima oder Maxima
umgeschaltet werden.  Was bewirkt nun die Einstellung über die
Zeitbasis-Links?
 
<p>Wurde Beispielsweise "Mittelwerte auf Tagesbasis" gewählt, werden für den anzuzeigenden
Zeitraum in den Graphiken nicht mehr die Basisdaten zur Darstellung  verwendet, sondern
die Mittelwerte der dargestellten Sensoren über jeweils einen Tag.  Angenommen zur Zeit
werden die  Original-Daten einer Woche dargestellt. Für eine Woche könnte es sich hierbei
je  nach Einstellung des Meßintervalls in der Wetterstation beispielsweise um  1000
Datensätze handeln. Durch die Darstellung der Mittelwerte auf Tagesbasis  wird nun
für jeden Tag der Woche genau ein Mittelwert aller Daten dieses Tages für den 
dargestellten Sensors gebildet. Das Ergebnis,  das zur Darstellung der
Wochen-Graphik verwendet wird, besteht in
diesem Fall also aus nur 7 Mittelwertsdaten (eine Woche gleich 7 Tage),  anstelle der 1000
Einzeldaten.  Dadurch wird zum einen die Zahl der Daten für die Darstellung reduziert, zum
anderen ergibt sich aber durch die Bildung von Mittelwerten der Sensordaten insbesondere
eine  geglättete Darstellung. Ähnliches gilt für die Darstellung der Minima und Maxima auf
Tages-, Wochen-, Monats, und Jahresbasis. Hier werden keine Mittelwerte z.B. je eines
Tages, sondern das  Minimum bzw. das Maximum je eines Tages zur Darstellung herangezogen.
Für den Regensensor ist es zudem möglich anstelle von Summen
(z.B. eines Tages)  auch Mittelwerte auszugeben (s.u.). Zur Kennzeichnung 
der Darstellung von Mittelwerten/minima/Maxima (im Vergleich zur Darstellung von
Originaldaten) werden die Graphiken mit einer leicht unterschiedlichen  Hintergrundfarbe
versehen.

<p>Speziell für den Regensensor kann durch Selektion des Knopfs "Mittelwerte statt Summen" 
von der 
Darstellung der Summen eines Tags/Woche/Montats/Jahres auf die Mittelwerte/Minima/Maxima-Darstellung 
gewechselt werden (zur Anzeige muß anschließend der "Anzeigen"-Knopf gedrückt werden). In der 
Summendarstellung des Regensensors werden die Gesamtmengen an Regen für die jeweilige Periode dargestellt, 
also z.B. die Gesamtregenmenge eines Tages, einer Woche, eines Montas oder eines Jahres. 
Der Knopf "Mittelwerte statt Summen" ist nur dann sichtbar, wenn die 
Darstellung  einen Regensensor beinhaltet und zusätzlich die Darstellung  
von Tages/Wochen/Montas/Jahres-Durchschnitten angewählt wurde. Werden die original 
Daten dargestellt, wird der Knopf daher nicht angezeigt. 

<p>Bei der Darstellung von Montas- bzw. Jahresdurchschnitten wird das angegebene 
Startdatum  automatisch auf den Anfang des Montas bzw. den Anfang des Jahres gesetzt 
um eine sinvolle Darstellung zu ermöglichen. Alle Montas- bzw. Jahresmittelwerte  
werden jeweils auf den ersten Tag des jeweiligen Monats bzw. Jahres gelegt. Diese
Wahl ist zwar grundsätzlich willkürlich, aber für die Darstellung sinnvoll. Die Wirkung 
besteht darin, das z.B. in der
Regensensor Graphik der Regenmittelwert eines Monats für den ersten Tag des Montas dargestellt wird 
und nicht z.B. in der Mitte oder am Ende des Montas. Bei der Darstellung von Tages-Mittelwerten
wird die Uhrzeit des Mittelwerts für den jeweiligen Tag 
auf 00:00:00 Uhr gesetzt.
  
<p>Die Anwahl von z.B. 
"Jahres-Durchschnitte" macht natürlich auch nur dann Sinn, wenn Originaldaten 
von mehreren Jahren vorliegen, da ja in diesem Fall alle Daten eines Jahres zu genau 
einem Mittelwert zusammengefaßt werden, der dann in der Graphik dargestellt wird
Eine Graphik über den Zeitraum von 2 Jahren besteht folglich nur aus zwei Werten 
für die Darstellung! 
Durch Anwahl von "Originaldaten" wird wieder auf die Verwendung der 
Originaldaten umgeschaltet. 
<p>
Die unter den Graphiken stehenden Maximum-/Minimum-/Average-Tabellen 
enthalten für reale Sensoren <b>IMMER</b> Werte, die auf den Originaldaten basieren. 
Daher kann es durchaus
vorkommen, das hier z.B. ein Maximalwert ausgewiesen wird, der in der 
z.B. Wochen-basierten Mittelwertsgraphik 
nicht  zu entdecken ist, eben weil die Graphik in diesem Fall nur
<I>Mittelwerte</I> darstellt. Anders verhält es sich für die Angabe von Minima/Maxima 
und Mittelwerten für virtuelle Sensoren (grauer Text) wie z.B. Windchilltemperatur oder 
Taupunkt. Die Maxima, Minima udn Durchschnitte für diese Sensoren basieren immer auf den 
dargestellten Daten, da sie sich aus diesen errechnen.
EOF
;

# Temp
$h[0]=$latest_trendThresholdT->[0];
$h[1]=$latest_trendThresholdT->[1];
$h[2]=$latest_trendThresholdT->[2];

# Hum
$h[3]=$latest_trendThresholdH->[0];
$h[4]=$latest_trendThresholdH->[1];
$h[5]=$latest_trendThresholdH->[2];

# Pressure
$h[6]=$latest_trendThresholdPres->[0];
$h[7]=$latest_trendThresholdPres->[1];
$h[8]=$latest_trendThresholdPres->[2];

# Symbols:
$h[100]=$latest_trendSymbUp->[0];
$h[101]=$latest_trendSymbUp->[1];
$h[102]=$latest_trendSymbUp->[2];
$h[103]=$latest_trendSymbDown->[0];
$h[104]=$latest_trendSymbDown->[1];
$h[105]=$latest_trendSymbDown->[2];


   $helpLatest=<<EOF
In dieser Übersicht werden die aktuellen Wetterwerte dargestellt, also z.B. die aktuelle
Temperatur. Ist der Name eines dargestellten Sensors hervorgehoben (z.B. rote Schrift) und
steht eine Zahl in Klammern dahinter, so bedeutet dies, das dieser Sensor sogenannte
"Drop Outs" hatte, also Empfangsprobleme. Die Zahl in Klammern ist dabei die Anzahl der
Empfangsausfälle in den letzten $latestAlertHours Stunden. Dies ist als 
eine Hilfe für den 
Administrator der Wetterstation gedacht, um zu erkennen, das hier ein Problem besteht. 

<p>Für den Windsensor werden u.U. zwei Geschwindigkeitswerte dargestellt, von denen der erste die aktuellen Böen-Geschwindigkeit 
anzeigt und der zweite die aktuelle normale, durchschnittliche Windgeschwindigkeit.

<p>Die für den Luftdruck dargestellten Werte, die z.B. als "(1h:) -6 hPa" gekennzeichnet sind zeigen, wie sich 
der Luftdruck in der letzten Zeit (hier: "1h"= in einer Stunde; Betrag:
-6 hPa) verändert hat. Die Zeit wird von der Uhrzeit des letzten verfügbaren Datensatzes
aus gerechnet, die in der Überschrift "Letzte Werte vom ..." dargestellt wird. Wird ein positiver
Wert angezeigt, bedeutet dies, das der Luftdruck in der letzten Stunde 
um den angezeigten Differenzbetrag auf den als aktuell angezeigten Wert gestiegen ist. 
Ist der Wert negativ, bedeutet dies, das der Luftdruck 
in der letzten Stunde um den angezeigten Differenzbetrag auf den als aktuell angezeigten Wert gefallen ist. 
Die oben als Beispiel angegebene Anzeige "(1h:) -6 hPa" bedeutet also, das der Luftdruck in der letzten Stunde um 6 hPa 
gefallen ist. Andersherum gesagt: Vor einer Stunde war der Luftdruck um 6 hPa höher als der jetzt als 
aktuell angezeigte Wert.  

<p>Wird hinter einem Meßwert ein Pfeil (&uarr;/&darr;) dargestellt, so
bedeutet dies, das der Wert einen Trend nach oben bzw. unten zeigt. Verschieden starke Trends werden 
durch unterschiedliche Symbole gekennzeichnet in Abhängigkeit davon, wie stark der Wert eines Sensors 
sich zuletzt geändert hat. Ausschlaggebend für die Auswahl des Trend-Symbols ist der Unterschied 
vom letzten Wert des Sensors zum aktuellen Wert. Diese Differenz wird
nach ihrer Größe (also dem Betrag der Differenz, ohne Vorzeichen) in Bereiche eingeteilt für die 
verschiedenfarbige Symbole dargestellt werden. Die unten verwendete Schreibweise, z.B. 
$h[0]&deg;C &le; dt &lt; $h[1]&deg;C: $h[100]/$h[103] für Temperatursensoren bedeutet,
das falls die Temperaturdifferenz (dt) größer oder 
gleich dem linken Wert ist und zugleich kleiner als der Rechte, eines der ganz rechts stehenden 
Pfeil-Symbole verwendet wird je nachdem ob der Wert des Sensors gestiegen oder gefallen ist. 
Vereinfacht gesagt: Liegt der Temperaturunterschied zwischen $h[0]&deg;C und $h[1]&deg;C ($h[1] exklusiv) wird eines der Symbole $h[100] bzw. $h[103] verwendet.
Das Symbol 
"&le;" steht also für "kleiner gleich", das Symbol "&lt;" für "kleiner" und "&ge;" für größer gleich.  

<p>Für Temperatursensoren erfolgt die Auswahl des Trendsymbols in Abhängigkeit von der 
Temperaturdifferenz (dt) wie folgt: 
$h[0]&deg;C &le; dt &lt; $h[1]&deg;C: $h[100]/$h[103], &nbsp;
$h[1]&deg;C &le; dt &lt; $h[2]&deg;C: $h[101]/$h[104], &nbsp;
dt &ge; $h[2]&deg;C: $h[102]/$h[105].

<p>Für Feuchtesensoren erfolgt die Auswahl des Trendsymbols in Abhängigkeit von der 
Feuchtedifferenz (dh) wie folgt:
$h[3]% &le; dh &lt; $h[4]%: $h[100]/$h[103], &nbsp;
$h[4]% &le; dh &lt; $h[5]%: $h[101]/$h[104], &nbsp;
dh &ge; $h[5]%: $h[102]/$h[105].

<p>Für den Luftdrucksensor erfolgt die Auswahl des Trendsymbols in Abhängigkeit von der 
Druckdifferenz (dp) wie folgt:
$h[6]hPa &le; dp &lt; $h[7]hPa: $h[100]/$h[103], &nbsp;
$h[7]hPa &le; dp &lt; $h[8]hPa: $h[101]/$h[104], &nbsp;
dp &ge; $h[8]hPa: $h[102]/$h[105].

<p>Für die Anzeige des Regensensors bedeuten die konkreten Angaben der Regenmenge,
wieviel Regen insgesamt in der angegebenen 
Zeitspanne gefallen ist. Eine  Angabe von z.B. "(12h:) 3 mm bedeutet, daß in den 
letzten 12 Stunden insgesamt 3 mm Regen gefallen sind. Die dargestellte
Gesamtregenmenge für den heutigen Tag wird ab Mitternacht des aktuellen
Tags gemessen.

<p>Je nach der Einstellung des Datenintervalls der Wetterstation, kann es
sein, das für die Ermittlung der Trendwerte, bzw für die Darstellung konkreter Werte von 
z.B. vor 1h, 3h oder 12h kein Wert in der Datenbank gefunden wird, der z.B. genau 1, 3 
oder 12 Stunden zurück liegt. In diesem Fall wird der Datensatz 
verwendet, der dem gesuchten Zeitpunkt am nächsten liegt. Wird kein zeitlich genau 
passender Wert gefunden und keiner, der zeitlich in der Nähe liegt, so wird kein 
Trend-Wert ausgegeben.

EOF
;

$helpStatistics=<<EOF
In der statistischen Übersicht werden Daten des ausgewählten Zeitraums in einzelnen vom 
Benutzer wählbaren Zeitabschnitten (Tage, Wochen, Monate, Jahre) dargestellt. Die ausgegebenen 
Daten stellen eine Statistik für den jeweils bezeichneten Zeitabschnitt dar. Für jeden 
Abschnitt werden die Minima, Maxima und Durchschnittswerte des dargestellten Sensors
angegeben. Darüber hinaus werden weitere sensorspezifische Daten dargestellt, wie z.B. die 
Zahl der Regentage. Die Ergebnistabelle enthält in den Zeilen die genannten Daten für 
jeweils einen Zeitabschnitt (z.B. eine zeile je Monat),  die letzte Zeile der dargestellten 
Tabelle enthält die oben beschriebenen Daten nocheinmal gesondert
für den gesamten gewählten Zeitraum wie z.B. 01.01.2005-31.12.2005 als einen Abschnitt.  

<p>Ganz links in jeder Zeile steht das Datum des 
jeweiligen Zeitabschnitts. Die weiteren 
Spalten enthalten die statistischen Daten der jeweiligen Sensoren. 
Bei dem durch das Datum beschriebenen Zeitabschnitt 
handelt es sich um Tage, Kalenderwochen (Woche beginnt Montags und endet Sonntags), 
Kalendermonate (Monat beginnt immer am 1.)  oder Kalenderjahre. 

<p>Unter der Angabe des Datums in der ganz
linken Spalte sowie in jeder Spalte eines Sensors befindet sich das &iota;&Iota;&iota;-Zeichen. 
Durch einen Klick auf diese Verknüpfung 
werden die Sensordaten des entsprechenden Zeitabschnitts in einem neuen Fenster graphisch dargestellt.
Abhängig davon ob die Verknüpfung in der ganz links stehenden Datumsspalte oder in einer der Spalten mit
Sensorenstatistiken gewählt wurde, öffnet sich ein Fenster mit Grpahiken aller bzw. nur des gewählten Sensors 
für den jeweiligen Zeitabschnitt. Auf diese Weise kann die Grundlage für die statistischen Werte leicht
eingesehen werden.

<p>Unter der Verknüpfung für die Sensorgrafik stehen weitere Verknüpfungen, 
die dazu dienen, den in dieser Zeile dargestellten Zeitabschnitt genauer auflösen zu können. 
Werden in der aktuellen Zeile beispielsweise statistische Daten des Zeitraums eines Montas 
dargestellt, so stehen darunter Verknüfungen, um den gleichen Zeitraum entweder in Abschnitten 
von Wochen oder Tagen darzustellen. Wird dann beispielsweise die Wochen-Verknüpfung gewählt 
so findet in der neuen Darstellung wiederum eine Verknüpfung für eine noch feinere Auflösung 
in Tagen (die nächst feinere Auflösung). 

<p>Die Verknüpfungen werden stets in zwei Varianten dargestellt. Die Form [m]&raquo;, [w]&raquo;,
[d]&raquo;  dient zur Anzeige des Zeitraums in Abschnitten von Monaten, Wochen oder Tagen 
jeweils in einem neuen Fenster. In der Form [m], [w], [d] werden die Daten im aktuellen Fenster 
dargestellt.  

<p>Die In der Tabelle verwendeten Abkürzungen sind: 
<ul>
<li>Ft: Frosttage. Tage an denen die Temperatur mindestens einmal kleiner als 0&deg;C war.
<li>Et: Eistage. Tage an denen die Temperatur ganztägig unter 0 &deg;C war.
<li>Wt: Warme Tage. Tage an denen die Temperatur mindestens einmal größer oder gleich  20&deg;C war.
<li>Ht: Heiße Tage. Tage an denen die Temperatur mindestens einmal größer oder gleich 30&deg;C war.
<li>Rt: Regentage. Zahl der Tage an denen es geregnet hat.
<li>Sum: Menge des Niederschlags in mm.
<li>S: Maximale und mittlere Windgeschwindigkeit
<li>B: Maximale und mittlere Böen-Windgeschwindigkeit
<li>Hwr: Die Hauptwindrichtung.
<li>Bwr: Die Hauptwindrichtung von Windböen
<li>&iota;&Iota;&iota;: Neues Fenster mit graphischer Datendarstellung
des jeweiligen Zeitabschnitts und Sensors.
</ul>
<p> Weitere Informationen sind als Tooltip abrufbar, indem man mit der Maus über den entsprechenden Wert 
fährt:
<ul>
<li>Für die Minimum/Maximum-Werte wird auf diese Weise das Datum des Minimums/Maximums sichtbar. 
<li>Für Frosttage, Eistage, warme Tage und heiße Tage kann das Datum des ersten und letzten Tags der 
entsprechenden Zeitperiode angezeigt werden.
<li>Für Regentage wird sowohl das Datum des ersten und letzten Regentags auf diese Weise sichtbar, als auch eine
Aufstellung über die Verteilung der Zahl der Regentage nach Regenmenge/Tag verfügbar gemacht.
<li>Wird mit der Maus über den Wert der Hauptwindrichtung gefahren, erhält man eine Aufschlüsselung, in 
der für die entsprechende Zeitperiode angegeben wird an wievielen Tagen welche Windstärke geherrscht hat. 
Die möglichen Windstärke-Stufen in Beaufort(Bft) sind:
<ul>
EOF
;

for($i=0; $i<=$#bfNames; $i++){
   if( $i == $#bfNames ){
      $helpStatistics .= "<li>$i: $bfNames[$i] ( >= $bfSpeeds[$i-1] Km/h)";
   }elsif( $i ){
      $helpStatistics .= "<li>$i: $bfNames[$i] ( $bfSpeeds[$i-1] - &lt;$bfSpeeds[$i] Km/h)";
   }else{
      $helpStatistics .= "<li>$i: $bfNames[$i] (0 - &lt;$bfSpeeds[$i] Km/h)";   
   }   
}
$helpStatistics.="</ul>Siehe auch die <a href=\"http://de.wikipedia.org/wiki/Beaufortskala\">Beaufort-Skala</a>." .
                 "bei <a href=\"http://www.wikipedia.de\">Wikipedia</a>.</ul>\n";

   # 
   # Select which help was requested
   #
   $moreHelp="";
   if( $subject=~/scaling/i ){
   	$help=$helpScaling; 
	$helpSubject="Skalierung";
   }elsif( $subject=~/displayPeriod/i ){
   	$help=$helpDisplayPeriod; 
	$helpSubject="Auswahl des Darstellungszeitraums";
   
   }elsif( $subject=~/quicknavi/i ){
   	$help=$helpQuickNavi;
	$helpSubject="Quicknavigation mit Links";

   }elsif( $subject=~/sensorGraphics/i ){
   	if( $subject =~/Wind/ ){
	   $moreHelp='Für den Windsensor sind verschiedene Darstellungen möglich. Zum einen kann '.
	          'die Windgeschwindigkeit über die Zeit dargestellt werden. Eine zweite Darstellungsform '.
		  'ermöglicht einen Überblick über die Winstärke in Korrelation zur Windrichtung. '. 
		  'In der dritten Darstellungsform schließlich kann abgelesen werden, wie sich die Windrichtung '.
		  'in der Zeit verändert hat. <p>'.
	          'In der Beschreibung der <a href="http://de.wikipedia.org/wiki/Beaufortskala">Beaufort</a>' .
	          "-Skala k&ouml;nnen Sie die Umrechnung der Windst&auml;rken in verschiedene Einheiten sowie" .
		  " die Auspr&auml;gung der sichtbaren Merkmale nachlesen.<hr>";
	   $help=$helpSensorGraphics; 
	   $helpSubject="Die Darstellung der Sensordaten des Windsensors";
	}elsif( $subject=~/Rain/ ){
	   $moreHelp="Die Originaldaten des Regensensors stellen die gefallene Menge an Niederschlag " .
	             "je Meßperiode dar. Die Meßperiode (z.B. 10 Minuten) ist jedoch nicht fest vorgegeben, sondern kann vom Verwalter ".
		     "der Station gesetzt werden. Zudem wird für den Regensensor nur dann ein Meßwert erfaßt, " .
		     "wenn wirklich Regen gefallen ist. Zeiträume ohne Regen werden nicht in der Datenbank " .
		     "gespeichert, so daß man in der tabellarischen Sicht nur Einträge findet, in denen es ".
		     "geregnet hat, wobei zwischen zwei Zeilen der Tabelle u.U. ein großer (trockener) Zeitraum liegen kann. " . 
		     "Die Länge der Meßperiode kann in der tabellarischen Ausgabe der Daten " .
		     "anhand der Datumseinträge aufeinanderfolgender Meßwerte (mit Regen) abgelesen werden. In den Graphiken ist dies jedoch nicht genau erkennbar. ". 
		     "Die Darstellung der <i>Originaldaten</i> für den Regensensor ".
		     "kann also nur dazu dienen möglichst genau zu sehen wann Regen gefallen ist, nicht jedoch " .
		     "dazu zu erfahren, wieviel Regen in jeweils einer Stunde gefallen ist. <p>".
		     "Um für den Regensensor aussagekräftige Resultate zu erlangen, sollte man daher die Anzeige ".
		     "auf <i>Stundenbasis</i> (Summe auf Stundenbasis) umschalten. Dadurch kann man in der Graphik genau ablesen wieviel Niederschlag je Stunde gefallen ist.
		     <p> Bei der Angabe des Minimalen-, Maximalen- und des Durchschnittwerts in der Tabelle unter der Graphik
		     wird für den Maximalen- (Max) und den Durchschnittswert (Avg) die Regenmenge immer bezogen 
		     auf eine Stunde (nicht auf eine Meßperiode) angegeben.<hr>";
	   $help=$helpSensorGraphics; 
	   $helpSubject="Die Darstellung der Sensordaten des Regensensors";
	     
	}elsif( $subject=~/LD/ ){
	   $moreHelp="Die Anzeige der Sonnenscheindauer erfolgt immer in Stunden ".
	             "Daher entspricht eine Anzeige von 0.5 h Sonne einer halben Stunde Sonnenschein" .
	             "Die Anzeige 0.1 h entspricht 6 Minuten Sonne." .
	             " " .
	             "<hr>";
	   $help=$helpSensorGraphics; 
	   $helpSubject="Die Darstellung der Sonnenscheindauer";
	}else{
	   $help=$helpSensorGraphics; 
	   $helpSubject="Die Darstellung der Sensordaten,  eine grundlegende Beschreibung";
	}

   }elsif( $subject=~/mma/i ){
   	$help=$helpMMA; 
	$helpSubject="Darstellung von Maximum, Minimum, Average-Werten";

   }elsif( $subject=~/tableView/i ){
   	$help=$helpTableView; 
	$helpSubject="Tabellarische Datenansicht";

   }elsif( $subject=~/sampleTime/i ){
   	$help=$helpSampleTime; 
	$helpSubject="Auswahl der Basisdaten";
   }elsif( $subject=~/latestValue/i ){
   	$help=$helpLatest; 
	$helpSubject="Anzeige der aktuellen Werte";
   }elsif( $subject=~/statisticDisplay/i ){
   	$help=$helpStatistics; 
	$helpSubject="Anzeige von statistischen Daten:";
   }

   
   # Convert some special chars to HTML encoding
   # Note: This cahrs are in latin1 as are the umlauts in the text above
   # So even if you cannot read the umlauts above because you use UTF8 
   # these umlauts should be converted here to correct HTML umlauts: 
   #
   $help=~s/ü/\&uuml;/g;
   $help=~s/ö/\&ouml;/g;
   $help=~s/ä/\&auml;/g;
   $help=~s/Ü/\&Uuml;/g;
   $help=~s/Ö/\&Ouml;/g;
   $help=~s/Ä/\&Auml;/g;
   $help=~s/ß/\&szlig;/g;

   $moreHelp=~s/ü/\&uuml;/g;
   $moreHelp=~s/ö/\&ouml;/g;
   $moreHelp=~s/ä/\&auml;/g;
   $moreHelp=~s/Ü/\&Uuml;/g;
   $moreHelp=~s/Ö/\&Ouml;/g;
   $moreHelp=~s/Ä/\&Auml;/g;
   $moreHelp=~s/ß/\&szlig;/g;

   print h3("Hilfe zu...<br>$helpSubject");
   print '<FONT class="help">', $moreHelp, $help, '</FONT>';
   
   
   print end_html, "\n";
   exit 0;
}


#
# Return latest date and time in form of Date:Calc:Today_and_Now
#
sub getLastTimeDateSet{
   my($dbh)=shift;
   my($sensorData)=shift;
   my($sql, $result, $stationIdSql);
   my($refSensor, $id, $table, @timeDateN, @timeDate, $tmp1, $tmp2);
   
   # Run through all defined sensors (at least all types the first sensor of this type)
   # To find the latest date.
   $refSensor=$sensorData->getFirstSensor("all");
   while( defined(%{$refSensor}) ){
 	if( ! ${$refSensor}{"doPlot"} || $refSensor->{"ignoreInGetLastTimeDateSet"} != 0 ){
	   # Get next 
           $refSensor=$sensorData->getNextSensor("all");
	   next;
	}
        $stationIdSql=$refSensor->{"stationIdSql"};
	$id=$refSensor->{"sensIds"}->[0];
	$table=$refSensor->{"tableName"};
	$sql="SELECT datetime FROM $table WHERE $stationIdSql AND " .
	     "sensid=$id ORDER by datetime desc LIMIT 1";
        #print "$sql<hr>\n";
	$result=$dbh->selectrow_hashref($sql);
       ($tmp1,$tmp2)=split(/\s/, $result->{"datetime"});
	@timeDate=(split(/-/o, $tmp1), split(/:/o, $tmp2));
	if( $#timeDateN >0 ){
	   if( Date_to_Time(@timeDateN) < Date_to_Time(@timeDate) ){
		@timeDateN=@timeDate;
	   }
	}else{
	   @timeDateN=@timeDate;
	}
        # Get next 
        $refSensor=$sensorData->getNextSensor("all");
   }	
   return( @timeDateN );
}


#
# Return first (most early)  date and time in form of Date:Calc:Today_and_Now
#
sub getFirstTimeDateSet{
   my($dbh)=shift;
   my($sensorData)=shift;
   my($sql, $result, $stationIdSql);
   my($refSensor, $id, $table, @timeDateN, @timeDate, $tmp1, $tmp2, $found);
   
   # Run through all defined sensors (at least all types the first sensor of this type)
   # To find the latest date.
   $found=0;
   $refSensor=$sensorData->getFirstSensor("all");
   while( defined(%{$refSensor}) ){
 	next if( ! ${$refSensor}{"doPlot"} );
        $stationIdSql=$refSensor->{"stationIdSql"};
	$id=$refSensor->{"sensIds"}->[0];
	$table=$refSensor->{"tableName"};
	$sql="SELECT datetime FROM $table WHERE $stationIdSql AND " .
	     "sensid=$id ORDER by datetime asc LIMIT 1";
	$result=$dbh->selectrow_hashref($sql);
        if( !defined($result) ){
	    $refSensor=$sensorData->getNextSensor("all");
	    next;
        }
	$found=1 if( $result > 0 );
	
       ($tmp1,$tmp2)=split(/\s/, $result->{"datetime"});
	@timeDate=(split(/-/o, $tmp1), split(/:/o, $tmp2));
	if( $#timeDateN >0 ){
	   if( Date_to_Time(@timeDateN) > Date_to_Time(@timeDate) ){
		@timeDateN=@timeDate;
	   }
	}else{
	   @timeDateN=@timeDate;
	}
        # Get next 
        $refSensor=$sensorData->getNextSensor("all");
   }
   if( $found==0 ){
      warn "getFirstTimeDateSet(): Was unable to find any SQL data of sensors for stationIds $stationIdSql .<br>\n";
   }	
   return( @timeDateN );
}



#
# Calculate and write the complete latestdata section into the web-page
#
sub showLatestDataPanel{
   my($plots, $sensorData, $pageTab, $refNow)=@_; 
   my(%latestSens, $tmp1, $tmp2, $tmpStr, $latestTab, @tmp, $tmp, $cfgId, $i, $j, $k);
   my($year,$month,$day, $hour,$min,$sec, $Dd,$Dh,$Dm,$Ds, $help);

   #
   # Now define the data for the latest sensor values to be calculated and printed
   #
   if( $plots =~ /TH/ ){
      if( defined($latest_th) ){
	 $tmp=$latest_th; 	# A ref to a list of sensorId.staionId pairs
	 $cfgId=$tmp;
      }elsif( defined($latestSensId{"TH"}) ){
	 $tmp=[$latestSensId{"TH"}];
	 $cfgId=["10"];
      }else{
	 $tmp=["1"];
	 $cfgId=["10"];
      }
      $latestSens{"temp"}->{"configIds"}=$cfgId;
      $latestSens{"temp"}->{"sensorids"}=$latest_th;
      $latestSens{"temp"}->{"sensornames"}=["Aussen","Innen"];
      $latestSens{"temp"}->{"stationId"}=$main::defaultStationId;
      # Names to be printed as latest values
      # These value either have to be a particular datase column name or in 
      # case a converter was specified it may be any nonempty name, its not used then
      # except for the purpose that the converter will be called and has to do its job
      # Note: This is true for "dbcols" NOT for "getDbcols" below!
      # dbcols and getdbcols should except for a beginning datetime always
      # be given in the same sequence allthough dbcols may have more entries 
      # You may *not* say dbcols=T,H and getdbcols=H,T
      $latestSens{"temp"}->{"dbcols"}=["T","H", "absHum", "dewpoint"];	
      # Functions that convert a database value into something else
      $latestSens{"temp"}->{"converter"}=[0, 0, \&absHumidity, \&dewPoint];
      # cols to get from the database. Are inserted into
      # $latestSens{"sensorval"}->{sensid}->... Hash with the names of the colums as key. 
      # See printLatestData
      $latestSens{"temp"}->{"getDbcols"}=["T","H"];
      $latestSens{"temp"}->{"sensorunits"}=["&deg;C", "%rel Feuchte", "g/m<sup>3</sup>", "&deg;C"];
      $latestSens{"temp"}->{"valuename"}=["","", "abs", "Taupunkt"];
      $latestSens{"temp"}->{"table"}="th_sensors";
      $latestSens{"temp"}->{"type"}="TH";
      $latestSens{"temp"}->{"trendData"}=$latest_trendTemp;
      # If you want to display several trendData values for this sensor and not only 
      # an arrow sign for the trend itself set the variable to 1 here:
      $latestSens{"temp"}->{"trendDataDisplay"}=0;
      # If defined enables printing a tendency sign (up,down arrow) for sensors of this type
      # Besides this setting you also need to define that older values for this sensor
      # should be fetched. This is done in the head of the script see: $latest_trend*
      $latestSens{"temp"}->{"trendThreshold"}->{"T"}=$latest_trendThresholdT;
      $latestSens{"temp"}->{"trendThreshold"}->{"H"}=$latest_trendThresholdH;
      # Trendsymbol settings. See comments at the beginning of this script
      $latestSens{"temp"}->{"trendSymbDown"}=$latest_trendSymbDown;
      $latestSens{"temp"}->{"trendSymbUp"}=$latest_trendSymbUp;
      $latestSens{"temp"}->{"trendSymbMode"}=$latest_trendSymbMode;
      $latestSens{"temp"}->{"trendSymbTextCol"}=$latest_trendSymbTextCol;
      $latestSens{"temp"}->{"trendSymbTextSize"}=$latest_trendSymbTextSize;   
   }

   if( $plots =~ /RA/ ){
      # In the new sensid scheme where each sensor type starts with a sensid 
      # of 1.  Since then we have a configId that refers to a definition of a certain
      # sensor defined by addSensor()
      # 
      if( defined($latest_ra) ){
	 $tmp=$latest_ra; 	# A ref to a list of sensorId.staionId pairs
	 $cfgId=$tmp;
      }elsif( defined($latestSensId{"RA"}) ){
	 $tmp=[$latestSensId{"RA"}];
	 $cfgId=["40"];
      }else{
	 $tmp=["1"];
	 $cfgId=["40"];
      }

      $latestSens{"rain"}->{"configIds"}=$cfgId;
      $latestSens{"rain"}->{"sensorids"}=$tmp;
      $latestSens{"rain"}->{"stationId"}=$main::defaultStationId;
      $latestSens{"rain"}->{"sensornames"}=["Regen"];
      $latestSens{"rain"}->{"table"}="rain";
      # Special case for rain sensor; SUM($dbcolName) is caculated for this one col
      $latestSens{"rain"}->{"dbcolName"}="diff";
      $latestSens{"rain"}->{"dbcols"}=["-"];
      $latestSens{"rain"}->{"getDbcols"}=$latestSens{"rain"}->{"dbcols"}; 
      $latestSens{"rain"}->{"sensorunits"}=["mm"];
      $latestSens{"rain"}->{"unitfactor"}={"diff"=>"0.001"};
      $latestSens{"rain"}->{"sensorcolor"}=["#0000ff"];
      # This specifies the date from when a diff up to now will be calculated
      # Today means: take the difference from the first value of today up to
      # now to calculate difference
      $latestSens{"rain"}->{"datediff"}="$today";
      $latestSens{"rain"}->{"valuename"}=["(Ges. heute)"];
      $latestSens{"rain"}->{"type"}="RA";
      $latestSens{"rain"}->{"trendData"}=$latest_trendRain;
      $latestSens{"rain"}->{"trendDataUnits"}->{"-"}="mm";
      $latestSens{"rain"}->{"trendDataDisplay"}=1;

   }

   if( $plots =~ /WI/ ){
      if( defined($latest_wi) ){
	 $tmp=$latest_wi; 	# A ref to a list of sensorId.staionId pairs
	 $cfgId=$tmp;
      }elsif( defined($latestSensId{"WI"}) ){
	 $tmp=[$latestSensId{"WI"}];
	 $cfgId=["30"];
      }else{
	 $tmp=["1"];
	 $cfgId=["30"];
      }
      $latestSens{"wind"}->{"configIds"}=$cfgId;
      $latestSens{"wind"}->{"sensorids"}=$tmp;
      $latestSens{"wind"}->{"stationId"}=$main::defaultStationId;
      $latestSens{"wind"}->{"sensornames"}=["Wind"];
      $latestSens{"wind"}->{"table"}="wind";
      if( ! $main::latestWindGust ) {
	  $latestSens{"wind"}->{"dbcols"}=["speed", "angle", "range", "windchill"];
	  $latestSens{"wind"}->{"getDbcols"}= ["speed", "angle", "range"];
	  $latestSens{"wind"}->{"sensorunits"}=["Km/h", "", "", "&deg;C"];
	  $latestSens{"wind"}->{"valuename"}=["", "aus", "Varianz +/-", "Windchill"];
	  $latestSens{"wind"}->{"converter"}=[\&windSpeed, \&windDir2, \&windVar, \&windChill];
      }else{
	  $latestSens{"wind"}->{"dbcols"}=["gustspeed", "speed", "angle", "windchill"];
	  $latestSens{"wind"}->{"getDbcols"}= ["gustspeed", "speed", "angle" ];
	  $latestSens{"wind"}->{"sensorunits"}=["Km/h", "Km/h", "", "&deg;C"];
	  $latestSens{"wind"}->{"valuename"}=["", "", "aus", "Windchill"];
	  $latestSens{"wind"}->{"converter"}=[\&windSpeed, \&windSpeed, \&windDir2,\&windChill];
      }
      $latestSens{"wind"}->{"type"}="WI";
      
      $latestSens{"wind"}->{"windSpeedType"}=$main::latestWindSpeedType;
      if( $main::latestWindSpeedType == 1 ){
            $latestSens{"wind"}->{"unitfactor"}->{"speed"}=$main::kmhToKnots;
	    $latestSens{"wind"}->{"sensorunits"}->[0]="Kn";
      }
      $latestSens{"wind"}->{"latestWindRose"}=$main::latestWindRose;
      $latestSens{"wind"}->{"latestWindRoseUrl"}=$main::latestWindRoseUrl;
   }


   if( $plots =~ /PR/ ){
      #$latestSens{"pressure"}->{"configIds"}=[20];
      if( defined($latest_pr) ){
	 $tmp=$latest_pr; 	# A ref to a list of sensorId.staionId pairs
	 $cfgId=$tmp;
      }elsif( defined($latestSensId{"PR"}) ){
	 $tmp=[$latestSensId{"PR"}];
	 $cfgId=["20"];
      }else{
	 $tmp=["1"];
	 $cfgId=["20"];
      }
      $latestSens{"pressure"}->{"configIds"}=$cgfId;
      $latestSens{"pressure"}->{"sensorids"}=$tmp;
      $latestSens{"pressure"}->{"stationId"}=$main::defaultStationId;
      $latestSens{"pressure"}->{"sensornames"}=["Luftdruck"];
      $latestSens{"pressure"}->{"table"}="pressure";
      $latestSens{"pressure"}->{"dbcols"}=["P"];
      $latestSens{"pressure"}->{"getDbcols"}=$latestSens{"pressure"}->{"dbcols"};    
      $latestSens{"pressure"}->{"sensorunits"}=["hPa"];
      $latestSens{"pressure"}->{"valuename"}=[""];
      $latestSens{"pressure"}->{"type"}="PR";
      $latestSens{"pressure"}->{"trendData"}=$latest_trendPressure;
      $latestSens{"pressure"}->{"trendDataUnits"}->{"P"}="hPa";
      $latestSens{"pressure"}->{"trendDataDisplay"}=1;
      $latestSens{"pressure"}->{"trendThreshold"}->{"P"}=$latest_trendThresholdPres;
      # Trendsymbol settings. See comments at the beginning of this script
      $latestSens{"pressure"}->{"trendSymbDown"}=$latest_trendSymbDown;
      $latestSens{"pressure"}->{"trendSymbUp"}=$latest_trendSymbUp;
      $latestSens{"pressure"}->{"trendSymbMode"}=$latest_trendSymbMode;
      $latestSens{"pressure"}->{"trendSymbTextCol"}=$latest_trendSymbTextCol;
      $latestSens{"pressure"}->{"trendSymbTextSize"}=$latest_trendSymbTextSize;   
   }

   if( $plots =~ /LI/ ){
      if( defined($latest_li) ){
	 $tmp=$latest_li; 	# A ref to a list of sensorId.staionId pairs
	 $cfgId=$tmp;
      }elsif( defined($latestSensId{"LI"}) ){
	 $tmp=[$latestSensId{"LI"}];
	 $cfgId=["50"];
      }else{
	 $tmp=["1"];
	 $cfgId=["50"];
      }
      $latestSens{"light"}->{"stationId"}=$main::defaultStationId;
      $latestSens{"light"}->{"configIds"}=$cfgId;
      $latestSens{"light"}->{"sensorids"}=$tmp;
      $latestSens{"light"}->{"sensornames"}=["Helligkeit"];
      $latestSens{"light"}->{"table"}="light";
      $latestSens{"light"}->{"dbcols"}=["lux"];
      $latestSens{"light"}->{"getDbcols"}=["lux", "factor"];
      $latestSens{"light"}->{"sensorunits"}=["Lux"];
      $latestSens{"light"}->{"valuename"}=[""];
      $latestSens{"light"}->{"factor"}=[9];
      $latestSens{"light"}->{"type"}="LI";
   }
   
   if( $plots =~ /LD/ ){
      if( defined($latest_ld) ){
	 $tmp=$latest_ld; 	# A ref to a list of sensorId.staionId pairs
	 $cfgId=$tmp;
      }elsif( defined($latestSensId{"LD"}) ){
	 $tmp=[$latestSensId{"LD"}];
	 $cfgId=["60"];
      }else{
	 $tmp=["1"];
	 $cfgId=["60"];
      }

      # In the new sensid scheme where each sensor type starts with a sensid 
      # of 1.  Since then we have a configId that refers to a definition of a certain
      # sensor defined by addSensor()
      # 
      $latestSens{"sundur"}->{"configIds"}=$cfgId;
      $latestSens{"sundur"}->{"stationId"}=$tmp;
      $latestSens{"sundur"}->{"sensornames"}=["Sonnenscheindauer"];
      $latestSens{"sundur"}->{"table"}="light";
      # Special case for rain sensor; SUM($dbcolName) is caculated for this one col
      $latestSens{"sundur"}->{"dbcolName"}="sundur";
      $latestSens{"sundur"}->{"dbcols"}=["-"];
      $latestSens{"sundur"}->{"getDbcols"}=$latestSens{"rain"}->{"dbcols"}; 
      $latestSens{"sundur"}->{"sensorunits"}=["h"];
      $latestSens{"sundur"}->{"unitfactor"}={"sundur"=>"0.0166667"};
      $latestSens{"sundur"}->{"sensorcolor"}=["#ff7000"];
      # This specifies the date from when a diff up to now will be calculated
      # Today means: take the difference from the first value of today up to
      # now to calculate difference
      $latestSens{"sundur"}->{"datediff"}="$today";
      $latestSens{"sundur"}->{"valuename"}=["(heute)"];
      $latestSens{"sundur"}->{"type"}="LD";
      $latestSens{"sundur"}->{"trendDataDisplay"}=0;
   }


   if( $plots =~ /LR/ ){	# Sunlight radiation delivered by davis vantage pro 2
      if( defined($latest_lr) ){
	 $tmp=$latest_lr; 	# A ref to a list of sensorId.staionId pairs
	 $cfgId=$tmp;
      }elsif( defined($latestSensId{"LR"}) ){
	 $tmp=[$latestSensId{"LR"}];
	 $cfgId=["70"];
      }else{
	 $tmp=["1"];
	 $cfgId=["70"];
      }
      $latestSens{"radiation"}->{"stationId"}=$main::defaultStationId;
      $latestSens{"radiation"}->{"configIds"}=$cfgId;
      $latestSens{"radiation"}->{"sensorids"}=$tmp;
      $latestSens{"radiation"}->{"sensornames"}=["Sonnenstrahlung"];
      $latestSens{"radiation"}->{"table"}="light";
      $latestSens{"radiation"}->{"dbcols"}=["radiation"];
      $latestSens{"radiation"}->{"getDbcols"}=["radiation"];
      $latestSens{"radiation"}->{"sensorunits"}=["W/m*m"];
      $latestSens{"radiation"}->{"valuename"}=[""];
      $latestSens{"radiation"}->{"type"}="LR";
   }

   if( $plots =~ /LU/ ){	# UVindex deliverred by eg DAVIS Vanmte Pro 2
      if( defined($latest_lu) ){
	 $tmp=$latest_lu; 	# A ref to a list of sensorId.staionId pairs
	 $cfgId=$tmp;
      }elsif( defined($latestSensId{"LU"}) ){
	 $tmp=[$latestSensId{"LU"}];
	 $cfgId=["80"];
      }else{
	 $tmp=["1"];
	 $cfgId=["80"];
      }
      $latestSens{"uvindex"}->{"stationId"}=$main::defaultStationId;
      $latestSens{"uvindex"}->{"configIds"}=$cfgId;
      $latestSens{"uvindex"}->{"sensorids"}=$tmp;
      $latestSens{"uvindex"}->{"sensornames"}=["UV-Strahlung"];
      $latestSens{"uvindex"}->{"table"}="light";
      $latestSens{"uvindex"}->{"dbcols"}=["uvindex"];
      $latestSens{"uvindex"}->{"getDbcols"}=["uvindex"];
      $latestSens{"uvindex"}->{"sensorunits"}=["Index"];
      $latestSens{"uvindex"}->{"valuename"}=[""];
      $latestSens{"uvindex"}->{"type"}="LU";
   }

   
   getLatestValues($dbh, $sensorData, \%latestSens, @{$refNow});

   #
   # print out an overview of current values
   #
   print "<h3>$position</h3>";
   print "<p>$news</p>";
   $help=helpLink(-1, "?", "latestValue", 1);	

   $tmp1="$refNow->[0]-$refNow->[1]-$refNow->[2]";
   $tmp2="$refNow->[3]:$refNow->[4]:$refNow->[5]";
   
   ($tmp1,$tmp2)=timeConvert($tmp1, $tmp2, "LOC");
   @tmp=split(/-/o, $tmp1);

   # Get current local time to determine if the last data set 
   # is to far away from now
   ($year,$month,$day, $hour,$min,$sec) = Today_and_Now(0);
   ($Dd,$Dh,$Dm,$Ds) = Delta_DHMS($year,$month,$day, $hour,$min,$sec,
                                   $tmp[0], $tmp[1], $tmp[2],
   				   split(/:/o, $tmp2)                 );
   $tmp=$Dd*24+$Dh;  # Hours of delta from now to latest data set				   
				   
   #print "<br>Delta:$Dd,$Dh,$Dm,$Ds <br>\n"; 				   

   $tmpStr="Letzte Werte vom $tmp[2]-$tmp[1]-$tmp[0] um " .
           "$tmp2 Uhr"; 
   $tmpStr.=" (GMT)" if( $timeIsGMT );		   
   #$tmpStr.="&nbsp;&nbsp;$help";

   # Print latest data from text and date values:
   print "<DIV class=\"latestTabHead\">$tmpStr</DIV>\n";
   
   # Print How many hours ago this was
   if( $tmp < 0 && $tmp <= -2 ){
      $tmp=abs($tmp);
      print "<DIV class=\"latestTabHoursAgo\">&nbsp (Achtung: Werte sind $tmp Stunden alt)</DIV>\n";
   }
   print "&nbsp; $help\n";
   
   print "<p style=\"clear:both\">\n";
   
	# Create Table for Latest data
	$latestTab = simpleTable->new(
		  { "border" => "1", "cols" => "5", "auto" => "0", "fillEmptyCells" => "1" },
		  'class="latestTable"',
		  '<th class="latestTabHeader">Sensor</th><th class="latestTabHeader"> '
			. 'Wert1 </th><th class="latestTabHeader">Wert2</th>'
			. '<th class="latestTabHeader">Wert3</th>'
			. '<th class="latestTabHeader">Wert4</th>'
	);
   $latestTab->startTable(1,0);
   $k=0;
   # print out latestData for all sensors defined in $latestSens in the sequence
   # they are defined in $latestSens
   foreach $i (split(/\s+|,/, $latestSens)){
      foreach $j (keys(%latestSens)) {
      	if( $latestSens{$j}->{"type"}=~ /$i/i ){
	   $latestTab->newRow() if( $k );
	   $k=1;
      	   printLatestData(\%latestSens,$j, $latestTab);
	}
      }
   }
   $latestTab->endTable();
   print hr;
}



#
# Get mma start and end date/time from URL or from start/end date depending on
# Parameters in URL like "mma" etc.
#
sub calcMmaDates{
   my($startDate, $endDate, $startTime, $endTime, 
      $defaultStartTime, $defaultEndTime,$refDoPlotMma)=@_; 
   
   my($tmp, $tmp1, $tmp2 );
   my($mmaUrlParm, $mma);
   my($mmaStartDate,$mmaEndDate,$mmaStartTime,$mmaEndTime, @d);
   my($mmaStartDay, $mmaStartMon, $mmaStartYear, $mmaEndDay, $mmaEndMon,$mmaEndYear);
   my($locMmaStartYear, $locMmaStartMon, $locMmaStartDay,
      $locMmaEndYear, $locMmaEndMon, $locMmaEndDay,
      $locMmaStartHour, $locMmaStartMin, $locMmaStartSec,
      $locMmaEndHour, $locMmaEndMin, $locMmaEndSec );
        
   #
   # Decide if max,min and average should be printed
   $mmaUrlParm="";
   $mma=url_param("mma");
   if( length($mma) ) {  # Script was called by post with parameters
      ($refDoPlotMma->{"min"},$refDoPlotMma->{"max"},$refDoPlotMma->{"avg"})=
   	   split(/\s*,\s*/, $mma);
     # Time range for calculation of mma values
     if( $refDoPlotMma->{"avg"}==2 ){
  	   $mmaStartDate=url_param("mmasd");
	   $mmaStartDate=~s/_.*//o;
	   $mmaStartTime= $defaultStartTime;
  	   $mmaEndDate=url_param("mmaed");
	   $mmaEndDate=~s/_.*//o;
	   $mmaEndTime=$defaultEndTime;
	   $mmaUrlParm="mma=$mma;mmasd=$mmaStartDate;mmaed=$mmaEndDate";
      }else{
  	   $mmaStartDate=$startDate;
	   $mmaStartTime=$startTime;
  	   $mmaEndDate=$endDate;
	   $mmaEndTime=$endTime;
	   $mmaUrlParm="mma=$mma";
      }
   } else{
      $mmaStartDate=$startDate;
      $mmaStartTime=$startTime;
      $mmaEndDate=$endDate;
      $mmaEndTime=$endTime;
   }

   @d=split(/-/, $mmaStartDate);
   $mmaStartDay=$d[2]; $mmaStartMon=$d[1]; $mmaStartYear=$d[0];
   @d=split(/-/, $mmaEndDate);
   $mmaEndDay=$d[2]; $mmaEndMon=$d[1]; $mmaEndYear=$d[0];

   # Convert MMA times into local time
   ($tmp1, $tmp2)=timeConvert($mmaStartDate,$mmaStartTime, "LOC");
   ($locMmaStartYear, $locMmaStartMon, $locMmaStartDay)=split(/-/o, $tmp1);
   ($locMmaStartHour, $locMmaStartMin, $locMmaStartSec)=split(/:/o, $tmp2);
   
   ($tmp1, $tmp2)=timeConvert($mmaEndDate,$mmaEndTime, "LOC");
   ($locMmaEndYear, $locMmaEndMon, $locMmaEndDay)=split(/-/o, $tmp1);
   ($locMmaEndHour, $locMmaEndMin, $locMmaEndSec)=split(/:/o, $tmp2);

   return($mmaStartDate, $mmaStartTime, $mmaEndDate, $mmaEndTime,
    	$locMmaStartYear, $locMmaStartMon, $locMmaStartDay,
	$locMmaStartHour, $locMmaStartMin, $locMmaStartSec,
 	$locMmaEndYear, $locMmaEndMon, $locMmaEndDay,
	$locMmaEndHour, $locMmaEndMin, $locMmaEndSec,
	$mmaUrlParm
   );
}




#
# Create and show the navigation panel that lets the user navigate
# through time and select display options
#
sub showNavigationPanel{
   my($startDate, $endDate, $startTime, $endTime, 
      $defaultStartTime, $defaultEndTime, 
      $mmaStartDate, $mmaStartTime, 
      $mmaEndDate, $mmaEndTime,
      $locMmaStartYear, $locMmaStartMon, $locMmaStartDay,
      $locMmaStartHour, $locMmaStartMin, $locMmaStartSec,
      $locMmaEndYear, $locMmaEndMon, $locMmaEndDay, 
      $locMmaEndHour, $locMmaEndMin, $locMmaEndSec,
      $mmaUrlParm,
      $sampleTime, $sampleTimeBase, $sampleTimeUser,$defSampleTime, $defSampleDataType, $sampleDataType,
      $plots, $plotsSelected, $textPlots,
      $rainSumMode, $scaleMode, $defScaleMode, $defScaleFactor,
      $scaleFactor, $refDoPlotMma, $plotsTypeSerial, $refNow, $refFirst, $statisticsMode)=@_;
   
   # local variables   
   my($tmp, $tmp1, $tmp2, $tmp3, $tmp4, %links, %pLinks, $url, %urls, %pUrls, $i, %sampleTypeLabels);
   my($frameTab, $navTab, $tmpTab);
   my($endYear, $endMon, $endDay, $endHour, $endMin, $endSec,
      $startYear, $startMon, $startDay, $startHour, $startMin, $startSec,
      $locStartDay, $locStartMon, $locStartYear, $locStartDate,$locStartTime,
      $locEndDate, $locEndTime,
      $locEndDay, $locEndMon, $locEndYear);
   my($startLink, $actionUrl, $statisticsUrl, $nonStatisticsUrl,
      $statistics_1YM_Url);
   my(@d, $statistics);
   my($mmaStartDay, $mmaStartMon, $mmaStartYear, $mmaEndDay, $mmaEndMon,$mmaEndYear,
      $mmaLinkmma, $mmaLinkP2mma, $mmaLinkP3mma, 
      $mmaLink__a,$mmaLinkP2__a, $mmaLinkP3__a, $mmaLink___ );
   my($sampleTimeAllLink, $sampleTimeHourLink, $sampleTimeDayLink,$sampleTimeWeekLink,
      $sampleTimeMonthLink, $sampleTimeYearLink, $sampleDataTypeLinkAvg,
      $sampleDataTypeLinkMin,$sampleDataTypeLinkMax);
   my($periodEndDate,$periodEndTime,
      $periodSyear,$periodSmon, $periodSday,
      $periodShour, $periodSmin, $periodSsec, $periodDate, $periodUrl,
      $periodMonSyear,$periodMonSmon, $periodMonSday,
      $periodMonShour, $periodMonSmin, $periodMonSsec,
      $periodMonDate,$periodMonUrl);  
   my($tmpSyear, $tmpSmon, $tmpSday, $tmpShour, $tmpSmin, $tmpSsec,
      $tmpEyear, $tmpEmon, $tmpEday, $tmpEhour, $tmpEmin, $tmpEsec );  
    
    
   ($startYear, $startMon, $startDay)=split(/-/o, $startDate);
   ($startHour, $startMin, $startSec)=split(/:/o, $startTime);
   ($endYear, $endMon, $endDay)      =split(/-/o, $endDate); 
   ($endHour, $endMin, $endSec)      =split(/:/o, $endTime);
 
   # Convert start and end date into local time
   ($locStartDate, $locStartTime)=timeConvert($startDate, $startTime, "LOC");	
   ($locStartYear, $locStartMon, $locStartDay)=split(/-/o, $locStartDate);
   # Fill variables with local time
   ($locEndDate, $locEndTime)=timeConvert($endDate, $endTime, "LOC");	
   ($locEndYear, $locEndMon, $locEndDay)=split(/-/o, $locEndDate);
    

   # If a particular plot was selected keep this info in URL
   if( $plotsSelected ){
   	   if( $textPlots ){
	       $tmp = "tp";
	   }else{
	      $tmp = "pl";
	   }
	   $url="${scriptUrl}?$tmp=$plots$plotsTypeSerial";
   }else{
	   $url="$scriptUrl";
   }

   # Save the scripts url for the action attribute of the form
   # $url can now be changed to be used as a base in building
   # the date links etc.
   $actionUrl=$url;


   # If the user defined a scaling mode or factor add this to URL
   # for alle the date- and image-links
   if( $scaleMode ne $defScaleMode || $scaleFactor!=$defScaleFactor ){
      $url=addUrlParm($url, "sm=$scaleMode", "sf=$scaleFactor");
   }


   # Create Links for sampleTime: all, day, week, month, year
   # stuser is a flag meaning the user has selected this 
   # sample time it was NOT done automatically
   $sampleTimeAllLink=addUrlParm($url, "sd=${startDate}_$startTime;ed=${endDate}_$endTime",
                                  "st=0,$defSampleDataType", "stuser=1", $mmaUrlParm);
   $sampleTimeAllLink=addUrlParm($sampleTimeAllLink, "statMode=1") if( $statisticsMode );				
   # ------------------
   $sampleTimeHourLink=addUrlParm($url, "sd=${startDate}_$startTime;ed=${endDate}_$endTime",
                                   "st=h,$sampleDataType","rst=$rainSumMode", "stuser=1", $mmaUrlParm);
   $sampleTimeHourLink=addUrlParm($sampleTimeHourLink, "statMode=1") if( $statisticsMode );				
   # ------------------
   $sampleTimeDayLink=addUrlParm($url, "sd=${startDate}_$startTime;ed=${endDate}_$endTime",
                                   "st=d,$sampleDataType","rst=$rainSumMode", "stuser=1", $mmaUrlParm);
   $sampleTimeDayLink=addUrlParm($sampleTimeDayLink, "statMode=1") if( $statisticsMode );				
   # ------------------
   $sampleTimeWeekLink=addUrlParm($url, "sd=${startDate}_$startTime;ed=${endDate}_$endTime",
                                   "st=w,$sampleDataType", "rst=$rainSumMode", "stuser=1", $mmaUrlParm);
   $sampleTimeWeekLink=addUrlParm($sampleTimeWeekLink, "statMode=1") if( $statisticsMode );				
   # ------------------
   $sampleTimeMonthLink=addUrlParm($url, "sd=${startDate}_$startTime;ed=${endDate}_$endTime",
                                   "st=m,$sampleDataType", "rst=$rainSumMode", "stuser=1", $mmaUrlParm);
   $sampleTimeMonthLink=addUrlParm($sampleTimeMonthLink, "statMode=1") if( $statisticsMode );				
   # ------------------
   $sampleTimeYearLink=addUrlParm($url, "sd=${startDate}_$startTime;ed=${endDate}_$endTime",
                                   "st=y,$sampleDataType", "rst=$rainSumMode", "stuser=1", $mmaUrlParm);
   $sampleTimeYearLink=addUrlParm($sampleTimeYearLink, "statMode=1") if( $statisticsMode );				

   # Create Links for sampleTime: all, day, week, month, year
   $sampleDataTypeLinkAvg=addUrlParm($url, "sd=${startDate}_$startTime;ed=${endDate}_$endTime","st=$sampleTimeBase,Avg", 
                                     "stuser=$sampleTimeUser",  $mmaUrlParm);
   $sampleDataTypeLinkMin=addUrlParm($url, "sd=${startDate}_$startTime;ed=${endDate}_$endTime",
                                     "st=$sampleTimeBase,Min", "stuser=$sampleTimeUser", $mmaUrlParm);
   $sampleDataTypeLinkMax=addUrlParm($url, "sd=${startDate}_$startTime;ed=${endDate}_$endTime",
                                     "st=$sampleTimeBase,Max", "stuser=$sampleTimeUser", $mmaUrlParm);

   # If the user defined a sampleTime mode add this to URL
   # for alle the date- and image-links
   if( $sampleTimeBase ne $defSampleTime ){
      $url=addUrlParm($url, "st=$sampleTime" );
      $url=addUrlParm($url, "rst=$rainSumMode" );
      if( length($sampleTimeUser) ){
      	$url=addUrlParm($url, "stuser=$sampleTimeUser" );
      }
   }



   # Initialize datastructure for date links like next week, last week...
   # Tag is the number printed in the html form eg "1,2,4 days"
   $links{"day"}={ "months" => 0, "days"   => 1, "tag" => "1T"   };
   $links{"day2"}={"months" => 0, "days"   => 2, "tag" => "2T"   };
   $links{"day3"}={"months" => 0, "days"   => 3, "tag" => "3T"   };
   $links{"day4"}={"months" => 0, "days"   => 5, "tag" => "5T"   };
   # Copy data into period hash f%plinks or selection of one day, week,month, ... 
   # The plinks hash is used for the period links only, while the 
   # links hash is used for the +/- period links. The calculation 
   # for period links is different depending on sttaisticsMode.
   $plinks{"day"}=$links{"day"};
   $plinks{"day2"}=$links{"day2"};
   $plinks{"day3"}=$links{"day3"};
   $plinks{"day4"}=$links{"day4"};

   $links{"week"}={ "months" => 0, "days"   => 7, "tag" => "1W"   };
   $links{"week2"}={"months" => 0, "days"   => 14,"tag" => "2W"   };
   $links{"week3"}={"months" => 0, "days"   => 21,"tag" => "3W"   };
   # Copy data into period hash for selection of one day, week,month, ... 
   # See above
   $plinks{"week"}=$links{"week"};
   $plinks{"week2"}=$links{"week2"};
   $plinks{"week3"}=$links{"week3"};

   $links{"month"}={ "months" => 1, "days"   => 0, "tag" => "1M"  };
   $links{"month2"}={"months" => 3, "days"   => 0, "tag" => "3M"   };
   $links{"month3"}={"months" => 6, "days"   => 0, "tag" => "6M"   };
   # Copy data into period hash for selection of one day, week,month, ... 
   # See above
   $plinks{"month"}=$links{"month"};
   $plinks{"month2"}=$links{"month2"};
   $plinks{"month3"}=$links{"month3"};

   $links{"year"}={ "months" => 12, "days"   => 0, "tag" => "1J"  };
   $links{"year2"}={"months" => 36, "days"   => 0, "tag" => "3J"  };
   $links{"year3"}={"months" => 60, "days"   => 0, "tag" => "5J"  };
   $links{"year4"}={"months" => 120,"days"   => 0, "tag" => "10J" };
   # Copy data into period hash for selection of one day, week,month, ... 
   # See above
   $plinks{"year"}=$links{"year"};
   $plinks{"year2"}=$links{"year2"};
   $plinks{"year3"}=$links{"year3"};
   $plinks{"year4"}=$links{"year4"};


   # If statisticsmode was selected, create the 
   # "opposite" mode url
   if( $statisticsMode > 0){
      # The url has to be modified to stay in statMode by default
      $nonStatisticsUrl=$actionUrl;
      $url=addUrlParm($url, "statMode=1");
      #$nonStatisticsUrl=addUrlParm($nonStatisticsUrl, "sd=${startDate}_$startTime;ed=${endDate}_$endTime","st=$sampleTime");
      $nonStatisticsUrl=addUrlParm($nonStatisticsUrl, "sd=${startDate}_$startTime;ed=${endDate}_$endTime");

      # Create an instance of statistics Class to get
      # the %plinks values for statistics mode
      $statistics=statistics->new($tmp, $startDate, $startTime, 
                            $endDate, $endTime,  $sampleTime, $tmp1, $tmp1, 
      			    $refNow, $refFirst );
      $statistics->setPeriodData(\%links, \%plinks, $locEndDate);
      #
   }else{
      $statisticsUrl=$url;
      $statisticsUrl=~s/st=[^;]*;//o;
      $statistics_1YM_Url=$statisticsUrl;
      $statisticsUrl=addUrlParm($statisticsUrl, "statMode=1");
      $statisticsUrl=addUrlParm($statisticsUrl, "sd=${startDate}_$startTime;ed=${endDate}_$endTime","st=$sampleTime");

      # Statisticsmode for current year in month segments
      $tmp=$startYear-1;
      $statistics_1YM_Url=addUrlParm($statistics_1YM_Url, "sd=${tmp}-12-31_23:00:00;ed=${startYear}-12-31_22:59:59");
      $statistics_1YM_Url=addUrlParm($statistics_1YM_Url, "statMode=1;st=m,Avg");
      
   }
   
   

   # Calculate data for timeperiod links (display a day, a month. a year )
   # the values are calculated backwards from today
   # For one day we have to subtract one day and add one second since the endDate
   # alwyas ends at day x 23:59:59 and not 00:00:00, but the startDay should be
   # day y 00:00:00 and not 23:59:59

   ($tmp1, $tmp2)=timeConvert($endDate, $endTime, "LOC");
   $tmp2=$defaultEndTime;
   ($periodEndDate, $periodEndTime)=timeConvert($tmp1, $tmp2, "GMT");

   # Now calculate the period links (day, week, month) 
   foreach $i (keys(%links)){
	#
	# Days
	($periodSyear,$periodSmon, $periodSday, 
  		$periodShour, $periodSmin, $periodSsec)=
		Add_Delta_YMDHMS($locEndYear, $locEndMon, $locEndDay, $locEndHour, $locEndMin, $locEndSec,
	        	       0, -$plinks{$i}->{"months"}, -$plinks{$i}->{"days"}+1, 0, 0, 0); 

	# Set new start date to defaulttime
	$tmp1= "$periodSyear-$periodSmon-$periodSday";
	$tmp2=$defaultStartTime;
	# Now reconvert new local start time back to GMT
	($tmp1, $tmp2)=timeConvert($tmp1, $tmp2, "GMT");
	$periodDate="${tmp1}_$tmp2";
	# Store result
	$pUrls{$i}=addUrlParm($url, "sd=$periodDate;ed=${periodEndDate}_$periodEndTime", "$mmaUrlParm");
	
	#if( $statisticsMode ){
	#   $pUrls{$i}=addUrlParm($pUrls{$i}, "statMode=1" );
	#} 
   }



   # Calculate $periodMonDate for month MMA display date range below
   ($periodMonSyear,$periodMonSmon, $periodMonSday,
  	   $periodMonShour, $periodMonSmin, $periodMonSsec)=
	   Add_Delta_YMDHMS($locEndYear, $locEndMon, $locEndDay, $locEndHour, $locEndMin, $locEndSec,
	   0, -1, 0, 0, 0, 0);	
   
   $tmp1="$periodMonSyear-$periodMonSmon-$periodMonSday";
   $tmp2=$defaultStartTime;
   # Now reconvert new local start time back to GMT
   ($tmp1, $tmp2)=timeConvert($tmp1, $tmp2, "GMT");
   $periodMonDate="${tmp1}_$tmp2";


   # create links for setting mma options
   # We create links for the current period of time as well as for the last
   # month. They can can be distinguished by the value of mma
   # "1" means current period; "2" means month
   $mmaLinkmma=addUrlParm($url, "mma=1,1,1", "sd=${startDate}_$startTime", "ed=${endDate}_$endTime",
		   "st=$sampleTime", "rst=$rainSumMode");
   $tmp="mma=2,2,2;mmasd=$periodMonDate;mmaed=$endDate";
   $mmaLinkP2mma=addUrlParm($url, "$tmp", "sd=${startDate}_$startTime", "ed=${endDate}_$endTime", 
		   "st=$sampleTime", "rst=$rainSumMode");
   $tmp="mma=2,2,2;mmasd=$firstDate;mmaed=$endDate";
   $mmaLinkP3mma=addUrlParm($url, "$tmp", "sd=${startDate}_$startTime", "ed=${endDate}_$endTime", 
		   "st=$sampleTime", "rst=$rainSumMode");

   $mmaLink__a=addUrlParm($url, "mma=0,0,1", "sd=${startDate}_$startTime", "ed=${endDate}_$endTime", 
		   "st=$sampleTime", "rst=$rainSumMode");
   $tmp="mma=0,0,2;mmasd=$periodMonDate;mmaed=$endDate";
   $mmaLinkP2__a=addUrlParm($url, "$tmp", "sd=${startDate}_$startTime", "ed=${endDate}_$endTime", 
		   "st=$sampleTime", "rst=$rainSumMode");
   $tmp="mma=0,0,2;mmasd=$firstDate;mmaed=$endDate";
   $mmaLinkP3__a=addUrlParm($url, "$tmp", "sd=${startDate}_$startTime", "ed=${endDate}_$endTime", 
		   "st=$sampleTime", "rst=$rainSumMode");

   $mmaLink___=addUrlParm($url, "mma=0,0,0", "sd=${startDate}_$startTime", "ed=${endDate}_$endTime", 
		   "st=$sampleTime", "rst=$rainSumMode");

   #print "$startTime, $endTime;; $startYear, $startMon, $startDay -> $endYear, $endMon, $endDay <br>\n";
   # Calculate URLs for tomorrow, yesterday, ... links
   foreach $i (keys(%links)){
	   # Get dates of tomorrow, next week, etc
	   ($tmpSyear, $tmpSmon, $tmpSday, $tmpShour, $tmpSmin, $tmpSsec)=
		   Add_Delta_YMDHMS($locStartYear, $locStartMon, $locStartDay,
			   $locStartHour, $locStartMin, $locStartSec, 
			   0, $links{$i}->{"months"}, $links{$i}->{"days"},
			   0, 0, 0);
	   ($tmpEyear, $tmpEmon, $tmpEday, $tmpEhour, $tmpEmin, $tmpEsec)=
		   Add_Delta_YMDHMS($locEndYear, $locEndMon, $locEndDay,
			   $locEndHour, $locEndMin, $locEndSec, 
			   0, $links{$i}->{"months"}, $links{$i}->{"days"},
			   0, 0, 0);
	   # Convert new period Start and End to GMT 
	   ($tmp1, $tmp2)=timeConvert("${tmpSyear}-${tmpSmon}-${tmpSday}", $defaultStartTime, "GMT");		   
	   ($tmp3, $tmp4)=timeConvert("${tmpEyear}-${tmpEmon}-${tmpEday}", $defaultEndTime, "GMT");		   
	   #
	   # store URL eg in "next_week"
	   $urls{"next_$i"}=addUrlParm($url, 
	             "sd=${tmp1}_${tmp2};" . "ed=${tmp3}_${tmp4};" . "$mmaUrlParm");

	   # Get dates of yesterday, last week etc
	   ($tmpSyear, $tmpSmon, $tmpSday, $tmpShour, $tmpSmin, $tmpSsec)=
		   Add_Delta_YMDHMS($locStartYear, $locStartMon, $locStartDay, 
			   $locStartHour, $locStartMin, $locStartSec, 
			   0, $links{$i}->{"months"}*-1, $links{$i}->{"days"}*-1,
			   0, 0, 0);
		   # In statistics mode when we look at the current year, 
		   # in a month by month fashion,  eg when it is now fisrt 
		   # May, and then we click "-1 years"  we want that the whole last year
		   # is displayed and not only Jan-May as in the current year.
		   # So in this case we have to rewrite the end date
		   if( $statisticsMode >0 && $sampleTime=~/m,/ ){
	               ($tmpEyear, $tmpEmon, $tmpEday, $tmpEhour, $tmpEmin, $tmpEsec)=	      
	               Add_Delta_YMDHMS($locEndYear, 12, 31,
			   $locEndHour, $locEndMin, $locEndSec, 
			   0, $links{$i}->{"months"}*-1, $links{$i}->{"days"}*-1,
			   0, 0, 0);
		   }else{
 	               ($tmpEyear, $tmpEmon, $tmpEday, $tmpEhour, $tmpEmin, $tmpEsec)=	      
 		       Add_Delta_YMDHMS($locEndYear, $locEndMon, $locEndDay,
			   $locEndHour, $locEndMin, $locEndSec, 
			   0, $links{$i}->{"months"}*-1, $links{$i}->{"days"}*-1,
			   0, 0, 0);
		   }	   
	   
	   # Convert new period Start and End to GMT 
	   ($tmp1, $tmp2)=timeConvert("${tmpSyear}-${tmpSmon}-${tmpSday}", $defaultStartTime, "GMT");		   
	   ($tmp3, $tmp4)=timeConvert("${tmpEyear}-${tmpEmon}-${tmpEday}", $defaultEndTime, "GMT");		   

	   #
	   # store URL eg in "last_week"
	   $urls{"last_$i"}=addUrlParm($url,
     	                       "sd=${tmp1}_${tmp2};ed=${tmp3}_${tmp4}", "$mmaUrlParm");
   }


	 # *****************************************************************
	 $frameTab = simpleTable->new( 
    { "cols" => "1", "auto" => "0" },
			'class="controlPanel"', 
      "" 
    );
   #    'background="sky3.jpg" border="1" cellspacing="1" cellpadding="1"', "");
   $frameTab->setRowOptions("VALIGN='TOP'");
   $frameTab->startTable(1,0);    
   $navTab=simpleTable->new({"cols"=>"6", "auto"=>"0"},  
       'border="0" cellspacing="1" cellpadding="1" width="100%"', "");
   print start_form(-method=>"post", -action=>"$url" ); # ***

   $navTab->startTable(1,2); # Open first col with colspan=2
   print '<FONT class="navTabHead">', "Darstellungsparameter:", '</FONT>'; 
   $navTab->newCol(2);$navTab->newCol(3);
   print '<FONT class="navTabHead">', "Aktuell verwendete Einstellungen:", '</FONT>'; 
   $navTab->newRow(); print " "; $navTab->newRow();

   # Start output for HTML input form
   print '<FONT class="navTabActHead">', "Skalierung der Graphiken ...", '</FONT>'; 
   $navTab->newCol(); helpLink(-1, "?", "scaling", 0);
   $navTab->newRow(3);

   print '<FONT class="navTabCurText">';
     print radio_group(-name=>'scaling',
                	-values=>['x','y','x+y'],
			-default=>$scaleMode); 
     print ", &nbsp;&nbsp;", "Skalierungsfaktor: ", 
           textfield(-class=>"navTabCurText", -name => "scaleFactor",
                   -default => $scaleFactor,
		   -override=>1,
                   -size => "3",
                   -maxlength=>5);
   print '</FONT>';

   $navTab->newCol();print "&nbsp;&nbsp;&nbsp;&nbsp;"; $navTab->newCol();
   print '<FONT class="navTabCurHead">', "Skalierung:", '</FONT>'; 
   $navTab->newCol();  
   print '<FONT class="navTabCurText">', 
   	"Modus: $scaleMode, Faktor: $scaleFactor </FONT>\n";
   $navTab->newRow(2);

   print '<FONT class="navTabActHead">', "Darstellungszeitraum ...", '</FONT>'; 
   $navTab->newCol(); helpLink(-1, "?", "displayPeriod", 0); $navTab->newRow(3);


   print '<FONT class="navTabCurText">', "Vom ";   
   print textfield(-name => "startDay",
   		   -class=>"navTabCurText",
		   -default => $locStartDay,
		   -size => "2",
		   -maxlength=>2) ,
	" - ",

	   textfield(-name => "startMonth",
   		   -class=>"navTabCurText",
		   -default => $locStartMon,
		   -size => "2",
		   -maxlength=>2) ,
	" - ",
	   textfield(-name => "startYear", 
   		   -class=>"navTabCurText",
		   -default => $locStartYear,
		   -size => "4",
		   -maxlength=>4); 

   print "\n", "bis: "; 
   print textfield(-name => "endDay", 
   		   -class=>"navTabCurText",
		   -default => $locEndDay,
		   -size => "2",
		   -maxlength=>2),
	" - ",
	   textfield(-name => "endMonth",
   		   -class=>"navTabCurText",
		   -default => $locEndMon,
		   -size => "2",
		   -maxlength=>2),
	" - ",
	   textfield(-name => "endYear", 
   		   -class=>"navTabCurText",
		   -default => $locEndYear,
		   -size => "4",
		   -maxlength=>4);  

   print "&nbsp", submit(-class=>"navTabCurText",-name=>'Anzeigen');
   print "</FONT>";
             
   $navTab->newCol(); $navTab->newCol();
   print '<FONT class="navTabCurHead">', "Zeitraum:", '</FONT>';
   $navTab->newCol(); 
   print '<FONT class="navTabCurText">',
         " $locStartDay.$locStartMon.$locStartYear - " .
                        	  "$locEndDay.$locEndMon.$locEndYear",
				  '</FONT>';
   if( $timeIsGMT ){
	   print " (GMT)\n";
   }else{
	   print "\n";
   }	
   
   # In the statistics mode display there is no MMA choice to display
   if( $statisticsMode == 0 ){
      $navTab->newRow(2);

      print '<FONT class="navTabActHead">', "Min/Max/Avg-Anzeige ...", '</FONT>';
      $navTab->newCol(); helpLink(-1, "?", "mma", 0); $navTab->newRow();

      print    a({-class=>"navTabLink", href=>$mmaLinkmma},"Zeige MMA aktuell") , br,
               a({-class=>"navTabLink", href=>$mmaLinkP2mma},"Zeige MMA Monat"), br
               a({-class=>"navTabLink", href=>$mmaLinkP3mma},"Zeige MMA alles"), "\n";

      $navTab->newCol();
      print    a({-class=>"navTabLink", href=>$mmaLink__a},"Zeige --A aktuell"), br,
               a({-class=>"navTabLink", href=>$mmaLinkP2__a},"Zeige --A Monat"), br,
               a({-class=>"navTabLink", href=>$mmaLinkP3__a},"Zeige --A alles") ;
      $navTab->newCol();
      print a({-class=>"navTabLink", href=>$mmaLink___},"Keine MMA-Anzeige"), "\n";
      $navTab->newCol();$navTab->newCol(2);

      $tmpTab=simpleTable->new({"cols"=>"2", "auto"=>"0"},
		      'border="0" cellspacing="1" cellpadding="1"', "");
      $tmpTab->startTable(1,0);
      print '<FONT class="navTabCurHead">', "MMA:</FONT><br>";$tmpTab->newCol();
      if( !$refDoPlotMma->{"min"} && !$refDoPlotMma->{"max"} && !$refDoPlotMma->{"avg"} ){
	  print '<FONT class="navTabCurText">', 
        	"Keine MMA-Graphiken </FONT>\n" ;
      }else{
	      print '<FONT class="navTabCurText">';
	      print "Minimum " if( $refDoPlotMma->{"min"} );
	      print "Maximum " if( $refDoPlotMma->{"max"} );
	      print "Average " if( $refDoPlotMma->{"avg"} );
	      print "(ber die Originaldaten)\n";
	      print "</FONT>\n";
      }
      $tmpTab->newRow();  print '<FONT class="navTabCurHead">', "MMA-Basis: ", '</FONT>'; 
      $tmpTab->newCol();
      print  '<FONT class="navTabCurText">',
              "$locMmaStartDay.$locMmaStartMon.$locMmaStartYear - " .
 	      "$locMmaEndDay.$locMmaEndMon.$locMmaEndYear",
              "</FONT> \n";
      $tmpTab->endTable();  undef $tmpTab;
   }# if ($statisticsMode)
   
   $navTab->newRow(2);

   print '<FONT class="navTabActHead">', "Quicknavigation f&uuml;r Darstellung...", '</FONT>';
   $navTab->newCol(); helpLink(-1, "?", "quicknavi", 0); $navTab->newRow();
   
   # ***** Day links 
   # +++ Period links 
    # When statisticsmode is active and show the +day, -day, ... links only when 
    # the daterange of the ststisticsdisplay is days else this would not make sense
   if( $sampleTime=~/^[d]/o ||  $statisticsMode==0 ){
      print '<FONT class="navTabLink">Tage:&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; </FONT>';
      print a({-class=>"navTabLink", href=>$pUrls{"day"}}, $links{"day"}->{"tag"} ), ", "; 	     
      print a({-class=>"navTabLink", href=>$pUrls{"day2"}}, $links{"day2"}->{"tag"} ), ", "; 	     
      print a({-class=>"navTabLink", href=>$pUrls{"day3"}},
      $links{"day3"}->{"tag"} ), ", "; 	     
      print a({-class=>"navTabLink", href=>$pUrls{"day4"}}, $links{"day4"}->{"tag"} ); 	     
      $navTab->newCol();

      # +++ "prev"-links 
      print a({-class=>"navTabLink", href=>$urls{"last_day"}}, "-".$links{"day"}->{"tag"}), " ";
      print a({-class=>"navTabLink", href=>$urls{"last_day2"}}, "-".$links{"day2"}->{"tag"}), " ";
      print a({-class=>"navTabLink", href=>$urls{"last_day3"}},
      "-".$links{"day3"}->{"tag"}), " ";
      print a({-class=>"navTabLink", href=>$urls{"last_day4"}}, "-".$links{"day4"}->{"tag"});
      $navTab->newCol();

      # +++ "next"-links 
      print a({-class=>"navTabLink", href=>$urls{"next_day"}}, "+".$links{"day"}->{"tag"}), " ";
      print a({-class=>"navTabLink", href=>$urls{"next_day2"}}, "+".$links{"day2"}->{"tag"}), " ";
      print a({-class=>"navTabLink", href=>$urls{"next_day3"}},
      "+".$links{"day3"}->{"tag"}), " ";
      print a({-class=>"navTabLink", href=>$urls{"next_day4"}}, "+".$links{"day4"}->{"tag"});
      $navTab->newRow();
   }
   
  
   # ***** Week links  
   # +++ Period links 
   # When statisticsmode is active and show the +week, -week, ... links only when 
   # the daterange of the statisticsdisplay is weeks or days else this would not make sense
   if( $sampleTime=~/^[dw]/o ||  $statisticsMode==0 ){
      print '<FONT class="navTabLink">Wochen: </FONT>';
      print a({-class=>"navTabLink", href=>$pUrls{"week"}}, $links{"week"}->{"tag"} ), ", "; 	     
      print a({-class=>"navTabLink", href=>$pUrls{"week2"}}, $links{"week2"}->{"tag"} ), ", "; 	     
      print a({-class=>"navTabLink", href=>$pUrls{"week3"}}, $links{"week3"}->{"tag"} ); 	     
      $navTab->newCol();

      # +++ "prev"-links 
      print a({-class=>"navTabLink", href=>$urls{"last_week"}}, "-".$links{"week"}->{"tag"}), " ";
      print a({-class=>"navTabLink", href=>$urls{"last_week2"}}, "-".$links{"week2"}->{"tag"}), " ";
      print a({-class=>"navTabLink", href=>$urls{"last_week3"}}, "-".$links{"week3"}->{"tag"});
      $navTab->newCol();


      # +++ "next"-links 
      print a({-class=>"navTabLink", href=>$urls{"next_week"}}, "+".$links{"week"}->{"tag"}), " ";
      print a({-class=>"navTabLink", href=>$urls{"next_week2"}}, "+".$links{"week2"}->{"tag"}), " ";
      print a({-class=>"navTabLink", href=>$urls{"next_week3"}}, "+".$links{"week3"}->{"tag"});
      $navTab->newRow();
   }
   

   # ***** Month links  
   # +++ Period links 
   print '<FONT class="navTabLink">Monate: </FONT>';
   print a({-class=>"navTabLink", href=>$pUrls{"month"}}, $links{"month"}->{"tag"} ), ", "; 	     
   print a({-class=>"navTabLink", href=>$pUrls{"month2"}}, $links{"month2"}->{"tag"} ), ", "; 	     
   print a({-class=>"navTabLink", href=>$pUrls{"month3"}}, $links{"month3"}->{"tag"} ); 	     

   $navTab->newCol();

   # +++ "prev"-links 
   print a({-class=>"navTabLink", href=>$urls{"last_month"}}, "-".$links{"month"}->{"tag"}), " ";
   print a({-class=>"navTabLink", href=>$urls{"last_month2"}}, "-".$links{"month2"}->{"tag"}), " ";
   print a({-class=>"navTabLink", href=>$urls{"last_month3"}}, "-".$links{"month3"}->{"tag"}), " ";
   $navTab->newCol();


   # +++ "next"-links 
   print a({-class=>"navTabLink", href=>$urls{"next_month"}}, "+".$links{"month"}->{"tag"}), " ";
   print a({-class=>"navTabLink", href=>$urls{"next_month2"}}, "+".$links{"month2"}->{"tag"}), " ";
   print a({-class=>"navTabLink", href=>$urls{"next_month3"}}, "+".$links{"month3"}->{"tag"}), " ";
   $navTab->newRow();


   # ***** Year links  
   # +++ Period links 
   print '<FONT class="navTabLink">Jahre:&nbsp;&nbsp;&nbsp; </FONT>';
   print a({-class=>"navTabLink", href=>$pUrls{"year"}}, $links{"year"}->{"tag"} ), ", "; 	     
   print a({-class=>"navTabLink", href=>$pUrls{"year2"}}, $links{"year2"}->{"tag"} ), ", "; 	     
   print a({-class=>"navTabLink", href=>$pUrls{"year3"}}, $links{"year3"}->{"tag"} ), ", "; 	     
   print a({-class=>"navTabLink", href=>$pUrls{"year4"}}, $links{"year4"}->{"tag"} ); 	     

   $navTab->newCol();

   # +++ "prev"-links 
   print a({-class=>"navTabLink", href=>$urls{"last_year"}}, "-".$links{"year"}->{"tag"}), " ";
   print a({-class=>"navTabLink", href=>$urls{"last_year2"}}, "-".$links{"year2"}->{"tag"}), " ";
   print a({-class=>"navTabLink", href=>$urls{"last_year3"}}, "-".$links{"year3"}->{"tag"}), " ";
   print a({-class=>"navTabLink", href=>$urls{"last_year4"}}, "-".$links{"year4"}->{"tag"});
   $navTab->newCol();


   # +++ "next"-links 
   print a({-class=>"navTabLink", href=>$urls{"next_year"}}, "+".$links{"year"}->{"tag"}), " ";
   print a({-class=>"navTabLink", href=>$urls{"next_year2"}}, "+".$links{"year2"}->{"tag"}), " ";
   print a({-class=>"navTabLink", href=>$urls{"next_year3"}}, "+".$links{"year3"}->{"tag"}), " ";
   print a({-class=>"navTabLink", href=>$urls{"next_year4"}}, "+".$links{"year4"}->{"tag"});

   $navTab->newCol();

   $navTab->newRow(2);


   print '<FONT class="navTabActHead">', "Nutze f&uuml;r die Darstellung ...", '</FONT>'; 
   $navTab->newCol(); helpLink(-1, "?", "sampleTime", 0); $navTab->newRow();

   # Statistics mode does not allow to select Minima/Maxima as base data, raw data is used
   if( $statisticsMode == 0 ){
      print '<FONT class="navTabLink"><B>', a({href=>$sampleTimeAllLink},"Originaldaten"), "</FONT>";
      if( $sampleTime !~ /^0/o ){
	      $navTab->newCol();
	      print '<FONT class="navTabLink">', " oder ...", '</FONT>';
	      $navTab->newRow();
	      print a({-class=>"navTabLink", href=>$sampleDataTypeLinkAvg}, "Mittelwerte"); $navTab->newCol();
	      print a({-class=>"navTabLink", href=>$sampleDataTypeLinkMin}, "Minima"); $navTab->newCol();
	      print a({-class=>"navTabLink", href=>$sampleDataTypeLinkMax}, "Maxima"); $navTab->newCol();
	      print '<FONT class="navTabLink">', "auf...", '</FONT>';
      }else{
	      $navTab->newCol(2);
	      print '<FONT class="navTabLink">', "oder Mittelwerte auf ...", '</FONT>';
      }

      $navTab->newRow();
      print a({-class=>"navTabLink", href=>$sampleTimeHourLink}, "Stundenbasis"); $navTab->newCol();
   }else{
      $navTab->newRow(); 
      print '<FONT class="navTabLink">Abschnitte auf ...';
      $navTab->newCol(); 
   }

   print a({-class=>"navTabLink", href=>$sampleTimeDayLink}, "Tagesbasis"); $navTab->newCol();
   print a({-class=>"navTabLink", href=>$sampleTimeWeekLink},"Wochenbasis");
   $navTab->newRow();
   print a({-class=>"navTabLink", href=>$sampleTimeMonthLink},"Monatsbasis"); $navTab->newCol();
   print a({-class=>"navTabLink", href=>$sampleTimeYearLink},"Jahresbasis");

   $navTab->newCol(); print "&nbsp;";
   $navTab->newCol(); print "&nbsp;";
   $navTab->newCol(); print "&nbsp;";

   print '<FONT class="navTabCurHead">', "Datenbasis: ", '</FONT>'; 
   $navTab->newCol();
   
   print '<FONT class="navTabCurText">';
   print "Original-Daten\n" if( $sampleTime =~ /^0/o );

   if( $statisticsMode == 0 ){
      if( ($plotsSelected  && $plots=~/RA/io && $rainSumMode ) ){
          %sampleTypeLabels=("Avg"=>'Summe', "Min"=>'Minima', "Max"=>'Maxima');
      }else{
         %sampleTypeLabels=("Avg"=>'Mittelwerte', "Min"=>'Minima', "Max"=>'Maxima');
      }
   }else{
      %sampleTypeLabels=("Avg"=>'Abschnitte', "Min"=>'Abschnitte', "Max"=>'Abschnitte');
   }
   $tmp=$sampleTypeLabels{$sampleDataType};
   print "$tmp auf Stundenbasis\n" if( $sampleTime =~ /^h/o );
   print "$tmp auf Tagesbasis\n" if( $sampleTime =~ /^d/o );
   print "$tmp auf Wochenbasis\n" if( $sampleTime =~ /^w/o );
   print "$tmp auf Monatsbasis\n" if( $sampleTime =~ /^m/o );
   print "$tmp auf Jahresbasis\n" if( $sampleTime =~ /^y/o );
   #
   print '</FONT>';
   
   if( !$statisticsMode && !$plotsSelected  && $rainSumMode && $sampleTime !~ /^0/o ){
      print '<FONT class="navTabCurText">';
      print "<br>(Summen f&uuml;r Regensensor)";
      print '</FONT>';
      
   }
   
   if( ($statisticsMode == 0) && $sampleTime !~ /^0/o && 
       ( !$plotsSelected || ($plotsSelected  && $plots=~/RA/io)) 
     ) {
      $navTab->newRow(3);
      print '<FONT class="">', checkbox(-name=>'rainSum', 
		  -checked=>1-$rainSumMode, 
		  -value=>"1", 
		  -label=>"Mittelwerte f&uuml;r Regensonsor (statt Summen...)");
      print '</FONT>';	       
   }
   #
   $navTab->newRow();
   print '<FONT class="navTabActHead">', "Darstellen als: ", '</FONT>'; 

   $navTab->newRow();
   if( $statisticsMode ){
       print a({-class=>"navTabLink", href=>$nonStatisticsUrl}, "Graphik Display");
   }else{
       print a({-class=>"navTabLink", href=>$statisticsUrl}, "Statistik (Auto)");
       $navTab->newCol();
       print a({-class=>"navTabLink", href=>$statistics_1YM_Url}, "Statistik J:M");
   }
   
   
   #$navTab->newCol(); print "&nbsp;";
   $navTab->newCol(); print "&nbsp;";
   $navTab->newCol(); print "&nbsp;";
   $navTab->newCol(); print "&nbsp;";

   print '<FONT class="navTabCurHead">', "Darstellung: ", '</FONT>';
   $navTab->newCol(0, '<FONT class="navTabCurText"');
   if( ! $statisticsMode ){
      print "Graphik Display" ;
   }else{
      print "Statistik Display" ;
   }   


   $navTab->endTable(); 
   $frameTab->endTable();
   print end_form;
}


#
# Display the grafixs overview showing all sensors or the more
# detailed grafic of only one sensor
#
sub showGrafixPanel{
   my($dbh, $sensorData, 
      $plotsSelected, $plots, $plotsTypeSerial,
      $rainSumMode, $sampleTime, $sampleTimeUser,
      $startDate, $startTime, $endDate, $endTime,
      $mmaStartDate, $mmaStartTime, $mmaEndDate, $mmaEndTime,
      $locMmaStartDay, $locMmaStartMon, $locMmaStartYear,
      $locMmaEndDay, $locMmaEndMon, $locMmaEndYear, 
      $xScaleFactor, $yScaleFactor, 
      $url, $startLink,
      $refDoPlotMma,
      $mmaUrlParm, $scaleMode, $scaleFactor)=@_;
      
   my($i, $j, $k, $tmp, $tmpCnt,
      @tmp,
      $refSensor, $typeSerial, $firstRun,
      $seenErrCodes, $allErrMsg, $errCode, $errMsg, 
      $xscale, $yscale, $theSampleTime,
      $gfxSensTab, $imgUrl, $dataManager, $textUrl );
      
   $seenErrCodes="";
   $allErrMsg="";
   $refSensor=$sensorData->getFirstSensor("graphics");
   
   # If not a single sensor was selected but the overview 
   # Create a new table for all the sensors to be displayed
   if( !$plotsSelected ){
      # Give user a hint ...
      print '<FONT class="medium">',  "&nbsp;<br>Zur genaueren Ansicht, bitte auf " . 
        	  "gew&uuml;nschtes Bild klicken ...\n", '</FONT>';

      # Create a table for output of graphics
		  $gfxSensTab = simpleTable->new(
			{ "cols" => $colGrfxTable, "auto" => "1" },
        'border="1" width="100%" cellspacing="2" cellpadding="5" class="grfxContainer"',
			   ""
		  );
      $gfxSensTab->setRowOptions("VALIGN='TOP'");
      $gfxSensTab->startTable(1,0);
   }
   $firstRun=1; # needed below
   
   # Now iterate over the sensors defined and marked plottable
   while( defined(%{$refSensor}) ){
      $typeSerial=${$refSensor}{"typeSerial"};
      # Do plot only if ${$refSensor}{"doPlot"} or if 
      # either $plotsSelected is false or 
      # it is true and the sensor in question has actually been selected to be plotted 
      # by the user which can be seen in the list of sensorTypes in $plots
      if( ${$refSensor}{"doPlot"} && (
            !$plotsSelected || ( $plots =~ /${$refSensor}{"sensType"}/ 
	 			 && $typeSerial == $plotsTypeSerial )) ){

	 if( $plotsSelected ){
  	      $xscale=${$refSensor}{"xNormalScale"} * $xScaleFactor;
  	      $yscale=${$refSensor}{"yNormalScale"} * $yScaleFactor;
	 }else{
  	      $xscale=${$refSensor}{"xSmallScale"} * $xScaleFactor;
  	      $yscale=${$refSensor}{"ySmallScale"} * $yScaleFactor;
	 }

	 $theSampleTime=$sampleTime;
	 if( (${$refSensor}{"sensType"} =~/RA/ && 
	     $sampleTime !~ /^0/o && $rainSumMode) ||
	     (${$refSensor}{"sensType"} =~/LD/ && $sampleTime !~ /^0/o) ){
      	   # For rain sensor user may want to see summary values instead of 
	   # average values (default) if $sampleTime is day, week, month ....
	   # This is marked by appending a capital S to the value of $sampleTime
	   $theSampleTime=~s/,/S,/;
	 }


	 # Create a new Data Object for one sensor.
	 $dataManager=dataManager->new($dbh, $sensorData, $refSensor, 
	 				\%dstRange);

	 # Set options needed for the work the dataManger Class does
	 $dataManager->setOptions( {"sampleTime"=>"$theSampleTime",
	 			   "startDate" => "$startDate",
	 			   "startTime" => "$startTime",
	 			   "endDate" => "$endDate",
	 			   "endTime" => "$endTime",
				   "mmaStartDate"=>$mmaStartDate,
				   "mmaStartTime"=>$mmaStartTime,
				   "mmaEndDate"  =>$mmaEndDate,
				   "mmaEndTime"  =>$mmaEndTime,
				   "xscale"  =>  "$xscale",  # scaling for graphics
				   "yscale"  =>  "$yscale",
				   "dataFilename" => "/tmp/wetterData_$$.txt",
				   "gnuplotFilename" => "/tmp/wetterGnuplot_$$.txt",
				   "bgColorAverage" =>  $bgColorAverage ,
				   "bgColorNormal"  => $bgColorNormal,
				   "gnuplotBinary" => "$gnuplot",
				   "refDoPlotMma"  => $refDoPlotMma});

	# At the moment we ty the plotting of MMA values of virtual sensors 
	# to the settings of the real sensor. So if MMA values are plotted for
	# a real sensor they also will be plotted for its virtual sensors
	# An exception to this rule is if the mma daterange is different
	# from the datrange of the graphics display. In this case we cannot display
	# virtsens MMA data, since we only have them for the daterange of the display
	$errCode=$dataManager->checkVirtMma($refSensor);
				   
        # Do all needed preparation work. This function also gets MMA values
	# The are stored in 
	# $dataManager->{"results"}->{<sensid>}->{"mma"}->{<mmaDBColName>}->
	#  ...->{"minValue"},  ...->{"minDate"}, ...->{"minTime"}
	#  ...->{"maxValue"},  ...->{"maxDate"}, ...->{"maxTime"}
	#  ...->{"avgValue"}
	$dataManager->prepareSensData(0);  
	
	# Run Gnuplot to create the graphics
	$errCode|=$dataManager->runGnuplot();
	
	# Unlink temp files and SQL result data (MMA data are left untouched)
	# This is done to save memory since the complete results of one
	# sql query are kept in main memory
	$dataManager->unlinkTmpData();  
	
	 
	# If there was an error/warning that should be displayed to the user
	# Note this message. To avoid double warning of the same type 
	# we uses an errorType that has a n associated message.
	# Each errcode that was found is noted in $seenErrCodes so a second error
	# of the same type can be skipped.
	if( $errCode ){
	    if( $seenErrCodes !~ /$errCode/i ){
		    $allErrMsg.="<br>" if( length($allErrMsg) );
		    $seenErrCodes.="$errCode ";  # Note this code as "seen"
		    $allErrMsg.=$main::errMsg ;
	    }
	}	    
      
        # Now we need to distinguish wheater the user selected one particular sensor
	# to be displayed or if he wants to see the overview with several sensors
	# in which case $plotSelected is 0 
	if( !$plotsSelected ){  
	   # User wants see the sensor overview
	   # Start next HTML table column or row if this is not the very first run
	   $gfxSensTab->newCol() if( ! $firstRun );	  
	   $firstRun=0;

	   # e.g: TH0
	   $tmp=${$refSensor}{"sensType"} . ${$refSensor}{"typeSerial"};
	   $url=addUrlParm($scriptUrl, "pl=$tmp",
		"sd=${startDate}_$startTime;ed=${endDate}_$endTime", "$mmaUrlParm",
		"sm=$scaleMode", "sf=$scaleFactor", "st=$sampleTime",
		"rst=$rainSumMode");
	   if( $sampleTimeUser ){
	      $url=addUrlParm($url, "stuser=$sampleTimeUser");
	   }	
	  
	   $imgUrl=$sensorData->getSensImgUrl($refSensor);     
	   # Title of grafics
   	   print '<FONT class="grfxTitle">',$refSensor->{"grfxName"} , '</FONT>'; 
	   if( $refSensor->{"sensType"}=~/WI/ || $refSensor->{"sensType"} =~ /WD/ ){
	      print "&nbsp;&nbsp;", helpLink(-2, "?", "sensorGraphicsWind", 1), "<br>";
	   }elsif( $refSensor->{"sensType"}=~/RA/ ){
	      print "&nbsp;&nbsp;", helpLink(-2, "?", "sensorGraphicsRain", 1), "<br>";
	   }elsif( $refSensor->{"sensType"}=~/LD/ ){
	      print "&nbsp;&nbsp;", helpLink(-2, "?", "sensorGraphicsLD", 1), "<br>";
	   }else{
	      print "&nbsp;&nbsp;", helpLink(-2, "?", "sensorGraphics", 1), "<br>";
	   }
	   
	   if( $dataManager->{"results"}->{"gnuplotHasPlots"} ){
	      print a({href=>$url, target=>"_blank"},
			img {src=>"$imgUrl", align=>"TOP"});
	   }else{
	   	print "<br>&mdash; <FONT size=-2>Keine Daten</FONT> &mdash;\n";
	   }
	   # Print out the URL to select textual output
	   $textUrl=$url; $textUrl=~s/pl=/tp=/;
	   if( ($refSensor->{"sensType"} eq "RA" || $refSensor->{"sensType"} eq "LD" ) && 
	       $sampleTimeUser==0 ){
	       # Since the rain sensor default display for min/Max/Avg is based on hours
	       # We show the table values for this sensor also based on hours by default.
	       # We only do this if the user has not preselected a 
	       # certain sampleTime ($sampleTimeUser==0)
	       $textUrl=~s/st=0,Avg/st=h,Avg/;
	   }
	   
	   print "<br>";
	   print a({-class=>"tiny",href=>$textUrl, target=>"_blank"}, "Als Tabelle ...");
	   
	   # Now create a list with the mma-names to be displayed
	   # eg temp0, hum0
	   if( ${$refSensor}{"displayMMA"} ){
	      print hr;
	      undef @tmp;
	      $tmpCnt=0;
	      foreach $i (@{${$refSensor}{"mmaNames"}}){
		  $tmp[$tmpCnt++]="$i".${$refSensor}{"typeSerial"};
	      }
	      $tmp=${$refSensor}{"mmaHeight"};
	   }
	}else{   # if  plotsSelected
	
   	     print '<br><FONT class="grfxTitle">',$refSensor->{"grfxName"} , '</FONT>'; 
	     if( $refSensor->{"sensType"} =~ /WI/ || $refSensor->{"sensType"} =~ /WD/ ){
		print "&nbsp;&nbsp;", helpLink(-2, "?", "sensorGraphicsWind", 1), "<br>";
	     }elsif( $refSensor->{"sensType"}=~/RA/ ){
	        print "&nbsp;&nbsp;", helpLink(-2, "?", "sensorGraphicsRain", 1), "<br>";
	     }elsif( $refSensor->{"sensType"}=~/LD/ ){
	        print "&nbsp;&nbsp;", helpLink(-2, "?", "sensorGraphicsLD", 1), "<br>";
	     }else{
		print "&nbsp;&nbsp;", helpLink(-2, "?", "sensorGraphics", 1), "<br>";
	     }

	     # If there is nothing to plot, avoid "broken image" icon
	     if( $dataManager->{"results"}->{"gnuplotHasPlots"} ){
		print '<FONT class="small">', "&nbsp;&nbsp;&nbsp;&nbsp; (Zur&uuml;ck zur ", 
	               a({href=>"$startLink"},"&Uuml;bersicht"),
         	       " aller Sensoren.)<BR>\n", '</FONT>';
	        print "<br>";

    		# Assemble image URL for this sensor
		$imgUrl=$sensorData->getSensImgUrl($refSensor);     
		print img {src=>"$imgUrl"};
	     }else{
	   	print "<br>&mdash; <FONT size=-2>Keine Daten</FONT> &mdash;\n";
	     }
	   
	     # Print Link to access the raw text data
  	     $tmp=${$refSensor}{"sensType"} . ${$refSensor}{"typeSerial"};
	     $url=addUrlParm($scriptUrl, "pl=$tmp",
		"sd=${startDate}_$startTime;ed=${endDate}_$endTime", "$mmaUrlParm",
		"sm=$scaleMode", "sf=$scaleFactor", "st=$sampleTime",
		"rst=$rainSumMode");
	     $textUrl=$url; $textUrl=~s/pl=/tp=/;
	     print "<br>";
	     print a({-class=>"tiny",href=>$textUrl, target=>"_blank"}, "Als Tabelle ....");

	     
	     
	     if( ${$refSensor}{"displayMMA"} ){
		print h4("Maximal/Minimal-Werte vom " .
	               "$locMmaStartDay.$locMmaStartMon.$locMmaStartYear - " .
		       "$locMmaEndDay.$locMmaEndMon.$locMmaEndYear" );


		# Now create a list with the mma-names to be displayed
		# eg temp0, hum0
		undef @tmp;
		$tmpCnt=0;
		foreach $i (@{${$refSensor}{"mmaNames"}}){
		    $tmp[$tmpCnt++]="$i$plotsTypeSerial";
		}
		$tmp=${$refSensor}{"mmaHeight"};
	     }	
	}# end if plotsSelected 
	
	# Now print the MMA values 
	if( ${$refSensor}{"displayMMA"} ){
	   $tmp=${$refSensor}{"mmaHeight"};
           printMmaValues($dataManager, $refSensor, 
	      		     'width="100%"', 		# width
			     $tmp!=0?"height=$tmp":"", 	# height
			     $plotsSelected?2:-2, 	# Fontsize
			     $plotsSelected,		# Print virtual sensors 
			     $theSampleTime	        #       MMA or not
			   );
	}			
	
      } # end if doPlot
      
      # Keep the MMA values stored in $dataManager for the display below
      undef $dataManager;
      # Get next 
      $refSensor=$sensorData->getNextSensor("graphics");
   } # end while	
	
   $gfxSensTab->endTable() if( ! $plotsSelected ); 

   # print errors/warning that might have been collected in plotData();
   if( length($allErrMsg) ){
 	   print '<hr><p><span style="font-weight:bold">Warnung:</span><br> ';
	   print $allErrMsg, "\n";
 	   print "<hr>";
   }
}


#
# Display the Textgrafixs overview showing all sensors or the more
# detailed grafic of only one sensor
#
sub showTextPanel{
   my($dbh, $sensorData, 
      $plotsSelected, $plots, $plotsTypeSerial,
      $rainSumMode, $sampleTime, 
      $startDate, $startTime, $endDate, $endTime,
      $mmaStartDate, $mmaStartTime, $mmaEndDate, $mmaEndTime,
      $locMmaStartDay, $locMmaStartMon, $locMmaStartYear,
      $locMmaEndDay, $locMmaEndMon, $locMmaEndYear, 
      $xScaleFactor, $yScaleFactor, 
      $url, $startLink,
      $refDoPlotMma,
      $mmaUrlParm, $scaleMode, $scaleFactor)=@_;
      
   my($i, $j, $k, $tmp, $tmpCnt,
      @tmp, $modeUrl,
      $refSensor, $typeSerial, $firstRun,
      $seenErrCodes, $allErrMsg, $errCode, $errMsg, 
      $theSampleTime,
      $imgUrl, $dataManager );
      
   $seenErrCodes="";
   $allErrMsg="";
   $refSensor=$sensorData->getFirstSensor("graphics");
   
   $firstRun=1; # needed below
 
   # Now iterate over the sensors defined and marked plottable
   while( defined(%{$refSensor}) ){
      $typeSerial=${$refSensor}{"typeSerial"};

      # Do plot only if ${$refSensor}{"doPlot"} or if 
      # either $plotsSelected is false or 
      # it is true and the sensor in question has actually been selected to be plotted 
      # by the user which can be seen in the list of sensorTypes in $plots
      if( ${$refSensor}{"doPlot"} && (
            !$plotsSelected || ( $plots =~ /${$refSensor}{"sensType"}/ 
	 			 && $typeSerial == $plotsTypeSerial )) ){

	 $theSampleTime=$sampleTime;
	 if( (${$refSensor}{"sensType"} =~/RA/ && $sampleTime !~ /^0/o 
	     && $rainSumMode) || 
	     (${$refSensor}{"sensType"} =~/LD/ && $sampleTime !~ /^0/o )){
      	   # For rain sensor user may want to see summary values instead of 
	   # average values (default) if $sampleTime is day, week, month ....
	   # This is marked by appending a capital S to the value of $sampleTime
	   $theSampleTime=~s/,/S,/;
	 }

	 # Create a new Data Object for one sensor.
	 $dataManager=dataManager->new($dbh, $sensorData, $refSensor, 
	 				\%dstRange);

	 # Set options needed for the work the dataManger Class does
	 $dataManager->setOptions( {"sampleTime"=>"$theSampleTime",
	 			   "startDate" => "$startDate",
	 			   "startTime" => "$startTime",
	 			   "endDate" => "$endDate",
	 			   "endTime" => "$endTime",
				   "mmaStartDate"=>$mmaStartDate,
				   "mmaStartTime"=>$mmaStartTime,
				   "mmaEndDate"  =>$mmaEndDate,
				   "mmaEndTime"  =>$mmaEndTime,
				   "xscale"  =>  "$xscale",  # scaling for graphics
				   "yscale"  =>  "$yscale",
				   "dataFilename" => "/tmp/wetterData_$$.txt",
				   "gnuplotFilename" => "/tmp/wetterGnuplot_$$.txt",
				   "bgColorAverage" =>  $bgColorAverage ,
				   "bgColorNormal"  => $bgColorNormal,
				   "gnuplotBinary" => "$gnuplot",
				   "refDoPlotMma"  => $refDoPlotMma});

	# At the moment we ty the plotting of MMA values of virtual sensors 
	# to the settings of the real sensor. So if MMA values are plotted for
	# a real sensor they also will be plotted for its virtual sensors
	# An exception to this rule is if the mma daterange is different
	# from the datrange of the graphics display. In this case we cannot display
	# virtsens MMA data, since we only have them for the daterange of the display
	$dataManager->checkVirtMma($refSensor);
				   
        # Do all needed preparation work. This function also gets MMA values
	# The are stored in 
	# $dataManager->{"results"}->{<sensid>}->{"mma"}->{<mmaDBColName>}->
	#  ...->{"minValue"},  ...->{"minDate"}, ...->{"minTime"}
	#  ...->{"maxValue"},  ...->{"maxDate"}, ...->{"maxTime"}
	#  ...->{"avgValue"}
	$dataManager->prepareSensData(0);  

	# construct URL to get the sensor beeing displayed
	$tmp=${$refSensor}{"sensType"} . ${$refSensor}{"typeSerial"};
	$url=addUrlParm($scriptUrl, "pl=$tmp",
	  "sd=${startDate}_$startTime;ed=${endDate}_$endTime", "$mmaUrlParm",
	  "sm=$scaleMode", "sf=$scaleFactor", "st=$sampleTime",
	  "rst=$rainSumMode");

	# Create Link to graphical display
	$modeUrl=$url; $modeUrl=~s/tp=/pl=/;
	print a({-class=>"small",href=>$modeUrl, target=>"_blank"}, "Zur Graphik");

	print '<FONT class="small">', ", &nbsp;&nbsp; zur&uuml;ck zur ", 
	       a({href=>"$startLink"},"&Uuml;bersicht"),
               " aller Sensoren.<BR>\&nbsp;<BR>\n", '</FONT>';
        print '<FONT class="navTabCurHead">', "Tabellarische Datenbersicht:", '</FONT>';
	helpLink(-1, "   ?", "tableView", 0);
	print "<br>\&nbsp;<br>\n";
	
	# print tabular  output
	$errCode=$dataManager->runTextplot($sampleTime);
	# Unlink temp files and SQL result data (MMA data are left untouched)
	# This is done to save memory since the complete results of one
	# sql query are kept in main memory
	$dataManager->unlinkTmpData();  
	
	 
	# If there was an error/warning that should be displayed to the user
	# Note this message. To avoid double warning of the same type 
	# we uses an errorType that has a n associated message.
	# Each errcode that was found is noted in $seenErrCodes so a second error
	# of the same type can be skipped.
	if( $errCode ){
	    if( $seenErrCodes !~ /$errCode/i ){
		    $allErrMsg.="<br>" if( length($allErrMsg) );
		    $seenErrCodes.="$errCode ";  # Note this code as "seen"
		    $allErrMsg.="$main::errMsg";
	    }
	}	    
      
	

	if( ${$refSensor}{"displayMMA"} ){
	   print h4("Maximal/Minimal-Werte vom " .
	          "$locMmaStartDay.$locMmaStartMon.$locMmaStartYear - " .
		  "$locMmaEndDay.$locMmaEndMon.$locMmaEndYear" );

	   # Now create a list with the mma-names to be displayed
	   # eg temp0, hum0
	   undef @tmp;
	   $tmpCnt=0;
	   foreach $i (@{${$refSensor}{"mmaNames"}}){
	       $tmp[$tmpCnt++]="$i$plotsTypeSerial";
	   }
	   $tmp=${$refSensor}{"mmaHeight"};
	}	


	# Now print the MMA values 
	if( ${$refSensor}{"displayMMA"} ){
	   $tmp=${$refSensor}{"mmaHeight"};
           printMmaValues($dataManager, $refSensor, 
	      		     'width="100%"', 		# width
			     $tmp!=0?"height=$tmp":"", 	# height
			     $plotsSelected?2:-2, 	# Fontsize
			     $plotsSelected,		# Print virtual sensors 
			     $theSampleTime			# MMA or not
			   );
	}			
	
      } # end if doPlot
      
      # Keep the MMA values stored in $dataManager for the display below
      undef $dataManager;
      # Get next 
      $refSensor=$sensorData->getNextSensor("graphics");
   } # end while	
	

   # print errors/warning that might have been collected in plotData();
   if( length($allErrMsg) ){
 	   print '<hr><p><span style="font-weight:bold">Warnung:</span><br> ';
	   print $allErrMsg, "\n";
 	   print "<hr>";
   }
}


# ============================================================
# ----- main -------------------------------------------------
# ============================================================
# Check if impPath is writable for the script (and gnuplot)
imgpathWriteTest();

# If the url contains the parameter "days=1" then display only data of
# the given number of days (here 1).
$days=url_param('days');
if( $days > 0 ){
	$initialDisplayDays=$days;
}

$hours=url_param('hours');
if( $hours > 0 ){
	$initialDisplayHours=$hours;
}else{
	$initialDisplayHours=0;
}

# defaults for scaling
$defScaleMode="x";
$defScaleFactor="1";
$scaleMode=$defScaleMode;
$scaleFactor=$defScaleFactor;
$defSampleTime="0";   
$sampleTime=$defSampleTime;
$defSampleDataType="Avg";
$sampleDataType=$defSampleDataType;
$rainSumMode=1;	# For rain sensor we plot average not sum value if
		# $sampleTime != "0"
$defaultStartTime="00:00:00";   # Given in local time
$defaultEndTime="23:59:59";	# Given in local time, if changed look at
				# #**# below! Needs also to be changed then.

# Get todays date in local time
($tYear, $tMonth, $tDay, $tHour, $tMin, $tSec)=Today_and_Now(0); 
$today=sprintf("%4d-%02d-%02d", $tYear,$tMonth,$tDay);

if( $initialDisplayHours == 0 ){
	# Normal End time is $defaultEndtime (in GMT) 
	# this usually is the end of the current day.
	($endHour, $endMin, $endSec)=split(/:/o, $defaultEndTime);
	($endYear, $endMon, $endDay)=split(/-/o, $today); 
	# used below in Add_Delta_DHMS call
	$dh=0;
}else{
	# if $initialDisplayHours is != 0 Endtime is "Now"
	# And we want to display only the last <n> hours
	$endHour=$tHour; 
	$endMin=$tMin; 
	$endSec=$tSec;
        $endYear=$tYear;
        $endMon=$tMonth;
        $endDay=$tDay;
	# used below in Add_Delta_DHMS call
	$dh=$initialDisplayHours;
	# If the user specified a hours value we assume that days==0
	$initialDisplayDays=0;
}

# Format endDate and time string and initialize with start data
$endDate=sprintf("%4d-%02d-%02d", $endYear, $endMon, $endDay );
$endTime=sprintf("%02d:%02d:%02d", $endHour, $endMin, $endSec);

# Now take startDate and time back some $initialDisplayDays
# and add one second because the enddate is assumes to be something like 
# 23:59:59. If we subtract one 1 we again get 23:59:39 a day earlier as 
# a  start date. But actually we want 00:00:00 as a startdate so we have
# to add one second.
# So if initialDipslayDays is 1 we excatly see
# one day from 00:00:00 -> 23:59:00
# 
($startYear, $startMon, $startDay, $startHour, $startMin, $startSec)=
		Add_Delta_DHMS($endYear, $endMon, $endDay, 
		$endHour, $endMin, $endSec,
		-($initialDisplayDays), -$dh , 0, 1); #**# 

# Format new date so that its a correct written date
$startDate=sprintf("%4d-%02d-%02d",$startYear, $startMon, $startDay );
$startTime=sprintf("%02d:%02d:%02d", $startHour, $startMin, $startSec);

# Convert start end end date/time values into GMT
($startDate, $startTime)=timeConvert($startDate, $startTime, "GMT");	
($endDate, $endTime)=timeConvert($endDate, $endTime, "GMT");	


#warn "+++ $startDate, $startTime -> $endDate, $endTime <br>\n";

# Default *time* values for mma calculation
$mmaStartDate=$startDate;
$mmaStartTime=$startTime;
$mmaEndDate=$endDate;
$mmaEndTime=$endTime;



# Get sensors value from URL
$plots="";
$plots=url_param('pl');   # Flags that a particular sensor is to be plotted
$textPl=url_param('tp');  # Flags that text output of data is wanted for a sensor
if( !length($plots) && !length($textPl) ){
	$plotsSelected=0;
	$plots=$latestSens; # Temp/hum, Pressure, Wind, Light, 
				 # Rain, Pyranometer
	$plotsTypeSerial=0;			 
}else{
        if( length($textPl) ){
		$textPlots=1 ;   # Flag for Text output instead of graphics
		$plots=$textPl;  # Use $plots variable for further processing
	}
	
	$plotsSelected=1;
	$plotsTypeSerial=$plots;
	# Identify type serial id of sensor (eg which of several TH 
	# sensor graphics this is
	$plotsTypeSerial=~s/^[A-Z]+//; # eg. "TH1":  Result is "1"
	$plots=~s/[0-9]+//;
}

# Print Latest data only in overview mode with all sensor values
$printLatestData=1;
$printLatestData=0 if( $plotsSelected);


# Define CCS Stylesheet used for document text font sizes etc.
$docCss=<<EOF;
/* ----------------------------------------------------- */
/*  h1 and h2 not used in wetter.cgi, but set it sane anyway */
h1 {  font-family: Arial, Helvetica, sans-serif; font-size: 16pt }
h2 {  font-family: Arial, Helvetica, sans-serif; font-size: 14pt }

h3 {  font-family: Arial, Helvetica, sans-serif; font-size: 13pt }
h4 {  font-family: Arial, Helvetica, sans-serif; font-size: 12pt }

/* ----------------------------------------------------- */
.latestTable {
	text-align: center; 
	border-collapse:collapse;
	border-left: medium ridge grey;
	border-right: medium ridge grey;
	border-top: medium ridge grey;
	border-bottom: medium ridge grey;
	background-color: #f1f1fa;
	padding: 10px;
}
.latestTable td{
	text-align: center;
	border-left: thin solid black;
	border-right: thin solid black;
	border-top: thin solid black;
	border-bottom: thin solid black;
	padding-left: 15px;
	padding-right: 15px;
	padding-top: 3px;
	padding-bottom: 3px;
}
/* Headline of latest Tab section */
.latestTabHead {
   font-family: Arial, Helvetica, sans-serif; font-size: 12pt;
   font-weight: bold; float:left;
}
.latestTabHoursAgo {
   font-family: Arial, Helvetica, sans-serif; font-size: 9pt;
   float:left;color:rgb(200,100,100)
}
.latestTabHeader {
   font-family: Arial, Helvetica, sans-serif; font-size: 11pt
}
.latestRowHeader {
   font-family: Arial, Helvetica, sans-serif; font-size: 11pt; 
   font-style: oblique; font-weight: bold
}
.latestTabText {
   font-family: Arial, Helvetica, sans-serif; font-size: 11pt
}

/* ----------------------------------------------------- */
/* Table navigation */
/*  Headers for navigation panel */ 
.navTabHead {
   font-family: Arial, Helvetica, sans-serif; font-size: 12pt;
   font-weight: bold; padding-bottom:5px;
}
/*  Header for actions user may take, z.B. "Darstellungszeitraum" */ 
.navTabActHead {
   font-family: Arial, Helvetica, sans-serif; font-size: 11pt;
   font-weight: bold; 
}
/*  Header for current settings */ 
.navTabCurHead {
   font-family: Arial, Helvetica, sans-serif; font-size: 11pt;
   font-weight: bold;
}
/* Regular Text including form text fields in the navtab */
.navTabCurText {
   font-family: Arial, Helvetica, sans-serif; font-size: 10pt
}
/* Text in links like "Ein Tag" etc */
.navTabLink {
   font-family: Arial, Helvetica, sans-serif; font-size: 9pt
}
/* Text in links like "Ein Tag" etc */
.grfxTitle {
   font-family: Arial, Helvetica, sans-serif; font-size: 13pt;
   font-weight: bold
}

/* ----------------------------------------------------- */
/* The min/max/average display below each graphics	 */
.mmaTabHeader {
   font-family: Arial, Helvetica, sans-serif; font-size: 8pt;
   background-color: #e1e1ea;
}
/* Style for first element in each row (sensor name/type) */
.mmaTabRowHeader {
   font-family: Arial, Helvetica, sans-serif; font-size: 8pt;
   background-color: #f1f1fa;
}
/* Style element for text in each row except for the first colum */
.mmaTabText {
   font-family: Arial, Helvetica, sans-serif; font-size: 8pt;
   background-color: #f1f1fa;
}
/* Style for data elements in each virtual sensor row of data */
.mmaVirtTabText {
   font-family: Arial, Helvetica, sans-serif; font-size: 8pt; color: rgb(75,75,75);
   background-color: #f1f1fa
}
/* Style for first element in each virtual sensor row (sensor name/type) */
.mmaVirtTabRowHeader {
   font-family: Arial, Helvetica, sans-serif; font-size: 8pt; color: rgb(75,75,75);
   background-color: #f1f1fa
}
/* The table header line in textual output for Sensordata */
.sensTextTabHeader {
   font-family: Arial, Helvetica, sans-serif; font-size: 11pt;
}
/* The data lines for  textual output for Sensordata */
.sensTextTab {
   font-family: Arial, Helvetica, sans-serif; font-size: 10pt;
}
/* The data lines for  textual output for virtual Sensordata */
.sensVirtTextTab {
   font-family: Arial, Helvetica, sans-serif; font-size: 10pt; color: rgb(75,75,75);
}
/* The data lines for  textual output for extra columns in output */
/* like windspeed in a TH sensor output     */
.sensExtraTextTab {
   font-family: Arial, Helvetica, sans-serif; font-size: 10pt; color: rgb(150,150,150);
}
/* The minimum data for  textual output of Sensordata */
.sensTextTabMin {
   font-family: Arial, Helvetica, sans-serif; font-size: 10pt; background-color: green;
}
/* The maximum data for  textual output of Sensordata */
.sensTextTabMax {
   font-family: Arial, Helvetica, sans-serif; font-size: 10pt; background-color: red;
}
/* The row header column in textual output for Sensordata */
.sensRowHeaderTextTab {
   font-family: Arial, Helvetica, sans-serif; font-size: 10pt; font-weight: bold;
}
/* The main headers (sensornames) in the statistical table */
.statTabHeader1 {
  font-family: Arial, Helvetica, sans-serif; font-size: 10pt; font-weight: bold; 
  background-color: none;
}
/* The main headers (value headers) in the statistical table */
.statTabHeader2 {
   font-family: Arial, Helvetica, sans-serif; font-size: 9pt; font-style: normal;  
   font-weight: normal; background-color: none;
}
/* The date value in the statistical table */
.statTabValue1 {
   font-family: Arial, Helvetica, sans-serif; font-size: 10pt; background-color: none;
}
/* The format for the day, week, month links in statistical table */
.linkTabValue {
   font-family: Arial, Helvetica, sans-serif; font-size: 8pt; background-color: none;
}
/* The date value in the statistical table */
.statTabValue1lastRow {
   font-family: Arial, Helvetica, sans-serif; font-size: 9pt; font-weight: bold; 
   background-color: rgb(220,225,245) ;
}
/* The sensor values in the statistical table */
.statTabValue2 {
   font-family: Arial-Narrow, Helvetica, sans-serif; color: rgb(0,0,0); font-size: 9pt; 
   font-style: normal; font-weight: normal; background-color: rgb(210, 215, 245);*/
   
}
/* The Background of the whole statistics table */
.statTabBg {
   background-color: rgb(230,235,255);
}

/* ----------------------------------------------------- */
/* The help text					*/
.help {
   font-family: Arial, Helvetica; sans-serif; font-size: 11pt;
}
/* ----------------------------------------------------- */
/* Some medium sized text				 */
.medium {
   font-family: Arial, Helvetica; sans-serif; font-size: 9pt;
}
/* ----------------------------------------------------- */
/* Some small sized text				 */
.small {
   font-family: Arial, Helvetica; sans-serif; font-size: 8pt;
}
/* ----------------------------------------------------- */
/* Some very small sized text				 */
.tiny {
   font-family: Arial, Helvetica; sans-serif; font-size: 6pt;
}
/* Some error text				 */
.error {
   font-family: Arial, Helvetica; sans-serif; font-size: 10pt; color: grey;
}
div#qTip {
  padding: 3px;
  border: 1px solid #666;  border-right-width: 2px;  border-bottom-width: 2px;
  display: none;
  background: lightyellow;  color: #000;
  font: 10pt  Arial, Helvetica, sans-serif;
  text-align: left;  position: absolute;
  z-index: 1000;
}
EOF
;

#
# Code to have tooltips (supporting multiline) that work with all browsers
#
$toolTipCode=<<EOF
//////////////////////////////////////////////////////////////////
// qTip - CSS Tool Tips - by Craig Erskine
// http://qrayg.com | http://solardreamstudios.com
//
// Inspired by code from Travis Beckham
// http://www.squidfingers.com | http://www.podlob.com
//////////////////////////////////////////////////////////////////

var qTipTag = "td"; //Which tag do you want to qTip-ize? Keep it lowercase!//
var qTipX = -40; //This is qTip's X offset//
var qTipY = 25; //This is qTip's Y offset//

//There's No need to edit anything below this line//
tooltip = {
  name : "qTip",
  offsetX : qTipX,
  offsetY : qTipY,
  tip : null
}

tooltip.init = function () {
	var tipNameSpaceURI = "http://www.w3.org/1999/xhtml";
	if(!tipContainerID){ var tipContainerID = "qTip";}
	var tipContainer = document.getElementById(tipContainerID);

	if(!tipContainer) {
	  tipContainer = document.createElementNS ? document.createElementNS(tipNameSpaceURI, "div") : document.createElement("div");
		tipContainer.setAttribute("id", tipContainerID);
	  document.getElementsByTagName("body").item(0).appendChild(tipContainer);
	}

	if (!document.getElementById) return;
	this.tip = document.getElementById (this.name);
	if (this.tip) document.onmousemove = function (evt) {tooltip.move (evt)};

	var a, sTitle, newTitle;
	var anchors = document.getElementsByTagName (qTipTag);
        var regEx = new RegExp ('[\\n]', 'g') ;

	for (var i = 0; i < anchors.length; i ++) {
	   a = anchors[i];
	   sTitle = a.getAttribute("title");
	   if(sTitle) {
	      // Replace newline by <br>,  R.K.
	      newTitle=sTitle.replace(regEx, "<br>");
	      a.setAttribute("tiptitle", newTitle);
	      a.removeAttribute("title");
	      a.onmouseover = function() {tooltip.show(this.getAttribute('tiptitle'))};
	      a.onmouseout = function() {tooltip.hide()};
	   }
	}
}

tooltip.move = function (evt) {
	var x=0, y=0;
	if (document.all) {//IE
		x = (document.documentElement && document.documentElement.scrollLeft) ? document.documentElement.scrollLeft : document.body.scrollLeft;
		y = (document.documentElement && document.documentElement.scrollTop) ? document.documentElement.scrollTop : document.body.scrollTop;
		x += window.event.clientX;
		y += window.event.clientY;
		
	} else {//Good Browsers
		x = evt.pageX;
		y = evt.pageY;
	}
	this.tip.style.left = (x + this.offsetX) + "px";
	this.tip.style.top = (y + this.offsetY) + "px";
}

tooltip.show = function (text) {
	if (!this.tip) return;
	this.tip.innerHTML = text;
	this.tip.style.display = "block";
}

tooltip.hide = function () {
	if (!this.tip) return;
	this.tip.innerHTML = "";
	this.tip.style.display = "none";
}

window.onload = function () {
	tooltip.init ();
}

EOF
;



#
# Decide from where to take the cascading style sheets
if( !length($externalCssUrl) ){
	$cssTag="-code"; $cssValue="$docCss";
}else{
	$cssTag="-src"; $cssValue="$externalCssUrl";
}	
# print html stuff
# start htmlpage for all cases
print header(-type =>'text/html',  -expires =>'+1m'),
      start_html(-title  =>$pageTitle,
		-encoding =>'UTF-8',
		-style   =>{ $cssTag => $cssValue },
		-script  => $toolTipCode,		
                -author =>$pageAuthors,
                -dtd => '-//W3C//DTD HTML 4.01 Transitional//EN',
                -base   =>'true',
                -meta   =>{'keywords'   => $pageMetaKeywords,
                                'description'=> $pageDescription},
                -BGCOLOR=>$pageBackgroundColor, -TEXT   => $pageTextColor, -LINK =>$pageLinkColor,
		-background=>$pageBackgroundPicture,
                -VLINK  =>$pageVisitedLinkColor, -ALINK  =>'black'), "\n";



# Marks that we have started the http header. Used in doDie(), doWarn()
$preHtmlDocInit=0;


# Script was called to display help ?
# sub printHelp does not return.
$help=url_param('help');
printHelp($help) if( length($help) );


$dbh=connectDb();			# Connect with Database
if( !$dbh ){
	print "Keine Verbindung zum Datenbank-Server. Abbruch";
	print end_html, "\n";
}


# Find out which version the server has (SELECT VERSION(); )
$MysqlVersion=getMysqlVersion($dbh);
if( $MysqlVersion >= 5.0 ){
    # Use subqueries for Min/Max/Avgh determination
    # if this varaiable has not already been set elsewhere
    $useSqlSubQueries=1 if( ! defined($useSqlSubQueries) );   
}else{
    $useSqlSubQueries=0 if( ! defined($useSqlSubQueries) );
}


# Get the date of first Dataset.
@first=getFirstTimeDateSet($dbh, $sensorData);

$firstDate="$first[0]-$first[1]-$first[2]";
$firstYear=$first[0];
$firstMon=$first[1];
$firstDay=$first[2];

# Get date and time of last existant dataset
# needed below
@now=getLastTimeDateSet($dbh, $sensorData);

# Extract sensor Names from database and enter values into sensor configuration data
$sensorData->getSensorNames($dbh);

# Get date values from HTML form or from url
# If there is a date received from the form parameters this as well as
# other parameters from the form will be
# taken. Else we look for a date in the url, so we can evaluate links
# containing a date entry (sd=2003-06-25;ed=xxxxxxx)
$selsDay=param('startDay');
if( length($selsDay) ){
	$selsMon=param('startMonth');
	$selsYear=param('startYear');
	$seleDay=param('endDay');
	$seleMon=param('endMonth');
	$seleYear=param('endYear');
	
	# Scaling for images
	$scaleMode=param('scaling');
	$scaleMode=$defScaleMode if( $scaleMode ne "x" && $scaleMode ne "y" 
					&& $scaleMode ne "x+y" );

	$scaleFactor=param('scaleFactor');
	$scaleFactor=$defScaleFactor if( $scaleFactor !~ /[0-9.]+/o );
	
	# sample time average data display
	# we have to take this val from the url cause there is no
	# form element to define it but only a link
	# $sampletime encodes the time as well as the value to display
	# (Avg, Min, Max). It looks like eg "d,Min"
	$sampleTimeBase=url_param('st');
	$sampleDataType=$sampleTimeBase;
	$sampleDataType=~s/[0a-zA-Z],//o; # eg $sampleTime=="d,Avg"
	$sampleTimeBase=~s/,.*$//o;	
	$sampleTimeUser=url_param('stuser');
	$sampleTimeUser=0 if( ! length($sampleTimeUser));
	
	# Parameter if rain data is to be displayed as average or a summary
	# if $sampleTime != "0"
	#$rainSumMode=param('rainSum');
	$rainSumMode=0 if( param('rainSum') eq "1" );
	
	# Construct new start an end date
	$startDate="$selsYear-$selsMon-$selsDay";
	$startTime=$defaultStartTime;
	($startDate, $startTime)=timeConvert($startDate, $startTime, "GMT");	

		
	$endDate="$seleYear-$seleMon-$seleDay";
	$endTime=$defaultEndTime;
	($endDate, $endTime)=timeConvert($endDate, $endTime, "GMT");
}else{
  	$sDate=url_param('sd');
  	$eDate=url_param('ed');

	if(  length($sDate) && length($eDate) ){
		($startDate,$startTime)=split(/_/o, $sDate);
		($endDate,$endTime)=split(/_/o, $eDate);
		# Take care that date has correct format 
		($startYear, $startMon, $startDay)=split(/-/o, $startDate);
		($startHour, $startMin, $startSec)=split(/:/o, $startTime);
		($endYear, $endMon, $endDay)=split(/-/o, $endDate);
		($endHour, $endMin, $endSec)=split(/:/o, $endTime);
	        $startDate=sprintf("%04d-%02d-%02d", $startYear,$startMon, $startDay);
                $startTime=sprintf("%02d:%02d:%02d", $startHour,$startMin, $startSec);
                $endDate=sprintf("%04d-%02d-%02d", $endYear,$endMon, $endDay);
                $endTime=sprintf("%02d:%02d:%02d", $endHour,$endMin, $endSec);		
	}
	# Scaling for images
	$scaleMode=url_param('sm');
	$scaleFactor=url_param('sf');
	$scaleFactor=$defScaleFactor if( $scaleFactor !~ /[0-9.]+/o );
	$scaleMode=$defScaleMode if( $scaleMode ne "x" && $scaleMode ne "y" 
					&& $scaleMode ne "x+y" );
	# sample time average data display
	# $sampletime encodes the time as well as the value to display
	# (Avg, Min, Max). It looks like eg "d,Min"
	# The value to be displayed is stored in $sampleDataType
	$sampleTimeBase=url_param('st');
	$sampleDataType=$sampleTimeBase;
	$sampleDataType=~s/[0a-zA-Z],//o; # eg $sampleTime=="d,Avg"
	$sampleTimeBase=~s/,.*$//o;
	$sampleTimeUser=url_param('stuser'); 
	$sampleTimeUser=0 if( ! length($sampleTimeUser));
	# Parameter if rain data is to be displayed as average or a summary
	# if $sampleTime != "0"
	$rainSumMode=url_param('rst') if( length(url_param('rst')));
	$rainSumMode=0 if( $rainSumMode ne "1" );	
}


# Determine scaling factors
$xScaleFactor=1;
$yScaleFactor=1;
if( $scaleMode =~ /x\+y/ ){
	$xScaleFactor=$scaleFactor;
	$yScaleFactor=$scaleFactor;
}elsif( $scaleMode =~ /^x/ ){
	$xScaleFactor=$scaleFactor;
}elsif( $scaleMode =~ /^y/ ){
	$yScaleFactor=$scaleFactor;
}	


# Check sampleTimeBase Mode. May be "h","d", "w", "m", "y" (hour,day, week, moth, year)
# or "0" (off==use all data available, which is the default mode)
# $sampletime encodes the time as well as the value to display
# (Avg, Min, Max). It looks like eg "d,Min"
# Here we add the value ($sampleDataType) to the time period (d,w,m,y) contained in 
# $sampleTime already
if( $sampleTimeBase !~/^[hdwmy0]/io ){
	$sampleTimeBase=$defSampleTime;
	$sampleTime="$sampleTimeBase,$defSampleDataType";
	$sampleDataType="$defSampleDataType";
}else{
        if( length($sampleDataType) ){
		$sampleTime="$sampleTimeBase,$sampleDataType";
	}
}


# Correct single variables to corrected startDate, endDate
($startYear, $startMon, $startDay)=split(/-/o, $startDate);
($startHour, $startMin, $startSec)=split(/:/o, $startTime);
($endYear, $endMon, $endDay)=split(/-/o, $endDate);
($endHour, $endMin, $endSec)=split(/:/o, $endTime);


# Check if statisticsMode is active
$statisticsMode=url_param('statMode');
if( length($statisticsMode) && $statisticsMode =~ /1/o ){
   $statisticsMode="1";
   $delta=Delta_Days($startYear,$startMon,$startDay,
                              $endYear,$endMon,$endDay);
    # Set default sampleTime according to the date range selected
   if( ! $sampleTimeUser ){
        if( $delta <=7 ){ $sampleTime=~s/^[0a-zA-Z]/d/o; }
        if( $delta > 7 && $delta <28 ){ $sampleTime=~s/^[0a-zA-Z]/w/o;}
        if( $delta >=28 && $delta <=365){ $sampleTime=~s/^[0a-zA-Z]/m/o;}
        if( $delta > 365 ){ $sampleTime=~s/^[0a-zA-Z]/y/o;}
   }else{
       # The has preselected a sampleTime but "h"
       # is not allowed for statistics mode
       if( $sampleTime=~/^[0h].*/ ){
          $sampleTime=~s/^[0a-zA-Z]/w/o;
       }
   }
}else{
   $statisticsMode=0;
}

#
# Check dates
$dateIsValid=1;
# ***
($startDate, $startTime, $endDate, $endTime, $dateIsValid, $errStr)=
	checkDate($firstYear, $firstMon, $firstDay, 
	          $startDate, $startTime, $endDate, $endTime, 
		  $sampleTime, \@now, \@first, $statisticsMode);

# Doesn't need to be done if output is in GMT. Probably save some time...
if (!$timeIsGMT) {
   # Now we calculate for each year from start to end the 
   # time range for DST and store this in a global hash. It is needed in 
   # buildSqlCommand() since MYSQL does not yet support  DST conversion
   # We have to start at $startYear -1 since the user supplied startYear may be 
   # corrected to the year befor if the user select year average. The the 
   # startdate is eg for 2004 corrected to 01.01.2004 and then converted 
   # into gmt which is 31.12.2003 23:00:00
   for($i=$startYear-1; $i<=$endYear; $i++){
      ($dstStart,$dstEnd, $deltaIsDst, $deltaNoDst)=getDSTStartEnd($i);
      $dstRange{$i}->{"dstStart"}=$dstStart;
      $dstRange{$i}->{"dstEnd"}=$dstEnd;
      $dstRange{$i}->{"deltaIsDst"}=$deltaIsDst;
      $dstRange{$i}->{"deltaNoDst"}=$deltaNoDst;
   }

   # Get dst info for current year if not already there
   $tmp=(Today_and_Now(1))[0]; # year of today
   if( ! defined($dstRange{$tmp}) ){
      ($dstStart,$dstEnd, $deltaIsDst, $deltaNoDst)=getDSTStartEnd($tmp);
      $dstRange{$tmp}->{"dstStart"}=$dstStart;
      $dstRange{$tmp}->{"dstEnd"}=$dstEnd;
      $dstRange{$tmp}->{"deltaIsDst"}=$deltaIsDst;
      $dstRange{$tmp}->{"deltaNoDst"}=$deltaNoDst;
   }else{
      # Global variables to hold dst info for current year needed eg by timeConvert
      $dstStart=$dstRange{$tmp}->{"dstStart"};
      $dstEnd=$dstRange{$tmp}->{"dstEnd"};
      $deltaIsDst=$dstRange{$tmp}->{"deltaIsDst"};
      $deltaNoDst=$dstRange{$tmp}->{"deltaNoDst"};
   }
}
#print "$startDate _ $startTime, $endDate _ $endTime<br>\n";


# Check how many days we will display and decide if we 
# display hour based average values instead of original
# data values to minimize the processing time
$delta=Delta_Days($startYear,$startMon,$startDay,
                              $endYear,$endMon,$endDay);
#
if( !$statisticsMode && $doAutoBaseData && (! $sampleTimeUser)  && ($delta >= $doAutoBaseData) ){
        if( $delta >= 365 ){
	  $sampleDataType=$sampleTimeBase=$sampleTime="d,$sampleDataType";
	}else{ 
	  $sampleDataType=$sampleTimeBase=$sampleTime="h,$sampleDataType";
	}
	$sampleDataType=~s/[0a-zA-Z],//o;
	$sampleTimeBase=~s/,.*$//o;
}


# Start a table column, that surrounds the whole page, so the single
# Elements will have the same width
$pageTab=simpleTable->new({"cols"=>"1", "auto"=>"0"},  
    'border="0" cellspacing="0" cellpadding="0"', "");
$pageTab->startTable(1,0);    


#
# Define and write the latest data overview to the webpage if wanted
#
showLatestDataPanel($plots, $sensorData, $pageTab, \@now) 
                                       if( $printLatestData );

# get MMA date parameters from URL
($mmaStartDate, $mmaStartTime, 
 $mmaEndDate, $mmaEndTime,
 $locMmaStartYear, $locMmaStartMon, $locMmaStartDay,
 $locMmaStartHour, $locMmaStartMin, $locMmaStartSec,
 $locMmaEndYear, $locMmaEndMon, $locMmaEndDay, 
 $locMmaEndHour, $locMmaEndMin, $locMmaEndSec,
 $mmaUrlParm)  
               =  calcMmaDates($startDate, $endDate, $startTime, $endTime, 
      			       $defaultStartTime, $defaultEndTime, \%doPlotMma);

#
# Now create and write the navigation panel into the webpage
#
if( $navPanelPos eq "top" ){
   showNavigationPanel(
		 $startDate, $endDate, $startTime, $endTime, 
      		 $defaultStartTime, $defaultEndTime, 
		 $mmaStartDate, $mmaStartTime, 
		 $mmaEndDate, $mmaEndTime,
		 $locMmaStartYear, $locMmaStartMon, $locMmaStartDay,
		 $locMmaStartHour, $locMmaStartMin, $locMmaStartSec,
		 $locMmaEndYear, $locMmaEndMon, $locMmaEndDay, 
		 $locMmaEndHour, $locMmaEndMin, $locMmaEndSec,
		 $mmaUrlParm,
		 $sampleTime, $sampleTimeBase, $sampleTimeUser,
		 $defSampleTime,
		 $defSampleDataType, $sampleDataType,
      		 $plots, $plotsSelected, $textPlots, 
		 $rainSumMode, $scaleMode, $defScaleMode,
      		 $defScaleFactor, $scaleFactor, 
		 \%doPlotMma, $plotsTypeSerial, \@now, \@first, 
		 $statisticsMode             );
}		 

# Link to reach the overview page from any detailed plot page
$startLink=addUrlParm($url, "sd=$startDate;ed=$endDate");


if( !$dateIsValid ){
	print "<hr>", 
	      '<p class="error">', 
	      "<b>Der gew&uuml;nschte Datumsbereich war nicht " .
	      "g&uuml;ltig/verf&uuml;gbar und wurde korrigiert....<br></b>",
	      $errStr, 
	      "<hr>\n";
}


# Check if we should display the statistics dialog   
if( $statisticsMode ){
   # -----------------------------------------------------
   #print join(", ", keys(%$sensorData)), "\n";
   # Now get and siplay statistical data
   $statistics=statistics->new($sensorData, $startDate, $startTime, 
                            $endDate, $endTime,  $sampleTime, $dbh,  
			  # dst infos   # date of latest dataset            
			    \%dstRange,  \@now, \@first);
   $statistics->getPrintStats();   

}elsif( $textPlots ){
   # -----------------------------------------------------
   # Now set the rest of data to create the textual output
   showTextPanel($dbh, $sensorData, 
	 $plotsSelected, $plots, $plotsTypeSerial,
	 $rainSumMode, $sampleTime, 
	 $startDate, $startTime, $endDate, $endTime,
	 $mmaStartDate, $mmaStartTime, $mmaEndDate, $mmaEndTime,
	 $locMmaStartDay, $locMmaStartMon, $locMmaStartYear,
	 $locMmaEndDay, $locMmaEndMon, $locMmaEndYear, 
	 $xScaleFactor, $yScaleFactor, 
	 $url, $startLink,
	 \%doPlotMma,
	 $mmaUrlParm, $scaleMode, $scaleFactor);
}else{   
   # -----------------------------------------------------
   # Now set the rest of data to create the graphics, and 
   # create plots (images) for all defined sensors
   showGrafixPanel($dbh, $sensorData, 
	 $plotsSelected, $plots, $plotsTypeSerial,
	 $rainSumMode, $sampleTime, $sampleTimeUser, 
	 $startDate, $startTime, $endDate, $endTime,
	 $mmaStartDate, $mmaStartTime, $mmaEndDate, $mmaEndTime,
	 $locMmaStartDay, $locMmaStartMon, $locMmaStartYear,
	 $locMmaEndDay, $locMmaEndMon, $locMmaEndYear, 
	 $xScaleFactor, $yScaleFactor, 
	 $url, $startLink,
	 \%doPlotMma,
	 $mmaUrlParm, $scaleMode, $scaleFactor);
}

#
# Now create and write the navigation panel into the webpage
#
if( $navPanelPos eq "bottom" ){
   print "<hr>\n";
   showNavigationPanel(
		 $startDate, $endDate, $startTime, $endTime, 
      		 $defaultStartTime, $defaultEndTime, 
		 $mmaStartDate, $mmaStartTime, 
		 $mmaEndDate, $mmaEndTime,
		 $locMmaStartYear, $locMmaStartMon, $locMmaStartDay,
		 $locMmaStartHour, $locMmaStartMin, $locMmaStartSec,
		 $locMmaEndYear, $locMmaEndMon, $locMmaEndDay, 
		 $locMmaEndHour, $locMmaEndMin, $locMmaEndSec,
		 $mmaUrlParm,
		 $sampleTime, $sampleTimeBase, $sampleTimeUser,
		 $defSampleTime,
		 $defSampleDataType, $sampleDataType,
      		 $plots, $plotsSelected, $textPlots, 
		 $rainSumMode, $scaleMode, $defScaleMode,
      		 $defScaleFactor, $scaleFactor, 
		 \%doPlotMma, $plotsTypeSerial, $statisticsMode                     );
}		 

#
print hr, '<FONT class="small">';
print "Die Daten stammen von einer Davis Vantage Pro 2 Wetter-Station und werden unter ";
print "Linux mit der Software ";
print
a({href=>"http://userpages.uni-koblenz.de/~krienke/weather.html?Itemid=6"},"wview2wettercgi");
print " und aufbereitet. Alle Angaben erfolgen ohne
Gew&auml;hr fr ihre Vollst&auml;ndigkeit oder Richtigkeit.<br>\n";
print $contact, "\n";
print "<br>Version: $version\n";
print '</FONT>', "\n";

$pageTab->endTable();

# End html Stuff
print end_html, "\n";

#unlink $thImgName;
closeDb($dbh);
exit 0;


