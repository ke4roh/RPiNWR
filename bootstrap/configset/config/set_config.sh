#! /bin/sh
MYPATH=`dirname $0`
if [ "$1" != "" ]; then
    CONFIG=$1
else
    CONFIG=self_ap
fi

(cd $MYPATH/$CONFIG ; tar cfp - .) | (cd / ; tar xf -)


