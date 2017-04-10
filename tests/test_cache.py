# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
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

import unittest
from RPiNWR.messages import *
import pickle
import os
from test_sources import Watcher
from circuits import Component, Debugger, Event, BaseComponent, handler
import time
import re


class ScoreWatcher(Component):
    def __init__(self):
        super().__init__()
        self.score = None

    def new_score(self, score, msg):
        self.score = score


class MockAlerter(Component):
    """
    This component injects messages for testing purposes and keeps a clock.
    """

    def __init__(self, alerts):
        self.alerts = alerts
        self.clock = alerts[0].get_start_time_sec()  # this will report the time of the latest event
        self.aix = 0
        self.eix = 0
        super().__init__()

    def generate_events(self, event):
        event.reduce_time_left(0)
        while self.aix < len(self.alerts) and self.alerts[self.aix].get_start_time_sec() <= self.clock:
            self.fire(new_message(self.alerts[self.aix]))
            self.aix += 1
        self.clock += 15  # these events are marked by the minute, so 15 sec is 4x as fast as necessary, but it needs
        # to be smaller slices so that there are enough trips through generate_events to update score etc.
        if self.clock > self.alerts[-1].get_end_time_sec() + 300:
            self.fire(shutdown())

    def _time(self):
        return self.clock


class shutdown(Event):
    """shut down the manager"""


class CacheMonitor(BaseComponent):
    """
    This component keeps a record of the active messages in the buffer with each change
    """

    def __init__(self, cache):
        self.cache = cache
        self.clock = cache._MessageCache__time
        self.stats = []
        self.score = float("nan")
        super().__init__()

    @handler("update_score", priority=-1000)
    def update_score(self, msg):
        ptime = time.strftime("%j %H:%M  ", time.gmtime(self.clock()))
        here = self.cache.get_active_messages()
        elsewhere = self.cache.get_active_messages(here=False)
        stat = ptime + ",".join([x.get_event_type() for x in here]) \
               + " --- " + ",".join([x.get_event_type() for x in elsewhere]) \
               + " / " + str(self.score)
        if len(self.stats) and self.stats[-1].startswith(ptime):
            self.stats[-1] = stat.strip()
        else:
            self.stats.append(stat.strip())

    @handler("new_score")
    def new_score(self, score, msg):
        self.score = score
        self.update_score(msg)

    @handler("shutdown")
    def shutdown(self):
        self.stop()


