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
from RPiNWR.sources.radio.radio_component import Radio_Component
import os
import errno
from test_sources import Watcher
from circuits import Debugger

class TestRadioComponent(unittest.TestCase):
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
        TestRadioComponent._remove_if_exists("messages.log", "radio.log")

    def tearDown(self):
        TestRadioComponent._remove_if_exists("messages.log", "radio.log")

    def test_commands(self):
        import RPiNWR.sources.radio.Si4707.mock
        c= RPiNWR.sources.radio.Si4707.mock.MockContext()
        watcher = Watcher()
        r = Radio_Component(
            "--hardware-context RPiNWR.sources.radio.Si4707.mock.MockContext "
            "--mute-after -1  --transmitter KID77".split()) + watcher + Debugger()
        r.start()
        try:
            watcher.wait_for_start()
            watcher.wait_for_n_events(1, filter_function=lambda x: x[0].name == "radio_status", timeout=2)
            message = '-WXR-RWT-020103-020209-020091-020121-029047-029165-029095-029037+0030-3031700-KEAX/NWS-'
            r.context.run_script('send %s' % message)
            # It takes some time for the message to get "sent"
            events = watcher.wait_for_n_events(1, filter_function=lambda x: x[0].name == "new_message", timeout=20)
            self.assertEqual(message, events[0][0].args[0].get_SAME_message()[0])
        finally:
            r.stop()