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

import unittest
from RPiNWR.alerting import AlertTimer


class MockGenerateEvent(object):
    # TODO use unittest mocks so that if this method goes away, the test fails.
    def __init__(self):
        self.rtl = float("inf")
        self.lastrtl = float("nan")

    def reduce_time_left(self, secs):
        self.rtl = min(secs, self.rtl)
        self.lastrtl = secs


class TestAlertTimer(unittest.TestCase):
    def testAlert(self):
        t = [0]
        events = []

        def fire(event):
            events.append(event)

        at = AlertTimer(continuation_reminder_interval_sec=1, clock=lambda: t[0])
        at.fire = fire  # override to capture the events
        at.new_score(20)
        self.assertEqual(0, len(events))
        genevent = MockGenerateEvent()
        at.generate_events(genevent)
        self.assertEqual(1, genevent.lastrtl)
        self.assertEqual(0, len(events))
        t[0] = 1
        at.new_score(39)
        genevent = MockGenerateEvent()
        at.generate_events(genevent)
        self.assertEqual(1, genevent.lastrtl)
        self.assertEqual(0, len(events))
        t[0] = 2
        # Now fire an alert
        at.new_score(40)
        self.assertEqual(1, len(events))
        self.assertEqual("begin_alert", events[0].name)
        events.clear()
        genevent = MockGenerateEvent()
        at.generate_events(genevent)
        self.assertEqual(2, genevent.lastrtl)  # double for the first one
        self.assertEqual(0, len(events))

        # And check for double the delay after the first
        t[0] = 3
        at.generate_events(genevent)
        self.assertEqual(1, genevent.lastrtl)  # double for the first one
        self.assertEqual(0, len(events))

        t[0] = 4
        at.generate_events(genevent)
        self.assertEqual(1, genevent.lastrtl)
        self.assertEqual(1, len(events))
        self.assertEqual("continue_alert", events[0].name)
        events.clear()

        t[0] = 4.5
        at.generate_events(genevent)
        self.assertEqual(.5, genevent.lastrtl)
        self.assertEqual(0, len(events))

        t[0] = 5
        at.generate_events(genevent)
        self.assertEqual(1, genevent.lastrtl)
        self.assertEqual(1, len(events))
        self.assertEqual("continue_alert", events[0].name)
        events.clear()

        t[0] = 5.5
        at.new_score(30)
        self.assertEqual(1, len(events))
        self.assertEqual("all_clear", events[0].name)
        events.clear()
        at.generate_events(genevent)
        self.assertEqual(1, genevent.lastrtl)
        self.assertEqual(0, len(events))

        t[0] = 6
        at.generate_events(genevent)
        self.assertEqual(1, genevent.lastrtl)
        self.assertEqual(0, len(events))
