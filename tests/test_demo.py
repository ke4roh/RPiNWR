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
from RPiNWR.sources.radio.Si4707 import SAMEMessageReceivedEvent, EndOfMessage
from RPiNWR.demo import Radio
import os
import errno


class TestDemo(unittest.TestCase):
    @staticmethod
    def _remove_if_exists(*filenames):
        for filename in filenames:
            # http://stackoverflow.com/a/10840586/2544261
            try:
                os.remove(filename)
            except OSError as e:  # this would be "except OSError, e:" before Python 2.6
                if e.errno != errno.ENOENT:  # errno.ENOENT = no such file or directory
                    raise  # re-raise exception if a different error occured

    def setUp(self):
        TestDemo._remove_if_exists("messages.log", "radio.log")

    def tearDown(self):
        TestDemo._remove_if_exists("messages.log", "radio.log")

    def test_commands(self):
        with Radio("--hardware-context RPiNWR.sources.radio.Si4707.mock.MockContext "
                   "--mute-after -1  --transmitter KID77".split()) as r:
            running = [False]

            def run_radio():
                running[0] = True
                r.run()
                running[0] = False

            threading.Timer(0, run_radio).start()  # start the radio in its own thread
            while not r.ready:
                time.sleep(.1)
            messages = []
            eoms = []

            def add_message(event):
                if type(event) == SAMEMessageReceivedEvent:
                    messages.append(event.message)
                elif type(event) == EndOfMessage:
                    eoms.append(event)

            r.radio.register_event_listener(add_message)
            message = '-WXR-RWT-020103-020209-020091-020121-029047-029165-029095-029037+0030-3031700-KEAX/NWS-'
            r.context.run_script('send %s' % message)

            timeout = time.time() + 10
            while len(messages) < 1:
                self.assertTrue(time.time() < timeout)

            # Waiting for the EOMs gives the logger time to do its thing for messages
            timeout = time.time() + 10
            while len(eoms) < 1:
                self.assertTrue(time.time() < timeout)

            with open("messages.log") as f:
                messages_logged = f.readlines()

            self.assertEqual(1, len(messages_logged))
            self.assertTrue(message in messages_logged[0])

            with open("radio.log") as f:
                radio_log = f.readlines()

            self.assertEqual(3, len(list(filter(lambda x: "SAMEHeaderReceived" in x, radio_log))))

            r.radio.shutdown()
            while r.ready:
                time.sleep(.1)
            time.sleep(.1)
            self.assertFalse(running[0])  # Radio was really turned off
