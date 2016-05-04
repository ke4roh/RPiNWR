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
from RPiNWR.AIWIBoardContext import AIWIBoardContext
from threading import Timer
import Adafruit_GPIO.I2C as i2c
import time

if __name__ == '__main__':
    def exclude_routine_status_checks(record):
        return not (
            (record.funcName == "write8" and record.msg == "Wrote 0x%02X to register 0x%02X" and record.args[
                1] == 0x14) or
            (record.funcName == "readList" and record.msg == "Read the following from register 0x%02X: %s" and
             record.args[1][0] == 128 and len(record.args[1]) == 1))

    logging.basicConfig(level=logging.DEBUG, filename="radio.log", format='%(asctime)-15s %(levelname)-5s %(message)s')
    logger = logging.getLogger()

    message_logger = logging.getLogger("same.messages")
    message_log_handler = logging.FileHandler("messages.log", encoding='utf-8')
    message_logger.addHandler(message_log_handler)
    message_log_handler.setFormatter(logging.Formatter(datefmt=""))
    message_logger.setLevel(logging.INFO)  # INFO=watches, WARN=warnings, CRIT=emergencies

    # Since this is logging lots of things, best to not also log every time we check for status
    i2cLogger = logging.getLogger('Adafruit_I2C.Device.Bus.{0}.Address.{1:#0X}'
                                  .format(i2c.get_default_bus(), 0x11))
    i2cLogger.addFilter(exclude_routine_status_checks)

    def log_event(event):
        if True or isinstance(event, SAMEEvent):
            logger.info(str(event))

    def log_tune(event):
        if type(event) is TuneFrequency:
            logger.info("Tuned to %.3f  rssi=%d  snr=%d" % (event.frequency / 400.0, event.rssi, event.snr))

    def unmute_for_message(event):
        if type(event) is SAMEMessageReceivedEvent:
            radio.mute(False)
        if type(event) is EndOfMessage:
            radio.mute(True)

    try:
        with AIWIBoardContext() as context:
            with Si4707(context) as radio:
                radio.register_event_listener(log_event)
                radio.register_event_listener(log_tune)
                radio.register_event_listener(unmute_for_message)
                radio.power_on()  # { "frequency": 162.4 })
                radio.setAGC(False)  # Turn on AGC only if the signal is too strong (high RSSI)
                radio.mute(False)
                radio.set_volume(63)
                Timer(15, radio.mute, [True]).start()  # Mute the radio after 15 seconds
                while True:
                    time.sleep(300)
                    radio.do_command(ReceivedSignalQualityCheck()).get()
                    # Run these blinking commands through the command queue to see that it's still working
                    # radio.queue_callback(context.led, [True])
                    # time.sleep(.5)
                    # radio.queue_callback(context.led, [False])
                    # time.sleep(4.5)
                    # The radio turns off when the with block exits

    except KeyboardInterrupt:
        pass  # suppress the stack trace
