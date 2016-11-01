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
import os
from RPiNWR.sources import TextPull, FolderMonitor
from RPiNWR.cache import MessageCache
from circuits import Debugger
from RPiNWR.alerting import AlertTimer
import threading
import re
import shutil


class DummyLogger(object):
    def __init__(self):
        self.debug_history = []
        self.error_history = []
        self.debug_lock = threading.Condition()

    def debug(self, s):
        with self.debug_lock:
            self.debug_history.append(s)
            self.debug_lock.notify_all()

    def error(self, s):
        self.error_history.append(s)

    def wait_for_n_events(self, n, pattern, timeout):
        timeout = time.time() + timeout
        while len([filter(lambda x: pattern.match(x), self.debug_history)]) < n:
            now = time.time()
            if now > timeout:
                raise TimeoutError()
            with self.debug_lock:
                self.debug_lock.wait(timeout - now)


class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.box = None

    def tearDown(self):
        if self.box is not None:
            self.box.stop()
        shutil.rmtree("dropzone")

    def test_text_to_audio_playback(self):
        location = {
            'lat': 35.77,
            'lon': -78.64,
            'fips6': '037183',
            'warnzone': 'NCZ183',
            'firewxzone': 'NCZ183'
        }
        logger = DummyLogger()

        if not os.path.exists("dropzone"):
            os.makedirs("dropzone")
        t = [1302983940]
        self.box = box = FolderMonitor(location, "dropzone", .5) + AlertTimer(clock=lambda: t[0]) + MessageCache(
            location, clock=lambda: t[0]) + Debugger(logger=logger)
        box.start()

        logger.wait_for_n_events(1, re.compile('<started.*'), 5)

        shutil.copyfile(os.path.join(os.path.dirname(os.path.realpath(__file__)), "KRAH.TO.W.0023.2011.txt"),
                        'dropzone/tow')

        logger.wait_for_n_events(1, re.compile('<begin_alert.*'), 2)
        t[0] += 120
        logger.wait_for_n_events(1, re.compile('<continue_alert.*'), 2)

        t[0] += 60 * 45
        logger.wait_for_n_events(1, re.compile('<all_clear.*'), 2)

        self.assertEquals(0, len(logger.error_history), str(logger.error_history))
        self.assertTrue(len(logger.debug_history) < 20, str(logger.debug_history))
