# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# Store messages and list the active ones
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
import threading
import functools
import time
import re
from shapely.geometry import Point


class MessageCache(object):
    """
    MessageCache holds a collection of (presumably recent) SAME or VTEC (text/CAP) messages.

    Responsibilities:
    0. Know its county
    1. Receive SAME messages
    3. Provide a list of effective messages for a specific county in priority order
    4. Clear out inactive messages upon request

    Collaborators:
    A message source, either Si4707 or other message retriever
    A consumer, to monitor the messages
    """

    # TODO track the time since last received message for my fips, alert if >8 days
    # TODO monitor RSSI & SNR and alert if out of spec (what is spec)?
    def __init__(self, latlon, county_fips, sorter):
        self.__messages_lock = threading.Lock()
        self.__messages = {}
        self.__local_messages = []
        self.latlon = latlon
        self.county_fips = county_fips
        self.sorter = sorter
        # TODO add cleanup daemon thread to sweep every so often for expired messages

    def add_message(self, message):
        with self.__messages_lock:
            collection = self.__messages
            if message.event_id not in collection:
                holder = EventMessageGroup()
                collection[message.event_id] = holder
            else:
                holder = collection[message.event_id]
            holder.add_message(message)

    def get_active_messages(self, when=None, event_pattern=None, here=True):
        """
        :param when: the time for which to check effectiveness of the messages, default = the present time
        :param event_pattern: a regular expression to match the desired event codes.  default = all.
        :param here: True to retrieve local messages, False to retrieve those for other locales
        """
        if when is None:
            when = time.time()
        if event_pattern is None:
            event_pattern = re.compile(".*")
        elif not hasattr(event_pattern, 'match'):
            event_pattern = re.compile(event_pattern)

        l = list(filter(lambda m: m.is_effective(self.latlon, self.county_fips, here, when) and event_pattern.match(
            m.get_event_type()), self.__messages.values()))
        l.sort(key=functools.cmp_to_key(self.sorter))
        return l

    def clear_inactive(self, when=None):
        with self.__messages_lock:
            self.__messages = self.get_active_messages(when)


class EventMessageGroup(object):
    """
    Responsibilities:
    Store messages with VTEC codes by their geos
    split them by their geos to find status by geo
    """

    def __init__(self):
        self.messages = []
        self.areas = set([])

    def add_message(self, msg):
        if len(self.messages):
            assert msg.event_id == self.get_event_id()
            if msg in self.messages:
                return
        self.messages.append(msg)
        self.areas.update(msg.get_areas())
        # Maybe handle corrections by replacing, maybe just leave them in as historical record

    def get_event_id(self):
        if len(self.messages):
            return self.messages[0].event_id
        else:
            return None

    def add_messages(self, messages):
        for m in messages:
            self.add_message(m)

    def __str__(self):
        if len(self.messages):
            s = self.messages[0].event_id
        else:
            s = "-- empty --"
        return "EventMessageGroup: " + s

    def is_effective(self, latlon, fips, here=True, when=None):
        """
        Is this message effective (at the given place and time)?
        :param latlon: The point you want to check
        :param fips: the county containing the point you want to check
        :param when: The time at which to evaluate, default= now
        :param here: True if you want to know activity at the point, False for activity elsewhere
           (which could be used to raise alertness)
        :return:
        """
        if when is None:
            when = time.time()
        else:
            when + 0  # fail if it's not numeric

        # Get all the messages for the county
        # TODO make this work if they're zones, too.
        cm = list(filter(lambda m: m.applies_to_fips(fips) and m.published <= when and
                                   (m.get_end_time_sec() > when and
                                    (m.get_start_time_sec() is None or m.get_start_time_sec() <= when)), self.messages))

        # If it has a polygon, does it apply here?
        its_here = len(cm)
        polygon = None
        if its_here and latlon:
            try:
                polygon = cm[-1].container.polygon
            except AttributeError:
                polygon = None

            its_here = (not polygon or polygon.contains(Point(*latlon)))

        if here:
            return its_here
        else:
            if polygon:
                return not its_here
            elif its_here:
                return False
            else:
                # check neighboring areas
                for a in filter(lambda x: x != fips, self.areas):
                    if self.is_effective(None, a, True, when):
                        return True
        return False

    def get_start_time_sec(self):
        return self.messages[0].get_start_time_sec()

    def get_end_time_sec(self):
        return self.messages[-1].get_end_time_sec()

    def get_event_type(self):
        return self.messages[-1].get_event_type()
