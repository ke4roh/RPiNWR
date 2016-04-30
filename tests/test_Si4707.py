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
from RPiNWR.SAME import SAME_PATTERN
import unittest
import logging


class TestSi4707(unittest.TestCase):
    def test_power_up(self):
        logging.basicConfig(level=logging.INFO)
        events = []

        with MockContext() as context:
            with Si4707(context) as radio:
                radio.register_event_listener(events.append)
                result = radio.do_command(PowerUp(function=15)).get(timeout=1)
                self.assertEqual("2.0", result.firmware)
                time.sleep(.01) # The event will come later, after the command is done.
                self.assertEqual(1, len(events))

    def test_patch_command(self):
        logging.basicConfig(level=logging.INFO)
        events = []

        with MockContext() as context:
            with Si4707(context) as radio:
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

        with MockContext() as context:
            with Si4707(context) as radio:
                future = radio.do_command(ExceptionalCommand())
                self.assertRaises(Exception, future.get)

    def test_set_property(self):
        events = []

        with MockContext() as context:
            with Si4707(context) as radio:
                radio.register_event_listener(events.append)
                radio.power_on({"frequency": 162.4, "properties": {}})
                radio.do_command(SetProperty("RX_VOLUME", 5)).get()
                self.assertTrue(5, context.props[0x4000])
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
        with MockContext() as context:
            with Si4707(context) as radio:
                radio.power_on({"frequency": 162.4})
                self.assertEqual(63, radio.do_command(GetProperty("RX_VOLUME")).get())

    def test_agc_control(self):
        with MockContext() as context:
            with Si4707(context) as radio:
                radio.power_on({"frequency": 162.4})
                self.assertTrue(radio.do_command(GetAGCStatus()).get())
                radio.do_command(SetAGCStatus(False)).get()
                self.assertFalse(radio.do_command(GetAGCStatus()).get())
                radio.do_command(SetAGCStatus(True)).get()
                self.assertTrue(radio.do_command(GetAGCStatus()).get())

    def test_rsq_interrupts(self):
        events = []

        with MockContext() as context:
            with Si4707(context) as radio:
                radio.power_on({"frequency": 162.4})
                radio.register_event_listener(events.append)
                context.interrupts |= 8  # RSQ
                time.sleep(.05)
        rsqe = list(filter(lambda x: type(x) is ReceivedSignalQualityCheck, events))
        self.assertEqual(1, len(rsqe))
        self.assertEqual(15, rsqe[0].frequency_offset)

    def test_alert_tone_detection(self):  # WB_ASQ_STATUS
        events = []
        tone_duration = 0.5
        tone_duration_tolerance = 0.1

        with MockContext() as context:
            with Si4707(context) as radio:
                radio.power_on({"frequency": 162.4})
                radio.register_event_listener(events.append)
                context.alert_tone(True)
                time.sleep(tone_duration)
                context.alert_tone(False)
                time.sleep(0.05)

        asqe = list(filter(lambda x: type(x) is AlertToneCheck, events))
        self.assertEqual(2, len(asqe))
        self.assertTrue(asqe[0].tone_on)
        self.assertTrue(asqe[0].tone_start)
        self.assertFalse(asqe[0].tone_end)
        self.assertFalse(asqe[1].tone_on)
        self.assertFalse(asqe[1].tone_start)
        self.assertTrue(asqe[1].tone_end)

        # Finally, make sure the timing of the tones is measured fairly accurately
        self.assertTrue(abs((asqe[1].time_complete - asqe[0].time_complete) - tone_duration) < tone_duration_tolerance,
                        "Tone duration measured as %f sec - spec called for %f±%f" % (
                            asqe[1].time_complete - asqe[0].time_complete, tone_duration, tone_duration_tolerance))
        self.assertIsNone(asqe[0].duration)
        self.assertTrue(abs(asqe[1].time_complete - asqe[0].time_complete - asqe[1].duration) < 0.01)

    def __filter_same_events(self, events, interrupt):
        return list(filter(lambda x: type(x) is SameInterruptCheck and x.status[interrupt], events))

    def __wait_for_eom_events(self, events, n=3, timeout=30):
        timeout = time.time() + timeout
        while len(self.__filter_same_events(events, "EOMDET")) < n and not time.time() >= timeout:
            time.sleep(.02)

    def test_send_message(self):
        events = []
        message = '-WXR-RWT-020103-020209-020091-020121-029047-029165-029095-029037+0030-3031700-KEAX/NWS'

        with MockContext() as context:
            with Si4707(context) as radio:
                radio.power_on({"frequency": 162.4})
                radio.register_event_listener(events.append)
                context.send_message(message=message, voice_duration=1, time_factor=0.1)
                self.__wait_for_eom_events(events)

        same_messages = list(filter(lambda x: type(x) is SAMEMessageReceivedEvent, events))
        self.assertEquals(1, len(same_messages))
        self.assertEquals(message, same_messages[0].message.raw_message)
        for interrupt in ["EOMDET", "HDRRDY", "PREDET"]:
            times = len(self.__filter_same_events(events, interrupt))
            self.assertEquals(3, times, "Interrupt %s happened %d times" % (interrupt, times))
        self.assertEquals(1, len(list(filter(lambda x: type(x) is EndOfMessage, events))))
        self.assertEqual(0, sum(context.same_buffer), "Buffer wasn't flushed")

    def test_send_message_no_tone_2_headers(self):
        # This will hit the timeout.
        events = []
        message = '-WXR-RWT-020103-020209-020091-020121-029047-029165-029095-029037+0030-3031700-KEAX/NWS'

        with MockContext() as context:
            with Si4707(context) as radio:
                radio.power_on({"frequency": 162.4})
                radio.register_event_listener(events.append)
                context.send_message(message=message, voice_duration=50, time_factor=0.1, header_count=2, tone=None)
                self.__wait_for_eom_events(events)

        same_messages = list(filter(lambda x: type(x) is SAMEMessageReceivedEvent, events))
        self.assertEquals(1, len(same_messages))
        self.assertEquals(message, same_messages[0].message.raw_message)
        for interrupt in ["HDRRDY", "PREDET"]:
            times = len(self.__filter_same_events(events, interrupt))
            self.assertEquals(2, times, "Interrupt %s happened %d times" % (interrupt, times))

    def test_send_invalid_message(self):
        # This will hit the timeout.
        events = []
        message = '-WWF-RWT-020103-020209-020091-020121-029047-029165'

        with MockContext() as context:
            with Si4707(context) as radio:
                radio.power_on({"frequency": 162.4})
                radio.register_event_listener(events.append)
                context.send_message(message=message, time_factor=0.1, tone=None, invalid_message=True)
                self.__wait_for_eom_events(events)

        same_messages = list(filter(lambda x: type(x) is InvalidSAMEMessageReceivedEvent, events))
        self.assertEquals(1, len(same_messages))
        self.assertEquals(message, same_messages[0].headers[0][0])
        for interrupt in ["HDRRDY", "PREDET"]:
            times = len(self.__filter_same_events(events, interrupt))
            self.assertEquals(3, times, "Interrupt %s happened %d times" % (interrupt, times))
        ismre = list(filter(lambda x: type(x) is InvalidSAMEMessageReceivedEvent, events))
        self.assertEquals(1, len(ismre))
        self.assertEquals(message, ismre[0].headers[0][0])


