# -*- coding: utf-8 -*-
__author__ = 'ke4roh'

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

from RPiNWR.Si4707 import *
import unittest
import logging


class TestSi4707(unittest.TestCase):
    def test_power_up(self):
        logging.basicConfig(level=logging.INFO)
        i2c = MockI2C()
        events = []

        def print_event(event):
            logging.info(str(event))

        with Si4707(i2c) as radio:
            radio.register_event_listener(print_event)
            radio.register_event_listener(events.append)
            result = radio.do_command(PowerUp(function=15)).get(timeout=1)
            self.assertEqual("2.0", result.firmware)
            self.assertEqual(1, len(events))

    def test_patch_command(self):
        logging.basicConfig(level=logging.INFO)
        i2c = MockI2C()
        events = []

        def print_event(event):
            print(str(event))

        with Si4707(i2c) as radio:
            radio.register_event_listener(print_event)
            radio.register_event_listener(events.append)
            self.assertFalse(radio.radio_power)
            result = radio.do_command(
                PatchCommand(DEFAULT_CONFIG["power_on"]["patch"], DEFAULT_CONFIG["power_on"]["patch_id"])).get(
                timeout=500)
            self.assertTrue(radio.radio_power)

        # Power Down is supposed to happen as part of the __exit__ routine
        self.assertEquals(PowerDown, type(events[-1]))

    def test_exception_in_command(self):
        class ExceptionalCommand(Command):
            def do_command0(self, r):
                raise NotImplemented("Oh no!")

        i2c = MockI2C()
        with Si4707(i2c) as radio:
            future = radio.do_command(ExceptionalCommand())
            self.assertRaises(Exception, future.get)

    def test_set_property(self):
        i2c = MockI2C()
        events = []

        def print_event(event):
            print(str(event))

        with Si4707(i2c) as radio:
            radio.register_event_listener(print_event)
            radio.register_event_listener(events.append)
            radio.power_on({"frequency": 162.4, "properties": {}})
            radio.do_command(SetProperty("RX_VOLUME", 5)).get()
            self.assertTrue(5, i2c.props[0x4000])
            self.assertRaises(ValueError, SetProperty, "RX_VOLUME", 66)

        # Wait up to 2 sec for the shutdown to finish (it should go really fast)
        timeout = time.time() + 2
        while not type(events[-1]) is PowerDown:
            if time.time() >= timeout:
                raise TimeoutError()
            time.sleep(.002)

        # There is supposed to be 500 ms between power up and first tuning when using the crystal
        # oscillator.  We'll check that.
        self.assertTrue(type(events[-1]) is PowerDown)
        checked_rtt = False
        checked_tune = False
        pup_time = 0
        for event in events:
            if not pup_time:
                if type(event) is PowerUp or type(event) is PatchCommand:
                    pup_time = event.time_complete
        self.assertTrue(abs((radio.tune_after - pup_time) * 1000 - 500) < 5,
                        "tune_after - pup_time should be about 500 ms, but it is %d ms" % int(
                            (radio.tune_after - pup_time) * 1000))
        for event in events:
            if type(event) is ReadyToTuneEvent:
                self.assertTrue(event.time >= radio.tune_after,
                                "RTT happened %d ms early." % int((radio.tune_after - event.time) * 1000))
                checked_rtt = True
            if type(event) is TuneFrequency:
                self.assertTrue(event.time_complete >= radio.tune_after,
                                "Tune happened %d ms early." % int((radio.tune_after - event.time_complete) * 1000))
                checked_tune = True
        self.assertTrue(checked_tune)
        self.assertTrue(checked_rtt)

    def test_get_property(self):
        i2c = MockI2C()

        def print_event(event):
            print(str(event))

        with Si4707(i2c) as radio:
            radio.power_on({"frequency": 162.4})
            radio.register_event_listener(print_event)
            self.assertEqual(63, radio.do_command(GetProperty("RX_VOLUME")).get())


