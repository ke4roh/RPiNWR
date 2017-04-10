# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# Logic for parsing and manipulating CAP messages
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
import time
import xml.etree.ElementTree as etree
import urllib3
import logging
import iso8601
from RPiNWR.sources.net_events import NetStatus

_http = urllib3.PoolManager(num_pools=3)


class NewAtomEntry(object):
    def __init__(self, msg, t):
        self.message = msg
        self.time = t

    def __str__(self):
        return "New: " + str(self.message)


class DeletedAtomEntry(object):
    def __init__(self, entry_id, t):
        self.entry_id = entry_id
        self.time = t

    def __str__(self):
        return "Gone: " + str(self.entry_id)


class AtomEventGenerator(object):
    """
    This class polls an atom feed and calls the callback for every new item
    observed.
    """

    def __init__(self, url, callback, polling_interval_sec=60, persistence_sec=600):
        self.__logger = logging.getLogger(self.__class__.__name__)
        self.status = NetStatus("starting", True)
        self.url = url
        self.callback = callback
        self.polling_interval_sec = polling_interval_sec
        self.stop = False
        self.updated = None
        self.next_poll_time = 0
        self.persistence = persistence_sec
        self.id_cache = {}
        self.__thread = threading.Thread(target=self.__poller, daemon=True)
        self.__thread.start()

    def __poller(self):
        while not self.stop:
            self.__poll()
            self.next_poll_time = time.time() + self.polling_interval_sec
            while time.time() < self.next_poll_time:
                time.sleep(min(0.5, time.time() + self.next_poll_time))

    def __poll(self):
        # TODO what happens if HTTP error/timeout?
        r = _http.urlopen('GET', self.url, preload_content=False)
        if r.status != 200:
            self.__set_status(NetStatus(r.status))
            return
        try:
            root = etree.parse(r).getroot()
        except Exception as e:
            self.__set_status(NetStatus(str(e)))
            self.__logger.exception("net woes")
            return

        self.__set_status(NetStatus("OK", True, t=r.headers['Date']))
        self.last_successful_poll = self.status.time
        http_time_now = self.status.time
        updated = iso8601.parse_date(root.find("{http://www.w3.org/2005/Atom}updated").text).timestamp()
        self.updated = updated

        missing = dict(self.id_cache)
        new_messages = []
        for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
            entry_id = entry.find('{http://www.w3.org/2005/Atom}id').text
            if entry_id in self.id_cache:
                missing.pop(entry_id)
            else:
                new_messages.append(entry)
                self.id_cache[entry_id] = updated

        # Events need to fire in order so that they are processed in order
        for msg in sorted(new_messages, key=lambda x: iso8601.parse_date(
                x.find('{http://www.w3.org/2005/Atom}published').text).timestamp()):
            self.callback(NewAtomEntry(msg, http_time_now))

        # Clear the cache of entries that have gone away
        for entry_id, entry in missing.items():
            if self.id_cache[entry_id] + self.persistence <= updated:
                self.id_cache.pop(entry_id)
                self.callback(DeletedAtomEntry(entry_id, http_time_now))

        # Keep the cache of remaining entries alive
        for entry_id in self.id_cache.keys():
            self.id_cache[entry_id] = updated

    def __set_status(self, status):
        """
        This will always set the status, but only fire an event if the message or normalcy changed
        :param status: The new status
        """
        old_status = self.status
        self.status = status
        if old_status.msg != status.msg or old_status.normal != status.normal:
            self.callback(status)
