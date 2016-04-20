# -*- coding: utf-8 -*-

from RPiNWR import *
from tests.test_Si4707 import MockI2C
import unittest

class TestRPiNWR(unittest.TestCase):

    def testRadioPowerUp(self):
        with Radio(gpio=MockGPIO(), i2c=MockI2C()) as radio:
            radio.power_on()


class MockGPIO:
    BCM = 0
    OUT = 0
    LOW = 0
    HIGH = 1
    IN = 1
    PUD_UP = 1
    FALLING = 0

    def __init__(self):
        self.__pinmode = [None] * 40
        self.__output = [None] * 40
        self.__input = [None] * 40
        self.__mode = None

    def setmode(self, mode):
        self.__mode = mode  # gpio.BCM Use board pin numbering

    def setup(self, pin, mode, pull_up_down=None):
        self.__pinmode[pin] = mode

    def output(self, pin, value):
        self.__output[pin] = value

    def add_event_detect(self, pin, transition):
        pass

    def cleanup(self):
        pass


if __name__ == '__main__':
    unittest.main()
