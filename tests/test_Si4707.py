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
from RPiNWR.Si4707.mock import MockContext
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
                time.sleep(.01)  # The event will come later, after the command is done.
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
                timeout = time.time() + 5
                while not len(list(filter(lambda x: type(x) is ReceivedSignalQualityCheck, events))):
                    time.sleep(.1)
                    self.assertTrue(time.time()<timeout)

        rsqe = list(filter(lambda x: type(x) is ReceivedSignalQualityCheck, events))
        self.assertEqual(1, len(rsqe))
        self.assertEqual(1, rsqe[0].frequency_offset)

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
        interrupts_cleared = [0]

        with MockContext() as context:
            def check_interrupts_cleared(event):
                try:
                    if event.intack:
                        self.assertEqual(0, context.interrupts)
                        interrupts_cleared[0] += 1
                except AttributeError:
                    pass

            with Si4707(context) as radio:
                radio.register_event_listener(check_interrupts_cleared)
                radio.power_on({"frequency": 162.4})
                radio.register_event_listener(events.append)
                context.send_message(message=message, voice_duration=1, time_factor=0.1)
                self.__wait_for_eom_events(events)

        same_messages = list(filter(lambda x: type(x) is SAMEMessageReceivedEvent, events))
        self.assertEquals(1, len(same_messages))
        self.assertEquals(message, same_messages[0].message.get_SAME_message()[0])
        for interrupt in ["EOMDET", "HDRRDY", "PREDET"]:
            times = len(self.__filter_same_events(events, interrupt))
            self.assertEquals(3, times, "Interrupt %s happened %d times" % (interrupt, times))
        self.assertEquals(1, len(list(filter(lambda x: type(x) is EndOfMessage, events))))
        self.assertEqual(0, sum(context.same_buffer), "Buffer wasn't flushed")
        self.assertTrue(10 < interrupts_cleared[0] < 13, interrupts_cleared[0])

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
        self.assertEquals(message, same_messages[0].message.get_SAME_message()[0])
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

        same_messages = list(filter(lambda x: type(x) is SAMEMessageReceivedEvent, events))
        self.assertEquals(1, len(same_messages))
        self.assertEquals(message, same_messages[0].message.headers[0][0])
        for interrupt in ["HDRRDY", "PREDET"]:
            times = len(self.__filter_same_events(events, interrupt))
            self.assertEquals(3, times, "Interrupt %s happened %d times" % (interrupt, times))

if __name__ == '__main__':
    unittest.main()
