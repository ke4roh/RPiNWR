# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# Status and events common to all net sources
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
from circuits import Event
import calendar
import time

class NetStatus(object):
    def __init__(self, msg, normal=False, t=None):
        """
        :param msg: Whatever you want to say about the status
        :param normal: True if and only if this is successful operation
        :param t: The time, either seconds since the epoch or an HTTP date string like 'Wed, 25 May 16 01:24:05 GMT'
        """
        self.msg = msg
        self.normal = normal and True
        if t is None:
            t = time.time()
        try:
            t += 0
        except TypeError:
            # Maybe it was a string to parse
            t = calendar.timegm(time.strptime(t.strip(), '%a, %d %b %Y %H:%M:%S %Z'))
        self.time = t

    def __str__(self):
        if self.normal:
            stat = "normal"
        else:
            stat = "ERROR"
        return "NetStatus %s %s %.2df" % (stat, self.msg, self.time)


class net_status(Event):
    down = 0
    ok = 1
