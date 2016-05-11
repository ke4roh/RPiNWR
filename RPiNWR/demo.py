#!/usr/bin/python3
# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# Demo weather radio app based on Si4707
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

import logging
from RPiNWR.Si4707 import Si4707
from RPiNWR.Si4707.events import *
from RPiNWR.Si4707.commands import TuneFrequency, ReceivedSignalQualityCheck
from threading import Timer
import time
import argparse
import importlib

_CONTEXTS = ["RPiNWR.Si4707.mock.MockContext"]
try:
    from RPiNWR.AIWIBoardContext import AIWIBoardContext

    _CONTEXTS.append("RPiNWR.AIWIBoardContext.AIWIBoardContext")
except ImportError:
    pass  # It's not a valid choice in this environment
_DEFAULT_CONTEXT = _CONTEXTS[-1]


class Radio(object):
    def __init__(self, args=None):
        self.radio = None
        self.context = None
        self.ready = False
        self.logger = logging.getLogger("RPiNWR")
        clparser = argparse.ArgumentParser()
        clparser.add_argument("--off-after", default=None)
        clparser.add_argument("--hardware-context", default=_DEFAULT_CONTEXT, type=Radio._lookup_type)
        clparser.add_argument("--mute-after", default=15, type=float)
        clparser.add_argument("--transmitter", default=None)
        self.args = clparser.parse_args(args)
        self._configure_logging()

    @staticmethod
    def _lookup_type(type_name):
        module_name, class_name = type_name.rsplit(".", 1)
        return getattr(importlib.import_module(module_name), class_name)

    def _configure_logging(self):
        logging.basicConfig(level=logging.WARNING,
                            format='%(asctime)-15s %(levelname)-5s %(message)s')
        # TODO put log configuration in a (yaml) config file

        # The basic config doesn't hold through tests
        radio_logger = logging.getLogger("RPiNWR")
        radio_logger.setLevel(logging.DEBUG)
        radio_log_handler = logging.FileHandler("radio.log", encoding='utf-8')
        radio_log_handler.setFormatter(logging.Formatter(fmt='%(asctime)-15s %(levelname)-5s %(message)s', datefmt=""))
        radio_log_handler.setLevel(logging.DEBUG)
        radio_logger.addHandler(radio_log_handler)

        message_logger = logging.getLogger("RPiNWR.same.message")
        message_logger.setLevel(logging.INFO)
        message_log_handler = logging.FileHandler("messages.log", encoding='utf-8')
        message_log_handler.setFormatter(logging.Formatter(datefmt=""))
        message_log_handler.setLevel(logging.INFO)  # INFO=watches & emergencies, WARN=warnings
        message_logger.addHandler(message_log_handler)

        # Since this is logging lots of things, best to not also log every time we check for status
        try:
            import Adafruit_GPIO.I2C as i2c

            i2cLogger = logging.getLogger('Adafruit_I2C.Device.Bus.{0}.Address.{1:#0X}'
                                          .format(i2c.get_default_bus(), 0x11))
        except ImportError:
            i2cLogger = logging.getLogger(
                'Adafruit_I2C.Device.Bus')  # a little less specific, but probably just as good
        i2cLogger.addFilter(Radio.exclude_routine_status_checks)

    @staticmethod
    def exclude_routine_status_checks(record):
        return not (
            (record.funcName == "write8" and record.msg == "Wrote 0x%02X to register 0x%02X" and record.args[
                1] == 0x14) or
            (record.funcName == "readList" and record.msg == "Read the following from register 0x%02X: %s" and
             record.args[1][0] == 128 and len(record.args[1]) == 1))

    def log_event(self, event):
        if True or isinstance(event, SAMEEvent):
            self.logger.info(str(event))

    def log_tune(self, event):
        if type(event) is TuneFrequency:
            self.logger.info(
                "Tuned to %.3f  rssi=%d  snr=%d" % (event.frequency / 400.0, event.rssi, event.snr))

    def unmute_for_message(self, event):
        if type(event) is SAMEMessageReceivedEvent:
            self.radio.mute(False)
        if type(event) is EndOfMessage:
            self.radio.mute(True)

    def _contextFactory(self):
        return self.args.hardware_context()

    def run(self):
        """
        :return: when the radio stops, and not before
        """
        try:
            with self._contextFactory() as context:
                self.context = context
                with Si4707(context) as radio:
                    self.radio = radio
                    radio.register_event_listener(self.log_event)
                    radio.register_event_listener(self.log_tune)
                    radio.register_event_listener(self.unmute_for_message)
                    radio.power_on({"transmitter": self.args.transmitter})  # { "frequency": 162.4 })
                    radio.setAGC(False)  # Turn on AGC only if the signal is too strong (high RSSI)
                    radio.mute(False)
                    radio.set_volume(63)
                    if self.args.off_after:
                        Timer(self.args.off_after, radio.power_off).start()
                    if self.args.mute_after >= 0:
                        Timer(self.args.mute_after, radio.mute, [True]).start()  # Mute the radio after 15 seconds
                    self.ready = True
                    next_rsq_check = 0
                    while not radio.stop:
                        if time.time() > next_rsq_check:
                            if radio.radio_power:
                                radio.do_command(ReceivedSignalQualityCheck()).get()
                            next_rsq_check = time.time() + 300
                        time.sleep(.1)
                        # Run these blinking commands through the command queue to see that it's still working
                        # radio.queue_callback(context.led, [True])
                        # time.sleep(.5)
                        # radio.queue_callback(context.led, [False])
                        # time.sleep(4.5)
                        # The radio turns off when the with block exits
                    self.ready = False

        except KeyboardInterrupt:
            pass  # suppress the stack trace

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.ready = False
        if self.radio:
            self.radio.shutdown()


if __name__ == '__main__':
    with Radio() as r:
        r.run()