class TestCache(unittest.TestCase):
    def setUp(self):
        self.manager = None

    def tearDown(self):
        if self.manager is not None:
            self.manager.stop()
            self.manager = None

    def test_buffer_for_radio_against_storm_system(self):
        # Test to see that the correct events are reported in priority order as a storm progresses
        # This test is a little long in this file, but it's somewhat readable.
        alerts = [SAMEMessage("WXL58", x) for x in [
            "-WXR-SVR-037183+0045-1232003-KRAH/NWS-",
            "-WXR-SVR-037151+0030-1232003-KRAH/NWS-",
            "-WXR-SVR-037037+0045-1232023-KRAH/NWS-",
            "-WXR-SVR-037001-037151+0100-1232028-KRAH/NWS-",
            "-WXR-SVR-037069-037077-037183+0045-1232045-KRAH/NWS-",
            "-WXR-SVR-037001+0045-1232110-KRAH/NWS-",
            "-WXR-SVR-037069-037181-037185+0045-1232116-KRAH/NWS-",
            "-WXR-FFW-037125+0300-1232209-KRAH/NWS-",
            "-WXR-SVA-037001-037037-037063-037069-037077-037085-037101-037105-037125-037135-037145-037151-037181-037183-037185+0600-1241854-KRAH/NWS-",
            "-WXR-SVR-037001-037037-037151+0045-1242011-KRAH/NWS-",
            "-WXR-SVR-037001-037037-037135+0100-1242044-KRAH/NWS-",
            "-WXR-SVR-037037-037063-037135-037183+0045-1242120-KRAH/NWS-",
            "-WXR-SVR-037183+0100-1242156-KRAH/NWS-",
            "-WXR-TOR-037183+0015-1242204-KRAH/NWS-",
            "-WXR-SVR-037101-037183+0100-1242235-KRAH/NWS-",
            "-WXR-SVR-037151+0100-1242339-KRAH/NWS-",
            "-WXR-SVR-037101+0100-1250011-KRAH/NWS-",
            "-WXR-SVR-037125-037151+0100-1250029-KRAH/NWS-",
            "-WXR-SVR-037085-037105-037183+0100-1250153-KRAH/NWS-",
            "-WXR-SVR-037085-037101+0100-1250218-KRAH/NWS-"
        ]]

        expected = """123 20:03  SVR --- SVR / 30
            123 20:23  SVR --- SVR,SVR / 30
            123 20:28  SVR --- SVR,SVR,SVR / 30
            123 20:33  SVR --- SVR,SVR / 30
            123 20:45  SVR,SVR --- SVR,SVR / 30
            123 20:48  SVR --- SVR,SVR / 30
            123 21:08  SVR --- SVR / 30
            123 21:10  SVR --- SVR,SVR / 30
            123 21:16  SVR --- SVR,SVR,SVR / 30
            123 21:28  SVR --- SVR,SVR / 30
            123 21:30   --- SVR,SVR / 20
            123 21:55   --- SVR / 20
            123 22:01   ---  / 0
            123 22:09   --- FFW / 0
            124 01:09   ---  / 0
            124 18:54  SVA ---  / 20
            124 20:11  SVA --- SVR / 20
            124 20:44  SVA --- SVR,SVR / 20
            124 20:56  SVA --- SVR / 20
            124 21:20  SVR,SVA --- SVR / 30
            124 21:44  SVR,SVA ---  / 30
            124 21:56  SVR,SVR,SVA ---  / 30
            124 22:04  TOR,SVR,SVR,SVA ---  / 40
            124 22:05  TOR,SVR,SVA ---  / 40
            124 22:19  SVR,SVA ---  / 30
            124 22:35  SVR,SVR,SVA ---  / 30
            124 22:56  SVR,SVA ---  / 30
            124 23:35  SVA ---  / 20
            124 23:39  SVA --- SVR / 20
            125 00:11  SVA --- SVR,SVR / 20
            125 00:29  SVA --- SVR,SVR,SVR / 20
            125 00:39  SVA --- SVR,SVR / 20
            125 00:54   --- SVR,SVR / 20
            125 01:11   --- SVR / 20
            125 01:29   ---  / 0
            125 01:53  SVR ---  / 30
            125 02:18  SVR --- SVR / 30
            125 02:53   --- SVR / 20
            125 03:18   ---  / 0""".split("\n")

        alerter = MockAlerter(alerts)
        buf = MessageCache({'lat': 35.73, 'lon': -78.85, 'fips6': "037183"},
                           by_score_and_time, clock=alerter._time)
        self.manager = cachemon = CacheMonitor(buf)
        (cachemon + buf + alerter + Debugger()).run()
        self.assertEquals(len(expected), len(cachemon.stats), cachemon.stats)
        for i in range(0, len(expected)):
            self.assertEquals(expected[i].strip(), cachemon.stats[i].strip())


    def test_net_alerts(self):
        # This is more activity than we'd see in a regular setup because it considers every severe thunderstorm
        # and tornado watch nationwide, but that's because those are issued by the Storm Prediction Center from
        # KWNS, so it is harder to filter them for the immediate area when retrieved from a national sample.
        expected = """146 01:24  KGLD.TO.W.0028,TO.A.0206 --- TO.A.0204,TO.A.0207 / 45
146 01:26  KGLD.TO.W.0028,TO.A.0206 --- TO.A.0204,TO.A.0207 / 45
146 01:34  KGLD.TO.W.0028,TO.A.0206 --- TO.A.0204,TO.A.0207 / 45
146 01:36  KGLD.TO.W.0028,TO.A.0206 --- TO.A.0204,TO.A.0207 / 45
146 01:45  KGLD.TO.W.0029,TO.A.0206 --- TO.A.0204,TO.A.0207 / 45
146 02:02  TO.A.0206 --- KGLD.TO.W.0029,TO.A.0204,TO.A.0207 / 35
146 02:13  TO.A.0206 --- KGLD.TO.W.0029,TO.A.0204,TO.A.0207 / 35
146 02:17  TO.A.0206 --- KGLD.TO.W.0030,TO.A.0204,TO.A.0207 / 35
146 02:33  TO.A.0206 --- KGLD.TO.W.0030,TO.A.0204,TO.A.0207 / 35
146 02:33  TO.A.0206 --- KGLD.TO.W.0030,TO.A.0204,TO.A.0207 / 35
146 03:10  TO.A.0206 --- SV.A.0208,TO.A.0204,TO.A.0207 / 30
146 03:14  TO.A.0206 --- SV.A.0208,TO.A.0204,TO.A.0207 / 30
146 03:19  TO.A.0206 --- SV.A.0208,TO.A.0204,TO.A.0207 / 30
146 04:05  TO.A.0206 --- SV.A.0208,TO.A.0204,TO.A.0207 / 30
146 04:12  TO.A.0206 --- SV.A.0208,TO.A.0204,TO.A.0207 / 30
146 04:33  TO.A.0206 --- KGLD.SV.W.0094,SV.A.0208,TO.A.0204,TO.A.0207 / 30
146 04:44  TO.A.0206 --- KGLD.SV.W.0094,SV.A.0208,TO.A.0204,TO.A.0207 / 30
146 04:55  TO.A.0206 --- KGLD.SV.W.0094,SV.A.0208,TO.A.0204,TO.A.0207 / 30
146 04:56  TO.A.0206 --- KGLD.SV.W.0094,SV.A.0208,TO.A.0204,TO.A.0207 / 30
146 05:09  TO.A.0206 --- KGLD.SV.W.0094,SV.A.0208,TO.A.0207 / 30
146 05:10  TO.A.0206 --- KGLD.SV.W.0094,SV.A.0208,TO.A.0207 / 30""".split("\n")
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "kddc_kgld_kwns.cap.p"), "rb") as f:
            alerts = pickle.load(f)

        # https://mesonet.agron.iastate.edu/vtec/#2016-O-NEW-KGLD-TO-W-0029/USCOMP-N0Q-201605250145

        t = 0
        self.manager = buf = MessageCache({"lat": 40.321909, "lon": -102.718192, "fips6": "008125"},
                                          default_VTEC_sort, clock=lambda: t)
        watcher = Watcher()
        scorewatcher = ScoreWatcher()
        (buf + watcher + scorewatcher + Debugger()).start()
        watcher.wait_for_start()

        aix = eix = 0
        for t in range(alerts[0][0], alerts[-1][0] + 2):
            delta = False
            while aix < len(alerts) and alerts[aix][0] <= t:
                # This filters for messages from KGLD (Goodland, KS) or the Storm Prediction Center,
                # And for messages for Kansas and Colorado only
                for v in filter(lambda x: x.office_id in ["KGLD", "KWNS"] and
                        len(list(filter(lambda f: f.startswith("020") or f.startswith("008"), x.container.FIPS6))),
                                alerts[aix][1].vtec):
                    yield buf.callEvent(new_message(v))
                    delta = True
                aix += 1
            if delta:
                here = buf.get_active_messages()
                display_time = time.strftime("%j %H:%M  ", time.gmtime(t))
                try:
                    elsewhere = buf.get_active_messages(here=False)
                except TypeError:
                    print([str(x) for x in filter(lambda m: m.is_effective(t), buf._MessageCache__messages.values())])
                    raise
                line = display_time + ",".join([x.get_event_id() for x in here]) \
                       + " --- " + ",".join([x.get_event_id() for x in elsewhere]) \
                       + " / " + str(scorewatcher.score)
                # print(line)
                self.assertEqual(expected[eix], line)
                eix += 1

        self.assertIsNot(0, eix, 'need assertions')

    def test_not_here_with_polygon(self):
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "kddc_kgld_kwns.cap.p"), "rb") as f:
            alerts = pickle.load(f)
        valerts = list(filter(lambda v: v.event_id == "KGLD.TO.W.0028", [item for sublist in [c.vtec for a, c in alerts]
                                                                         for item in sublist]))

        buf = EventMessageGroup()

        buf.add_message(valerts[0])
        self.assertTrue(buf.is_effective((40.321909, -102.718192), "008125", True, lambda: valerts[0].published))
        self.assertFalse(buf.is_effective((40.321909, -102.718192), "008125", False, lambda: valerts[0].published))

    def test_not_here_sans_polygon(self):
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "kddc_kgld_kwns.cap.p"), "rb") as f:
            alerts = pickle.load(f)
        valerts = list(filter(lambda v: v.event_id == "TO.A.0206",
                              [item for sublist in [c.vtec for a, c in alerts] for item in sublist]))

        buf = EventMessageGroup()

        buf.add_message(valerts[0])
        self.assertTrue(buf.is_effective((40.321909, -102.718192), "008125", True, lambda: valerts[0].published))
        self.assertFalse(buf.is_effective((40.321909, -102.718192), "008125", False, lambda: valerts[0].published))
