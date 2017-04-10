# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# Get weather alerts from the internet by various means
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

# A source:
#    Accepts a dict for its configuration
#    Knows the location of interest (dict of lat/lon, FIPS, zone
#    Fires events when messages are received and expire for the location of interest
#    Knows its delay (typical age of messages available)
#    Knows if it might have polygons
#    Knows if it is operational (i.e. received an appropriate message recently enough)
#    Recovers or fires an event when not operational, or when recovered

from lxml import html
from .net_events import *
from .alert_source import AlertSource, new_message
from circuits import handler, Timer, Event
from circuits.web.client import Client, request
from urllib.parse import urlencode
from ..messages.NWSText import NWSText, FIPS_STATE
from ..sources.radio.radio_squelch import EscrowAction

class poll(Event):
    """This fires every time it's time to fetch data, but handlers must not block."""


# TODO update polling interval depending on weather


class TextPull(AlertSource):
    channel = "TextPull"
    client = Client(channel=channel)

    # http_client = AsyncHTTPClient(force_instance=True,
    #                              defaults=dict(user_agent="tornado/RPiNWR", accept="*/*"))

    def __init__(self, location, url='http://forecast.weather.gov/'):
        self.url = url
        super().__init__(location)
        self.last_status_time = 0
        self.last_status = None
        # {'lat': loc.lat, 'lon': loc.lon, fips6: 001089, warncounty: ALC089, 'warnzone': loc.zone, 'firewxzone': loc.firezone}

    def init(self):
        self.latest_messages = set([])
        self.lastquery = 0

        if self.url is not None:

            # Construct a web-specific version of the location
            loc = dict(self.location)
            if "warncounty" not in loc and "fips6" in loc:
                loc['warncounty'] = FIPS_STATE[loc['fips6'][-5:-3]] + "C" + loc['fips6'][-3:]
            if 'fips6' in loc:
                del loc['fips6']

            self.timer = Timer(interval=60,
                               event=request("GET", self.url + 'showsigwx.php?' + urlencode(loc),
                                             headers={'Accept': '*/*', 'User-Agent': 'RPiNWR/0.0.1'}),
                               persist=True, channel=self.channel)
            self.timer.register(self)

            # # import re, urllib3
            # #_http = urllib3.PoolManager()
            #     def new_location(self, location):
            #         # This code deduces location data (wfo, zones & fips) from lat & lon, but it only works if there is some
            #         # alert for the place.  (One could wait for there to be an alert and try this, but that's sketchy.
            #         # There are also polygons for these data available from NWS, but they change sometimes.  (Maybe worth
            #         # checking here from time to time?)
            #         # TODO figure out if there's a use for this process and use it or not.
            #         # This must be made async before using - it's written to be synchronous for now
            #         r = _http.request('GET', self.url + 'MapClick.php',
            #                           fields={'lat': location["lat"], 'lon': location["lon"]},
            #                           headers={'User-Agent': 'urllib3/RPiNWR', 'Accept': '*/*'})
            #
            #         if r.status == 200:
            #             ds = r.data.decode('utf-8')
            #
            #             def f(xp):
            #                 try:
            #                     return re.search(xp, ds).group(1)
            #                 except Exception:
            #                     return None
            #
            #             location.wfo = f("wfo=(\w+)")
            #             location.fips = f("county=(\w+)")
            #             location.zone = f("(?:warnzone|zoneid)=(\w+)")
            #             location.firewxzone = f("firewxzone=(\w+)")

    @handler("response")
    def _receive_response(self, response):
        if 200 <= response.status < 300:
            self.lastquery = time.time()
            tree = html.fromstring(response.read().decode('utf-8'))
            msgs = set([x.text for x in tree.xpath('//pre')])
            new_messages = msgs.difference(self.latest_messages)
            self.latest_messages = msgs
            for msg in new_messages:
                for tm in NWSText.factory(msg):
                    self.fireEvent(new_message(tm, "*"))
            self._fire_status(net_status.ok)
        else:
            self._fire_status(net_status.down)
            # TODO log it
            raise Exception("{0:d} {1:s}".format(response.status, response.reason))

    def _fire_status(self, status):
        if self.last_status != status:
            self.last_status = status
            self.fireEvent(net_status(status), "*")
        self.last_status_time = time.time()

    @handler("generate_events")
    def generate_events(self, event):
        if self.last_status_time + self.timer.interval < time.time():
            if self.is_operational():
                self._fire_status(net_status.ok)
            else:
                self._fire_status(net_status.down)
        event.reduce_time_left(self.last_status_time + self.timer.interval)

    @handler("radio_message_escrow")
    def radio_message_escrow(self, action, message):
        # If a message has been escrowed, start polling now and fast.
        if action == EscrowAction.escrowed:
            # Check immediately and every 7 seconds thereafter
            self.timer.reset(7)
            if self.lastquery < time.time() - 5:
                self.fire(self.timer.event, self.channel)
        else:
            # Step down to a lower level
            self.timer.reset(20)

    @handler("new_score")
    def new_score(self, score, message):
        if self.timer.interval > 7:  # not on high alert for an escrowed message
            if score >= 30:
                self.timer.reset(20)
            elif score > 0:
                self.timer.reset(60)
            else:
                self.timer.reset(120)

    def is_operational(self):
        return self.lastquery > (time.time() - self.timer.interval + 30)

