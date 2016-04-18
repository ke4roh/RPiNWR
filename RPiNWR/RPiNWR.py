# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# User-level control of a weather radio based on Si4707
#
# Copyright © 2016 James E. Scarborough
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import time
from RPiNWR.Si4707 import Si4707
import signal
import logging
from threading import Timer


class RPiNWRadio(object):
    """
    A Weather Radio

    This must be instantiated from the main thread - which is the default, because it sets
    interrupt handlers.  If you need to set your own interrupt handlers, ensure that you call
    shutdown to clean things up, else you won't be able to run it again without power-cycling
    your Raspberry Pi.

    This class is responsible for
     - Interfacing with the Raspberry Pi board
     - Providing user-level access to and control of Si4707 (on, off, tune, volume, messages, alert tones)
    """
    # TODO wrap this so that it will be cleaned up every time
    # --- see http://stackoverflow.com/questions/865115/how-do-i-correctly-clean-up-a-python-object#865272
    relay_gpio_pins = [13, 19]

    def __init__(self, gpio=None, i2c=None):
        self._logger = logging.getLogger(type(self).__name__)
        if gpio is None:
            import RPi.GPIO

            self.__gpio = RPi.GPIO
        else:
            self.__gpio = gpio
        if i2c is None:
            # This is the python3-compatible version.  There is a pull-request to merge it, but it's not accepted yet -
            #    https://github.com/adafruit/Adafruit_Python_GPIO/pull/30
            # sudo apt-get install python3-smbus
            # git clone https://github.com/nioinnovation/Adafruit_Python_GPIO.git
            # cd Adafruit_Python_GPIO
            # sudo python3 setup.py install
            import Adafruit_GPIO.I2C
            # from Adafruit_I2C import Adafruit_I2C (legacy)
            self.__i2c = Adafruit_GPIO.I2C.get_i2c_device(0x11)
        else:
            self.__i2c = i2c

    def __enter__(self):
        gpio = self.__gpio
        # Ref https://github.com/AIWIndustries/Pi_4707/blob/master/firmware/NWRSAME_v2.py
        gpio.setmode(gpio.BCM)  # Use board pin numbering

        gpio.setup(17, gpio.OUT)  # Setup the reset pin
        gpio.output(17, gpio.LOW)  # Reset the Si4707.
        time.sleep(0.2)
        gpio.output(17, gpio.HIGH)

        gpio.setup(23, gpio.IN, pull_up_down=gpio.PUD_UP)
        gpio.add_event_detect(23, gpio.FALLING)

        # Make sure to cleanup GPIO afterward
        for sig in [signal.SIGQUIT, signal.SIGTERM, signal.SIGTSTP]:
            if signal.getsignal(sig) == signal.SIG_DFL:
                signal.signal(sig, self.__exit__)
            else:
                raise ValueError("Not clobbering your custom interrupt handlers.")
        # signal.signal(signal.SIGHUP, handler)

        # ************This section is for the Pi specific board only******************#
        # Each relay has a 3 pin jumper that allows you to establish whether you want
        # the disabled state to be normally open (NO) or normally closed (NC). Place the
        # jumper accordingly. LOW=Disabled and HIGH=Active.
        for pin in RPiNWRadio.relay_gpio_pins:
            gpio.setup(pin, gpio.OUT)  # setup gpio pin for relay
            gpio.output(pin, gpio.LOW)  # boot to disabled state
        # ****************************************************************************#

        time.sleep(1)
        self.radio = Si4707(self.__i2c).__enter__()
        return self

    def power_on(self, configuration=None):
        """
        Turn on the radio, applying patches & configuration as appropriate.

        :param configuration: a dict with several keys:
            properties: a dict of mnemonics and their values to be set at startup
            frequency: The frequency to tune in MHz, or absent to pick the strongest signal from a scan
        :return: After the radio is running
        """
        self.radio.power_on(configuration)

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.info("Cleaning up RPiNWR")
        if self.radio is not None:
            r = self.radio
            self.radio = None
            r.__exit__(exc_type, exc_val, exc_tb)
        if self.__gpio is not None:
            g = self.__gpio
            self.__gpio = None
            g.cleanup()

    def tune(self, frequency):
        """
        Change the channel
        :param frequency: MHz
        :return: a tuple of RSSI (dBµV) and SNR (dB)
        """
        return self.radio.tune(frequency)

    def tune_status(self):
        """
        Check on the radio
        :return: a tuple of frequency (MHz), RSSI (dBµV), and SNR (dB)
        """
        return self.radio.tune_status()

    def scan(self):
        return self.radio.scan()

    def set_volume(self, loud):
        """
        :param loud: 0<=loud<=63
        """
        return self.radio.set_volume(loud)

    def get_volume(self):
        """
        :return:  0<=loud<=63
        """
        return self.radio.get_volume()

    def mute(self, hush):
        """
        :param hush: True to mute the speaker, False otherwise
        """
        self.radio.mute(hush)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    def print_event(event):
        logging.debug(str(event))

    try:
        with RPiNWRadio() as radio:
            radio.radio.register_event_listener(print_event)
            radio.power_on()
            radio.mute(False)
            radio.set_volume(63)
            Timer(15, radio.mute, [True]).start()  # Mute the radio after 15 seconds
            time.sleep(20)  # In a more realistic scenario, this would loop forever.
            # The radio turns off when the with block exits

    except KeyboardInterrupt:
        pass