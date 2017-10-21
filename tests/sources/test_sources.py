# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# Utility code to facilitate testing message sources
#
# Copyright © 2017 James E. Scarborough
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

from threading import Condition
import unittest
import time
from circuits import Component, handler

class Watcher(Component):
    def __init__(self):
        super().__init__()
        self.__cv = Condition()
        self.started = False
        self.events = []

    def started(self, component):
        with self.__cv:
            self.started = True
            self.__cv.notify_all()

    def wait_for_start(self):
        with self.__cv:
            while not self.started:
                self.__cv.wait()

    @handler(priority=-100)
    def _on_event(self, event, *args, **kwargs):
        with self.__cv:
            self.events.append((event, args, kwargs))
            self.waitEvent(event)
            self.__cv.notify_all()

    def wait_for_n_events(self, n, filter_function, timeout=float("inf")):
        toolate = time.time() + timeout
        lll = []

        def ll():
            lll.clear()
            lll.extend(filter(filter_function, self.events))
            return lll

        with self.__cv:
            while time.time() < toolate and len(ll()) < n:
                self.__cv.wait(toolate-time.time())
        if time.time() >= toolate:
            raise TimeoutError("n = %d\n" % len(lll) + "\n".join([str(e) for e in self.events]))
        return lll


class ManagerTest(unittest.TestCase):
    def setUp(self):
        self.manager = []

    def tearDown(self):
        for mgr in self.manager:
            mgr.stop()

