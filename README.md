# A Raspberry Pi Weather Radio

This library adapts the [Raspberry Pi SAME decoder board](http://www.aiwindustries.com/store/p9/Raspberry_Pi_B_%2F2_NWR_Receiver%2FSAME_Decoder.html) to user-level
functionality so that you can focus on your application.  It has
error handling!  It has unit tests!  It has events!  Callbacks!

## Build status
[![build status](https://travis-ci.org/ke4roh/RPiNWR.svg?branch=master)](https://travis-ci.org/ke4roh/RPiNWR/branches)
[![Coverage Status](https://coveralls.io/repos/github/ke4roh/RPiNWR/badge.svg?branch=master)](https://coveralls.io/github/ke4roh/RPiNWR?branch=master)

## Features
* Receive, prioritize, and act on SAME alerts
* Extensive error correction for poorly-received messages
* Quick (<.5 sec) response to received messages
* Multi-threaded event model

## Code
Before you run the radio, you'll need to set up dependencies:

```bash
sudo apt-get update
sudo apt-get install git python-dev python-smbus i2c-tools python-rpi.gpio python3-rpi.gpio
# Follow instructions to install i2c kernel support:
#   https://learn.adafruit.com/adafruits-raspberry-pi-lesson-4-gpio-setup/configuring-i2c
git clone https://github.com/nioinnovation/Adafruit_Python_GPIO.git
(cd Adafruit_Python_GPIO; sudo python3 setup.py install)
# now CD to where you cloned this project
sudo ./setup.py test
```

Running the radio is simple:
```bash
python3 -m RPiNWR.demo --transmitter WXL58
```

You can specify the transmitter or not, but if you do and the 
transmitter is listed in nwr_data.py, error correction is 
more robust.  

See demo.py and its tests for information about command line options.

At the moment, this radio implementation lets you subscribe to events
and observe status of the radio over time.  Further development will
add functionality and bring the demo code up to a more practical 
implementation.  

## Helping
Please submit your log files as issues! Messages and RSSI reports are 
especially useful at the moment.  

Also, see the next section...

## Developing
Have a look at ```# TODO``` items in the code and the issues to see what
needs to be done.  Pull requests and issues are most welcome!

Adding an Si4707 in a new environment (not RPi, or not the AIWI board)
is straightforward.  Just create a new context that provides the same
functionality as AIWIBoardContext.py for your environment.  Name that
context when you start the radio, and you're up and running.  Please
consider contributing your context via a pull request. 

## License
GNU GPL v. 3 - see the LICENSE file for details

