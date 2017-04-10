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
from RPiNWR.messages.cache import MessageCache
from circuits import Debugger, BaseComponent
from RPiNWR.alerting import AlertTimer
from RPiNWR.sources.radio.radio_component import Radio_Component, radio_run_script
from RPiNWR.sources.radio.radio_squelch import Radio_Squelch
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
        """

        :param n: How many events
        :param pattern: A string representing a pattern for re.compile() or the result of re.compile()
        :param timeout: How long are you willing to wait?
        :return:
        """
        try:
            pattern.match('')
        except AttributeError:
            pattern = re.compile(pattern)

        timeout = time.time() + timeout
        while sum(pattern.match(x) is not None for x in self.debug_history) < n:
            now = time.time()
            if now > timeout:
                raise TimeoutError()
            with self.debug_lock:
                # Wait for the next message to come along
                self.debug_lock.wait(timeout - now)


class ScriptInjector(BaseComponent):
    def inject(self, script):
        self.fire(radio_run_script(script))


class TestIntegration(unittest.TestCase):
    def setUp(self):
        self.box = None

    def tearDown(self):
        if self.box is not None:
            self.box.stop()
        try:
            shutil.rmtree("dropzone")
        except FileNotFoundError:
            pass

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
        t = 1302983940
        self.box = box = FolderMonitor(location, "dropzone", .5) + AlertTimer(clock=lambda: t) + MessageCache(
            location, clock=lambda: t) + Debugger(logger=logger)
        box.start()

        logger.wait_for_n_events(1, re.compile('<started.*'), 5)

        shutil.copyfile(os.path.join(os.path.dirname(os.path.realpath(__file__)), "KRAH.TO.W.0023.2011.txt"),
                        'dropzone/tow')

        logger.wait_for_n_events(1, re.compile('<begin_alert.*'), 2)
        t += 120
        logger.wait_for_n_events(1, re.compile('<continue_alert.*'), 2)

        t += 60 * 45
        logger.wait_for_n_events(1, re.compile('<all_clear.*'), 2)

        self.assertEquals(0, len(logger.error_history), str(logger.error_history))
        self.assertTrue(len(logger.debug_history) < 20, str(logger.debug_history))

    def test_Si4707_to_alert_timer_with_no_net(self):
        location = {
            'lat': 35.77,
            'lon': -78.64,
            'fips6': '037183',
            'warnzone': 'NCZ183',
            'firewxzone': 'NCZ183'
        }
        logger = DummyLogger()

        # Start this test at the top of the hour, at least an hour before the current time
        # Top of the hour gives some repeatability.
        # It's based on the current time because otherwise the radio will infer the wrong year on message timestamps.
        # TODO Design a better solution: Get year from context? Get time from context? Get time from radio?
        t = int((time.time() - 60 * 60)/(60*60)) * 60 * 60
        si4707args = "--hardware-context RPiNWR.sources.radio.Si4707.mock.MockContext --mute-after 0  --transmitter WXL58".split()
        injector = ScriptInjector()
        self.box = box = Radio_Component(si4707args) + Radio_Squelch() + \
                         TextPull(location=location, url='http://127.0.0.1:17/') + \
                         AlertTimer(continuation_reminder_interval_sec=.05, clock=lambda: t) + \
                         MessageCache(location, clock=lambda: t) + \
                         Debugger(logger=logger) + injector
        inject = injector.inject

        box.start()

        logger.wait_for_n_events(1, re.compile('<started.*'), 5)

        logger.wait_for_n_events(1, re.compile('<radio_status.*'), 5)

        self.assertTrue(len(logger.debug_history) < 20, str(logger.debug_history))

        # Send t-storm, see alert level go up
        injector.inject("send -WXR-SVR-037183+0030-%s-KRAH/NWS-" % time.strftime('%j%H%M', time.gmtime(t)))
        logger.wait_for_n_events(1, re.compile('<new_message[^\-]*-WXR-SVR-'), 5)
        logger.wait_for_n_events(1, re.compile('<new_score\D+30'), 5)

        # send TOR, see alert propagate because the net is (bogus)
        t += 120
        injector.inject("send -WXR-TOR-037183+0030-%s-KRAH/NWS-" % time.strftime('%j%H%M', time.gmtime(t)))
        logger.wait_for_n_events(1, re.compile('<new_message[^\-]*-WXR-TOR-'), 5)
        logger.wait_for_n_events(1, re.compile('<new_score\D+40'), .5)
        logger.wait_for_n_events(1, re.compile('<begin_alert.*'), 2)

        t += 60 * .5

        logger.wait_for_n_events(1, re.compile('<continue_alert.*'), 2)

        t += 60 * 45
        logger.wait_for_n_events(1, re.compile('<all_clear.*'), 2)

        self.assertEquals(0, len(logger.error_history), str(logger.error_history))
        self.assertTrue(len(logger.debug_history) < 35, str(logger.debug_history))
