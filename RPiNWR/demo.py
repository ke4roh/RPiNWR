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
from RPiNWR.Si4707.commands import TuneFrequency
from RPiNWR.AIWIBoardContext import AIWIBoardContext
from threading import Timer
import time

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, filename="radio.log", format='%(asctime)-15s %(message)s')

    def log_event(event):
        if isinstance(event, SAMEEvent):
            logging.info(str(event))

    def log_tune(event):
        if type(event) is TuneFrequency:
            logging.info("Tuned to %.3f  rssi=%d  snr=%d" % (event.frequency / 400.0, event.rssi, event.snr))

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
                radio.power_on()
                radio.mute(False)
                radio.set_volume(63)
                Timer(15, radio.mute, [True]).start()  # Mute the radio after 15 seconds
                while True:
                    # Run these blinking commands through the command queue to see that it's still working
                    radio.queue_callback(context.led, [True])
                    time.sleep(.5)
                    radio.queue_callback(context.led, [False])
                    time.sleep(4.5)
                    # The radio turns off when the with block exits

    except KeyboardInterrupt:
        pass  # suppress the stack trace