class MockI2C(object):
    # TODO split out the I2C mock from the Si4707 mock
    @staticmethod
    def getPiRevision():
        return 2

    @staticmethod
    def getPiI2CBusNumber():
        return 2

    def __init__(self):
        self.bus = {
            0: [0] * 5
        }
        self.registers = {
            0: [128, 1, 2, 3, 4, 5, 6, 7]
        }
        self.OPMODE = 0  # 5 = Analog audio,
        self.props = dict([(x[0], x[3]) for x in PROPERTIES])
        self.power = False

    def reverseByteOrder(self, data):
        "Reverses the byte order of an int (16-bit) or long (32-bit) value"
        # Courtesy Vishal Sapre
        byteCount = len(hex(data)[2:].replace('L', '')[::2])
        val = 0
        for i in range(byteCount):
            val = (val << 8) | (data & 0xff)
            data >>= 8
        return val

    def errMsg(self):
        raise NotImplemented()

    def write8(self, reg, value):
        self.bus[value][0] = reg
        self.op(reg)

    def write16(self, reg, value):
        raise NotImplemented()

    def writeRaw8(self, value):
        raise NotImplemented()

    def writeList(self, reg, l):
        if type(l) is not list or len(l) < 1 or len(l) > 32:
            raise TypeError("Third argument must be a list of at least one, but not more than 32 integers")

        self.bus[reg] = l
        self.op(reg)

    def readList(self, reg, length):
        return self.registers[reg][0:length]

    def readU8(self, reg):
        raise NotImplemented()

    def readS8(self, reg):
        raise NotImplemented()

    def readU16(self, reg, little_endian=True):
        raise NotImplemented()

    def readS16(self, reg, little_endian=True):
        raise NotImplemented()

    def op(self, reg):
        if reg == 0x01:  # Power up
            # CTSIEN GPO2OEN PATCH XOSCEN FUNC[3:0]
            # ARG2 OPMODE[7:0]
            # [(self.GPO2EN | self.PATCH | self.XOSCEN | self.WB), self.OPMODE
            self.CTSIEN = self.bus[reg][0] >> 7
            self.GPO2OEN = self.bus[reg][0] >> 6 & 1
            self.PATCH = self.bus[reg][0] >> 5 & 1
            self.XOSCEN = self.bus[reg][0] >> 4 & 1
            FUNC = self.bus[reg][0] & 15
            self.OPMODE = self.bus[reg][1]

            if FUNC == 3:  # WB Receive
                self.power = True
                self.registers[0][0] = 128
            elif FUNC == 15:  # Query Library ID
                self.registers[0] = [128, 7, 50, 48, 252, 255, 66, 9]
            else:
                self.registers[0][0] = 192  # CTS & ERR
        elif reg == 0x10:  # GET_REV
            self.registers[0] = [128, 7, 50, 48, 209, 149, 50, 48, 0]
        elif reg == 0x11:  # POWER_DOWN
            self.power = False
        elif reg == 0x12:  # SET_PROPERTY
            self.props[struct.unpack(">H", bytes(self.bus[reg][1:3]))] = struct.unpack(">H", bytes(self.bus[reg][3:5]))
        elif reg == 0x13:  # GET_PROPERTY
            prop = struct.unpack(">H", bytes(self.bus[reg][1:3]))[0]
            propval = struct.pack(">H", self.props[prop])
            self.registers[0] = [128, 0, propval[0], propval[1], 0, 0, 0]
        elif reg == 0x14:  # GET_INT_STATUS (interrupt)
            pass
        elif reg == 0x15 or reg == 0x16:  # patch data
            pass
        elif reg == 0x50:  # WB_TUNE_FREQ - tune the radio
            self.registers[0x50] = self.bus[reg][1:3]

            def set_stc():
                self.registers[0][0] |= 0x01

            threading.Timer(0.5, set_stc).start()
        elif reg == 0x52:  # WB_TUNE_STATUS
            self.registers[0] = [128, 0, self.registers[0x50][0], self.registers[0x50][1], 32, 27]
        else:
            logging.error("Command not mocked 0x%02X" % reg)
            self.registers[0][0] = 192


if __name__ == '__main__':
    unittest.main()