class MockContext(Context):
    # This mock includes an i2c facade because of how it came to be.
    # It would be nice to remove that feature...
    def write_bytes(self, data):
        if len(data) == 1:
            self.write8(data[0], 0)
        else:
            self.writeList(data[0], data[1:])

    def read_bytes(self, num_bytes):
        return self.readList(0, num_bytes)

    def reset_radio(self):
        self.__init__()

    # TODO split out the I2C mock from the Si4707 mock
    @staticmethod
    def getPiRevision():
        return 2

    @staticmethod
    def getPiI2CBusNumber():
        return 2

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

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
        self.interrupts = 0
        self.asq_stopped = False
        self.asq_started = False
        self.asq_tone = False
        self.asq_lock = threading.Lock()
        self.same_status = [0] * 4
        self.same_buffer = [0] * 255
        self.same_confidence = [0] * 255
        self.same_lock = threading.Lock()
        self._logger = logging.getLogger(type(self).__name__)
        self.agc = 1

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
        while len(self.registers[reg]) < min(32, length):
            self.registers[reg].append(0)
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
            self.registers[0][0] |= self.interrupts
        elif reg == 0x15 or reg == 0x16:  # patch data
            pass
        elif reg == 0x50:  # WB_TUNE_FREQ - tune the radio
            self.registers[0x50] = self.bus[reg][1:3]

            def set_stc():
                self.registers[0][0] |= 0x01

            threading.Timer(0.5, set_stc).start()
        elif reg == 0x52:  # WB_TUNE_STATUS
            self.registers[0] = [128, 0, self.registers[0x50][0], self.registers[0x50][1], 32, 27]
        elif reg == 0x53:  # WB_RSQ_STATUS
            if self.bus[reg][0]:
                self.interrupts ^= 8
            self.registers[0] = [128 | self.interrupts, 5, 1, 0, 3, 0, 0, 15]
        elif reg == 0x54:  # WB_SAME_STATUS
            with self.same_lock:
                if self.bus[reg][0] & 1:  # INTACK
                    self.interrupts ^= 4
                if self.bus[reg][0] & 2:  # CLEARBUF
                    for i in range(0, len(self.same_buffer)):
                        self.same_buffer[i] = 0
                        self.same_confidence[i] = 0
                    for i in range(0, len(self.same_status)):
                        self.same_status[i] = 0

                # Now assemble the response
                resp = self.registers[0] = [0] * 14
                resp[0] = 128 | self.interrupts
                for i in range(1, 4):
                    resp[i] = self.same_status[i]
                for i in range(0, 8):
                    if self.bus[reg][1] + i < len(self.same_buffer):
                        resp[i + 6] = self.same_buffer[self.bus[reg][1] + i]
                        resp[int((7 - i) / 4) + 4] |= self.same_confidence[i] << (i % 4 * 2)

                if self.bus[reg][0] & 1:  # INTACK
                    self.same_status[1] = 0
        elif reg == 0x55:  # WB_ASQ_STATUS - alert tone detection
            with self.asq_lock:
                if self.bus[reg][0]:
                    self.interrupts ^= 2

                self.registers[0] = [128 | self.interrupts, self.asq_started | self.asq_stopped << 1, self.asq_tone]

                if self.bus[reg][0]:
                    self.asq_stopped = 0
                    self.asq_started = 0
        elif reg == 0x57:  # WB_AGC_STATUS
            self.registers[0] = [128 | self.interrupts, self.agc ]
        elif reg == 0x58:  # WB_AGC_OVERRIDE
            self.agc = self.bus[reg][0]
        else:
            logging.error("Command not mocked 0x%02X" % reg)
            self.registers[0][0] = 192

    def alert_tone(self, playing=False):
        with self.asq_lock:
            if self.asq_tone != playing:
                self.asq_stopped |= not playing
                self.asq_started |= playing
                self.asq_tone = playing
                self.interrupts |= 2

    def send_message(self,
                     message='-WXR-RWT-020103-020209-020091-020121-029047-029165-029095-029037+0030-3031700-KEAX/NWS',
                     tone=8.0, noise=None, header_count=3, voice_duration=15.0, eom=3, time_factor=1.0,
                     invalid_message=False):
        """
        :param message: A valid SAME message
        :param tone: the number of seconds for which to sound the tone, None for no tone
        :param noise: A factor 0-1 (no more than 0.04ish for success), indicating how much noise to sprinkle into the
           messages.  None indicates that noise should not be added.
        :param header_count: The number of headers to send (3 or fewer in case of sketchy circumstances)
        :param voice_duration: The number of seconds to wait before EOM
        :param eom: The number of EOMs to send (3 or fewer)
        :param time_factor: Multiply all the timings by this to expedite testing
        :param invalid_message: to permit an invalid message going into the Si4707 emulation as if by noise
        """
        # There is some parameter checking here because it is much easier to diagnose here than in a separate thread.
        if not invalid_message and not SAME_PATTERN.match(message):
            raise ValueError()
        for num in [tone, noise, header_count, voice_duration, eom]:
            if num is not None:  # None should be fine for these things
                num + 1  # This will give a ValueError if it's not a number
        time_factor + 1  # This needs to be a number

        threading.Timer(0, self.send_message0,
                        [message, tone, time_factor, noise, header_count, voice_duration, eom]).start()

    def send_message0(self, message, tone, time_factor, noise, header_count, voice_duration, eom):
        ###
        # Do these things in turn:
        # SOM
        # 3x:
        #   PREAMBLE
        #   (populate the message)
        #   HDRRDY
        # TONE?
        # voice?
        # EOM
        ###
        try:
            with self.same_lock:
                self.same_status[1] |= 4  # SOMDET - start of message
                self.interrupts |= 4  # SAMEINT

            # Messages come in at 520.83 baud, 8 bits per char, 65.1 chars/sec = .0154 sec/char
            CHAR_TIME = 1 / 520.83 * 8

            for m in range(0, header_count):
                time.sleep(CHAR_TIME * 16 * time_factor)  # Preamble - 16 bytes
                with self.same_lock:
                    self.same_status[1] |= 2  # PREDET
                    self.same_status[2] = 1  # Preamble detected
                    self.interrupts |= 4  # SAMEINT

                time.sleep(CHAR_TIME * 4 * time_factor)  # ZCZC
                msg_start_time = time.time()
                for i in range(0, len(message)):
                    with self.same_lock:
                        self.same_buffer[i] = ord(message[i]) & 0xFF
                        self.same_confidence[i] = 3  # unless we introduce noise
                        self.same_status[3] = max(i, self.same_status[3])
                        self.same_status[2] = 2  # receiving SAME header
                    sleep_for = CHAR_TIME * time_factor * i + msg_start_time - time.time()
                    if sleep_for > 0:
                        time.sleep(sleep_for)

                with self.same_lock:
                    self.same_status[2] = 3  # SAME header message complete
                    self.same_status[1] |= 1  # HDRRDY
                    self.interrupts |= 4  # SAMEINT
                time.sleep(1 * time_factor)  # 1 sec pause between messages

            if tone:
                self.alert_tone(True)
                time.sleep(tone * time_factor)
                self.alert_tone(False)

            if voice_duration:
                time.sleep(voice_duration * time_factor)

            for m in range(0, eom):
                time.sleep(1 * time_factor)
                time.sleep(CHAR_TIME * 4 * time_factor)
                with self.same_lock:
                    self.same_status[1] |= 8  # EOMDET
                    self.same_status[2] = 0  # EOM detected
                    self.interrupts |= 4  # SAMEINT

        except Exception:
            self._logger.exception("Exception in message generator")


if __name__ == '__main__':
    unittest.main()
