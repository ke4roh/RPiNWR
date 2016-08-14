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
from circuits import Event, BaseComponent, handler


class new_score(Event):
    """Event propagating the score of the highest-scoring message in the group."""


class update_score(Event):
    """For the cache to re-check its (own) scores"""


default_message_scores = {
    "SVA": 20, "SV.A": 20,
    "SVR": 30, "SV.W": 30,
    "TOA": 35, "TO.A": 35,
    "TOR": 40, "TO.W": 45
}


class MessageCache(BaseComponent):
    """
    MessageCache holds a collection of (presumably recent) SAME or VTEC (text/CAP) messages.

    Responsibilities:
    0. Know its county
    1. Receive SAME messages
    3. Provide a list of effective messages for a specific county in priority order
    4. Clear out messages upon expiry
    5. Fire events for new and expiring messages

    Collaborators:
    A message source, either Si4707 or other message retriever
    A consumer, to monitor the messages

    Assumptions:
    If time function(s) are passed in to the various functions, they will be consistently nondecreasing.
    Messages are submitted to to the cache in chronological order.
    """

    # TODO track the time since last received message for my fips, alert if >8 days
    # TODO monitor RSSI & SNR and alert if out of spec (what is spec)?
    def __init__(self, latlon, county_fips, sorter, message_scores=default_message_scores, clock=time.time):
        """

        :param latlon: Where you care about messages
        :param county_fips: More about the location
        :param sorter: How to sort the types of messags coming in
        :param callback: a function with one parameter for LocalizedAlertEvent messages as they happen
        """
        super().__init__()
        self.__messages_lock = threading.Lock()
        self.__messages = {}
        self.__local_messages = []
        self.latlon = latlon
        self.county_fips = county_fips
        self.message_scores = message_scores

        if sorter is not None:
            self.sorter = sorter
        else:
            self.sorter = lambda a, b: self.message_scores.get(a.get_event_type(), 0) - \
                                       self.message_scores.get(b.get_event_type(), 0)
        self.__time = clock

    @handler("new_message")
    def add_message(self, message):
        """
        Add the given message and fire any necessary events.

        :param message: A raw weather message - if it has VTEC, it'll be combined.
        """
        with self.__messages_lock:
            collection = self.__messages
            if message.event_id not in collection:
                holder = EventMessageGroup()
                collection[message.event_id] = holder
            else:
                holder = collection[message.event_id]
            holder.add_message(message)
        self.fireEvent(update_score())

    @handler("generate_events")
    def _generate_events(self, event):
        event.reduce_time_left(max(0, self._get_first_expiry() - self.__time()))
        if self._get_first_expiry() < self.__time():
            with self.__messages_lock:
                self.__messages = {k: v for k, v in self.__messages.items() if v.get_end_time_sec() >= self.__time() }
            self.fireEvent(update_score())

    def _get_first_expiry(self):
        """Return the time (secs since the epoch) at which time the first message will expire"""
        with self.__messages_lock:
            try:
                return min([msg.get_end_time_sec() for msg in self.__messages.values()])
            except ValueError:
                return 0

    @handler("update_score")
    def make_new_scores(self):
        """Fire events for new and expired messages.  Call this periodically to fire events for expiring messages."""
        # TODO fire only with the priority of the highest priority message
        # TODO set generate_events to tick when the last message expires
        score = 0

        with self.__messages_lock:

            # Compute the top score
            for here, score_adj in [(True, 0), (False, -10)]:
                active = self.get_active_messages(here=here)
                for m in active:
                    score = max(score, self.message_scores.get(m.get_event_type(), 0) + score_adj)

        self.fireEvent(new_score(score))

    def get_active_messages(self, event_pattern=None, here=True):
        """
        :param event_pattern: a regular expression to match the desired event codes.  default = all.
        :param here: True to retrieve local messages, False to retrieve those for other locales
        """
        if event_pattern is None:
            event_pattern = re.compile(".*")
        elif not hasattr(event_pattern, 'match'):
            event_pattern = re.compile(event_pattern)

        l = list(filter(lambda m: m.is_effective(self.latlon, self.county_fips, here, self.__time) and
                                  event_pattern.match(m.get_event_type()), self.__messages.values()))
        l.sort(key=functools.cmp_to_key(self.sorter))
        return l


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
        self.areas.update(set(msg.get_areas()))

    def get_event_id(self):
        if len(self.messages):
            return self.messages[0].event_id
        else:
            return None

    def __eq__(self, other):
        return other.__type__ is EventMessageGroup and self.get_event_id() == other.get_event_id()

    def add_messages(self, messages):
        for m in messages:
            self.add_message(m)

    def __str__(self):
        if len(self.messages):
            s = self.messages[0].event_id
        else:
            s = "-- empty --"
        return "EventMessageGroup: " + s

    def is_effective(self, latlon, fips, here=True, when=time.time):
        """
        Is this message effective (at the given place and time)?
        :param latlon: The point you want to check
        :param fips: the county containing the point you want to check
        :param when: a function that will return the current time
        :param here: True if you want to know activity at the point, False for activity elsewhere
           (which could be used to raise alertness)
        :return:
        """
        t = when()

        # Get all the messages for the county
        # TODO make this work if they're zones, too.
        cm = list(filter(lambda m: m.applies_to_fips(fips) and m.published <= t and
                                   (m.get_end_time_sec() > t and
                                    (m.get_start_time_sec() is None or m.get_start_time_sec() <= t)), self.messages))

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
