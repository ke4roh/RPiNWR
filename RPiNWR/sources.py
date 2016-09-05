# -*- coding: utf-8 -*-
__author__ = 'jscarbor'

# A source:
#    Accepts a dict for its configuration
#    Knows the location of interest (dict of lat/lon, FIPS, zone
#    Fires events when messages are received and expire for the location of interest
#    Knows its delay (typical age of messages available)
#    Knows if it might have polygons
#    Knows if it is operational (i.e. received an appropriate message recently enough)
#    Recovers or fires an event when not operational, or when recovered

import time
from lxml import html
from circuits import BaseComponent, handler, Timer, Event
from circuits.web.client import Client, request
from urllib.parse import urlencode
from .NWSText import NWSText
from enum import Enum


class new_message(Event):
    """This fires when a new message comes in."""


class poll(Event):
    """This fires every time it's time to fetch data, but handlers must not block."""


class net_status(Event):
    down = 0
    ok = 1


# TODO update polling interval depending on weather

class AlertSource(BaseComponent):
    def __init__(self, location):
        self.location = location
        super().__init__()

    def get_delay_sec(self):
        raise NotImplementedError()

    def has_polygons(self):
        raise NotImplementedError()

    def is_operational(self):
        raise NotImplementedError()

class TextPull(AlertSource):
    channel = "TextPull"
    client = Client(channel=channel)

    # http_client = AsyncHTTPClient(force_instance=True,
    #                              defaults=dict(user_agent="tornado/RPiNWR", accept="*/*"))

    def __init__(self, location, url='http://forecast.weather.gov/'):
        self.url = url
        super().__init__(location)
        self.last_status_time = 0
        # {'lat': loc.lat, 'lon': loc.lon, 'warnzone': loc.zone, 'firewxzone': loc.firezone}

    def init(self):
        self.latest_messages = set([])
        self.lastquery = 0
        if self.url is not None:
            self.timer = Timer(interval=60,
                               event=request("GET", self.url + 'showsigwx.php?' + urlencode(self.location)),
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
            self.fireEvent(net_status(net_status.ok), "*")
            self.last_status_time = time.time()
        else:
            self.fireEvent(net_status(net_status.down), "*")
            self.last_status_time = time.time()
            # TODO log it
            raise Exception("{0:d} {1:s}".format(response.status, response.reason))

    @handler("generate_events")
    def generate_events(self, event):
        if self.last_status_time + self.timer.interval < time.time():
            if self.is_operational():
                self.fireEvent(net_status(net_status.ok), "*")
            else:
                self.fireEvent(net_status(net_status.down), "*")
        event.reduce_time_left(self.last_status_time + self.timer.interval)

    @handler("radio_message_escrow")
    def radio_message_escrow(self, action, message):
        # If a message has been escrowed, start poolling now and fast.
        if action == EscrowAction.escrowed:
            # Check immediately and every 7 seconds thereafter
            self.timer.reset(7)
            if self.lastquery < time.time() - 5:
                self.fire(self.timer.event, self.channel)
        else:
            # Step down to a lower level
            self.timer.reset(20)

    @handler("new_score")
    def new_score(self, score):
        if self.timer.interval > 7:  # not on high alert for an escrowed message
            if score >= 30:
                self.timer.reset(20)
            elif score > 0:
                self.timer.reset(60)
            else:
                self.timer.reset(120)

    def is_operational(self):
        return self.lastquery < (time.time() - self.timer.interval + 30)


class radio_message_escrow(Event):
    pass

class EscrowAction(Enum):
    escrowed = "A radio message has been waylaid pending net validation."
    released = "A radio message has been re-fired from escrow (probably because net failed)."
    suppressed = "A radio message is discarded because no net problem was observed for the entire escrow time."