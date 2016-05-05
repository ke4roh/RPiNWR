# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# Tests for handling of incoming messages and the likes
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

import unittest
import time
import threading
from RPiNWR.Si4707.events import SAMEMessageReceivedEvent
from RPiNWR.demo import Radio


class TestDemo(unittest.TestCase):
    def test_commands(self):
        with Radio("--hardware-context RPiNWR.Si4707.mock.MockContext --mute-after -1".split()) as r:
            running = [False]

            def run_radio():
                running[0] = True
                r.run()
                running[0] = False

            threading.Timer(0, run_radio).start()  # start the radio in its own thread
            while not r.ready:
                time.sleep(.1)
            messages = []

            def add_message(event):
                if type(event) == SAMEMessageReceivedEvent:
                    messages.append(event.message)

            r.radio.register_event_listener(add_message)
            r.context.run_script(
                'send -WXR-RWT-020103-020209-020091-020121-029047-029165-029095-029037+0030-3031700-KEAX/NWS-')

            timeout = time.time() + 10
            while len(messages) < 1:
                self.assertTrue(time.time() < timeout)

            # TODO check that the event was logged reasonably

            r.radio.shutdown()
            while r.ready:
                time.sleep(.1)
            time.sleep(.1)
            self.assertFalse(running[0])  # Radio was really turned off
