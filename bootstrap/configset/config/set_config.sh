#! /bin/sh
MYPATH=`dirname $0`
if [ "$1" != "" ]; then
    CONFIG=$1
else
    CONFIG=self_ap
fi

(cd $MYPATH/$CONFIG ; tar cfp - .) | (cd / ; tar xf -)

if [ "$CONFIG" = "self_ap" ]; then
	service hostapd stop ; service hostapd start
	service dhcpd restart
	ifdown wlan0
	ifup wlan0
	ifconfig wlan0 inet 10.0.0.1 netmask 255.255.255.0 
elif
	service hostapd stop
	service dhcpd restart
	ifdown wlan0
	ifup wlan0
fi


