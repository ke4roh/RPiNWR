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
import re
import urllib3
from lxml import html
from circuits import BaseComponent, handler, Timer, Event
from circuits.web.client import Client, request
from urllib.parse import urlencode
from .NWSText import NWSText

_http = urllib3.PoolManager()


class new_message(Event):
    """This fires when a new message comes in."""


class poll(Event):
    """This fires every time it's time to fetch data, but handlers must not block."""


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


class Radio(AlertSource):
    def __init__(self, location, config):
        super().__init__(location)

    def get_delay_sec(self):
        return 15

    def has_polygons(self):
        return False

        # TODO translate Demo into this code and fire newSAMEMessage events when messages come in


class TextPull(AlertSource):
    channel = "TextPull"
    client = Client(channel=channel)

    # http_client = AsyncHTTPClient(force_instance=True,
    #                              defaults=dict(user_agent="tornado/RPiNWR", accept="*/*"))

    def __init__(self, location, url='http://forecast.weather.gov/'):
        self.url = url
        super().__init__(location)
        # {'lat': loc.lat, 'lon': loc.lon, 'warnzone': loc.zone, 'firewxzone': loc.firezone}


    def init(self):
        self.latest_messages = set([])
        self.lastquery = 0
        if self.url is not None:
            self.timer = Timer(interval=60, event=request("GET", self.url + 'showsigwx.php?' + urlencode(self.location)),
                                persist=True, channel=self.channel)
            self.timer.register(self)

    def new_location(self, location):
        super().__init__(location)
        r = _http.request('GET', self.url + 'MapClick.php',
                          fields={'lat': location["lat"], 'lon': location["lon"]},
                          headers={'User-Agent': 'urllib3/RPiNWR', 'Accept': '*/*'})

        if r.status == 200:
            ds = r.data.decode('utf-8')

            def f(xp):
                try:
                    return re.search(xp, ds).group(1)
                except Exception:
                    return None

            location.wfo = f("wfo=(\w+)")
            location.fips = f("county=(\w+)")
            location.zone = f("(?:warnzone|zoneid)=(\w+)")
            location.firewxzone = f("firewxzone=(\w+)")

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
                    self.fireEvent(new_message(tm, channel="*"))
        else:
            # TODO log it
            raise Exception("{0:d} {1:s}".format(response.status, response.reason))

    def is_operational(self):
        return self.lastquery < (time.time() - self.timer.interval + 30)


class CapPull(object):
    def __init__(self, config, location):
        self.location = location

    def get_delay_sec(self):
        return 90

    def has_polygons(self):
        return True


class XMPPText(object):
    pass


class SocketText(object):
    pass
