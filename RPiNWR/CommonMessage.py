# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# Logic manipulating alert messages
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

import time
from circuits import Event

class new_message(Event):
    """This event indicates a new message has arrived."""

class CommonMessage(object):
    def is_effective(self, when=time.time):
        """
        :param when: a function returning nondecreasing floats, default= time.time(), the current time
        :return: True if the message is effective at the given time, False otherwise
        """
        return (self.get_start_time_sec() is None or self.get_start_time_sec() <= when()) and \
               (self.get_end_time_sec() is None or when() <= self.get_end_time_sec())

    def get_start_time_sec(self):
        raise NotImplemented()

    def get_end_time_sec(self):
        raise NotImplemented()

    def get_event_type(self):
        raise NotImplemented()

    def __eq__(self, other):
        if type(other) is type(self):
            ignored = self._fields_to_skip_for_eq()
            d1 = self.__dict__
            d2 = other.__dict__
            for k1, v1 in d1.items():
                if k1 not in ignored and (k1 not in d2 or d2[k1] != v1):
                    return False
            for k2, v2 in d2.items():
                if k2 not in ignored and k2 not in d1:
                    return False
            return True
        return False

    def _fields_to_skip_for_eq(self):
        return set([])