# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# Issue events for the initial alert, ongoing reminders, and an all-clear.
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
from circuits import Component, Event
from time import time


class AlertTimer(Component):
    def __init__(self, continuation_reminder_interval_sec=60, clock=time):
        """

        :param continuation_reminder_interval_sec: The length of time between "the alert is still in effect" messages
        :param clock: a function that returns the time, default is time.time
        """
        self.current_level = 0
        self.last_alert = 0
        self.clock = clock
        self.alerting_level = 40
        self.continuation_reminder_interval_sec = continuation_reminder_interval_sec
        super().__init__()

    def new_score(self, score, message):
        old_level = self.current_level
        self.current_level = score
        if old_level < self.alerting_level <= score:
            self.fire(begin_alert())
            self.last_alert = self.clock() + self.continuation_reminder_interval_sec
        elif old_level >= self.alerting_level > score:
            self.fire(all_clear())
            self.last_alert = 0

    def generate_events(self, event):
        if self.current_level < self.alerting_level:
            event.reduce_time_left(self.continuation_reminder_interval_sec)
            return

        if self.current_level >= self.alerting_level and self.clock() >= self.last_alert + self.continuation_reminder_interval_sec:
            self.last_alert = self.clock()
            self.fire(continue_alert())
        event.reduce_time_left(self.last_alert + self.continuation_reminder_interval_sec - self.clock())


class begin_alert(Event):
    pass


class continue_alert(Event):
    pass


class all_clear(Event):
    pass
