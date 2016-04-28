# -*- coding: utf-8 -*-
__author__ = 'jscarbor'
import RPi.GPIO as gpio
from time import sleep
import signal
import Adafruit_GPIO.I2C
from RPiNWR.Si4707 import Context

# TODO wrap this so that it will be cleaned up EVERY time
# --- see http://stackoverflow.com/questions/865115/how-do-i-correctly-clean-up-a-python-object#865272


class AIWIBoardContext(Context):
    """
    This class encapsulates the context through which the radio is used,
    providing adapters to the functionality to reset the radio,
    write to it, and read from it.  A duck-wise compatible class can be used
    to adapt to any context.

    This class is not thread-safe.

    This must be instantiated from the main thread - which is the default, because it sets
    interrupt handlers.  If you need to set your own interrupt handlers, ensure that you call
    shutdown to clean things up, else you won't be able to run it again without power-cycling
    your Raspberry Pi.

    """
    __signals_trapped = False

    relay_gpio_pins = [13, 19]

    i2c = Adafruit_GPIO.I2C.get_i2c_device(0x11)

    def __init__(self):
        super(AIWIBoardContext, self).__init__()
        self.gpio_started = False

    def reset_radio(self):
        """
        Reset the Si4707 chip
        """
        # Ref https://github.com/AIWIndustries/Pi_4707/blob/master/firmware/NWRSAME_v2.py
        if self.gpio_started:
            gpio.cleanup()
        self.gpio_started = True
        gpio.setmode(gpio.BCM)  # Use board pin numbering

        gpio.setup(17, gpio.OUT)  # Setup the reset pin
        gpio.output(17, gpio.LOW)  # Reset the Si4707.
        sleep(0.4)
        gpio.output(17, gpio.HIGH)

        gpio.setup(23, gpio.IN, pull_up_down=gpio.PUD_UP)
        gpio.add_event_detect(23, gpio.FALLING)

        # Initialize the onboard relays
        for pin in self.relay_gpio_pins:
            gpio.setup(pin, gpio.OUT)  # setup gpio pin for relay
            gpio.output(pin, gpio.LOW)  # boot to disabled state

        # set up the LED
        # https://www.reddit.com/r/raspberry_pi/comments/3641ug/blinking_an_onboard_led_on_the_pi_2_model_b/
        # http://raspberrypi.stackexchange.com/questions/697/how-do-i-control-the-system-leds-using-my-
        # sudo echo none >/sys/class/leds/led0/trigger
        # GPIO 16 LOW is on, HIGH is off
        gpio.setup(16, gpio.OUT)
        gpio.output(16, gpio.HIGH)

        sleep(1)

    def write_bytes(self, data):
        # TODO make this accept bytes(...)
        if len(data) == 1:
            self.i2c.write8(data[0], 0)
        else:
            self.i2c.writeList(data[0], data[1:])

    def read_bytes(self, num_bytes):
        # TODO make this return bytes(...)
        return self.i2c.readList(0, num_bytes)

    def __enter__(self):
        # Make sure to cleanup GPIO afterward
        if not self.__signals_trapped:
            self.__signals_trapped = True
            for sig in [signal.SIGQUIT, signal.SIGTERM, signal.SIGTSTP]:
                if hasattr(signal.getsignal(sig), '__call__'):
                    deleg = signal.getsignal(sig)

                    def delegate(signum, stack):
                        self.__exit__(None, None, None)
                        deleg(signum, stack)

                    signal.signal(sig, delegate)
                else:
                    def delegate(signum, stack):
                        self.__exit__(None, None, None)

                    signal.signal(sig, delegate)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.gpio_started:
                gpio.cleanup()
                self.gpio_started = False
        except RuntimeError:
            self._logger.info("Cleanup trouble", exc_info=True)
            pass  # Probably tried to do it twice

    def relay(self, num, on):
        if on:
            status = gpio.HIGH
        else:
            status = gpio.LOW
        gpio.output(self.relay_gpio_pins[num], status)

    def led(self, on):
        if not on:
            status = gpio.HIGH
        else:
            status = gpio.LOW
        gpio.output(16, status)
