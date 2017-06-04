# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# A clock that runs fast for testing purposes
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
import time
import unittest


class MockClock(object):
    def __init__(self, speedup=10, epoch=None):
        self.epoch = None
        self.start = None
        self.speedup = speedup
        self.set((epoch is None and time.time()) or epoch)

    def time(self):
        return self.epoch + (time.time() - self.start) * self.speedup

    def set(self, new_epoch):
        self.start = time.time()
        self.epoch = new_epoch


class TestMockClock(unittest.TestCase):
    def test_mock_clock_from_now(self):
        c = MockClock()
        start = time.time()
        self.assertAlmostEqual(start, c.start, 2)
        self.assertAlmostEqual(start, c.time(), 2)
        start = c.time()
        time.sleep(.5)
        self.assertAlmostEqual(start + (time.time() - start) * 10, c.time(), 2)

    def test_mock_clock_from_fixed_time(self):
        auspiciousDate = 1596807540
        c = MockClock(epoch=auspiciousDate, speedup=50)
        self.assertAlmostEqual(auspiciousDate, c.time(), 2)
        time.sleep(.5)
        self.assertAlmostEqual(auspiciousDate + 25, c.time(), 1)
