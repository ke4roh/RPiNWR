# A Raspberry Pi Weather Radio

This library adapts the [Raspberry Pi SAME decoder board](http://www.aiwindustries.com/store/p9/Raspberry_Pi_B_%2F2_NWR_Receiver%2FSAME_Decoder.html) to user-level
functionality so that you can focus on your application.  It has
error handling!  It has unit tests!  It has events!  Callbacks!

## Build status
[![build status](https://travis-ci.org/ke4roh/RPiNWR.svg?branch=master)](https://travis-ci.org/ke4roh/RPiNWR/branches)
[![Coverage Status](https://coveralls.io/repos/github/ke4roh/RPiNWR/badge.svg?branch=master)](https://coveralls.io/github/ke4roh/RPiNWR?branch=master)

## Install
Get GPIO working:

```bash
sudo apt-get update
sudo apt-get install git python-dev python-smbus i2c-tools python-rpi.gpio python3-rpi.gpio
# Follow instructions to install i2c kernel support:
#   https://learn.adafruit.com/adafruits-raspberry-pi-lesson-4-gpio-setup/configuring-i2c
git clone https://github.com/nioinnovation/Adafruit_Python_GPIO.git
(cd Adafruit_Python_GPIO; sudo python3 setup.py install)
# now CD to where you cloned this project
sudo ./setup.py test
python3 -m RPiNWR.demo
```

## License
GNU GPL v. 3 - see the LICENSE file for details

