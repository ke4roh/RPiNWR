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
from RPiNWR.SAME import *
from RPiNWR.cache import *
from RPiNWR.VTEC import *
import pickle
import os
from RPiNWR.CommonMessage import new_message
from test_sources import Watcher
from circuits import Component, Debugger
import time


class ScoreWatcher(Component):
    def __init__(self):
        super().__init__()
        self.score = None

    def new_score(self, score):
        self.score = score


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
    123 20:08  SVR --- SVR / 30
    123 20:13  SVR --- SVR / 30
    123 20:18  SVR --- SVR / 30
    123 20:23  SVR --- SVR,SVR / 30
    123 20:28  SVR --- SVR,SVR,SVR / 30
    123 20:33  SVR --- SVR,SVR / 30
    123 20:38  SVR --- SVR,SVR / 30
    123 20:43  SVR --- SVR,SVR / 30
    123 20:48  SVR --- SVR,SVR / 30
    123 20:53  SVR --- SVR,SVR / 30
    123 20:58  SVR --- SVR,SVR / 30
    123 21:03  SVR --- SVR,SVR / 30
    123 21:08  SVR --- SVR / 30
    123 21:13  SVR --- SVR,SVR / 30
    123 21:18  SVR --- SVR,SVR,SVR / 30
    123 21:23  SVR --- SVR,SVR,SVR / 30
    123 21:28  SVR --- SVR,SVR / 30
    123 21:33   --- SVR,SVR / 20
    123 21:38   --- SVR,SVR / 20
    123 21:43   --- SVR,SVR / 20
    123 21:48   --- SVR,SVR / 20
    123 21:53   --- SVR,SVR / 20
    123 21:58   --- SVR / 20
    123 22:03   ---  / 0
    123 22:08   ---  / 0
    123 22:13   --- FFW / 0
    123 22:18   --- FFW / 0
    123 22:23   --- FFW / 0
    123 22:28   --- FFW / 0
    123 22:33   --- FFW / 0
    123 22:38   --- FFW / 0
    123 22:43   --- FFW / 0
    123 22:48   --- FFW / 0
    123 22:53   --- FFW / 0
    123 22:58   --- FFW / 0
    123 23:03   --- FFW / 0
    123 23:08   --- FFW / 0
    123 23:13   --- FFW / 0
    123 23:18   --- FFW / 0
    123 23:23   --- FFW / 0
    123 23:28   --- FFW / 0
    123 23:33   --- FFW / 0
    123 23:38   --- FFW / 0
    123 23:43   --- FFW / 0
    123 23:48   --- FFW / 0
    123 23:53   --- FFW / 0
    123 23:58   --- FFW / 0
    124 00:03   --- FFW / 0
    124 00:08   --- FFW / 0
    124 00:13   --- FFW / 0
    124 00:18   --- FFW / 0
    124 00:23   --- FFW / 0
    124 00:28   --- FFW / 0
    124 00:33   --- FFW / 0
    124 00:38   --- FFW / 0
    124 00:43   --- FFW / 0
    124 00:48   --- FFW / 0
    124 00:53   --- FFW / 0
    124 00:58   --- FFW / 0
    124 01:03   --- FFW / 0
    124 01:08   --- FFW / 0
    124 01:13   ---  / 0
    124 01:18   ---  / 0
    124 01:23   ---  / 0
    124 01:28   ---  / 0
    124 01:33   ---  / 0
    124 01:38   ---  / 0
    124 01:43   ---  / 0
    124 01:48   ---  / 0
    124 01:53   ---  / 0
    124 01:58   ---  / 0
    124 02:03   ---  / 0
    124 02:08   ---  / 0
    124 02:13   ---  / 0
    124 02:18   ---  / 0
    124 02:23   ---  / 0
    124 02:28   ---  / 0
    124 02:33   ---  / 0
    124 02:38   ---  / 0
    124 02:43   ---  / 0
    124 02:48   ---  / 0
    124 02:53   ---  / 0
    124 02:58   ---  / 0
    124 03:03   ---  / 0
    124 03:08   ---  / 0
    124 03:13   ---  / 0
    124 03:18   ---  / 0
    124 03:23   ---  / 0
    124 03:28   ---  / 0
    124 03:33   ---  / 0
    124 03:38   ---  / 0
    124 03:43   ---  / 0
    124 03:48   ---  / 0
    124 03:53   ---  / 0
    124 03:58   ---  / 0
    124 04:03   ---  / 0
    124 04:08   ---  / 0
    124 04:13   ---  / 0
    124 04:18   ---  / 0
    124 04:23   ---  / 0
    124 04:28   ---  / 0
    124 04:33   ---  / 0
    124 04:38   ---  / 0
    124 04:43   ---  / 0
    124 04:48   ---  / 0
    124 04:53   ---  / 0
    124 04:58   ---  / 0
    124 05:03   ---  / 0
    124 05:08   ---  / 0
    124 05:13   ---  / 0
    124 05:18   ---  / 0
    124 05:23   ---  / 0
    124 05:28   ---  / 0
    124 05:33   ---  / 0
    124 05:38   ---  / 0
    124 05:43   ---  / 0
    124 05:48   ---  / 0
    124 05:53   ---  / 0
    124 05:58   ---  / 0
    124 06:03   ---  / 0
    124 06:08   ---  / 0
    124 06:13   ---  / 0
    124 06:18   ---  / 0
    124 06:23   ---  / 0
    124 06:28   ---  / 0
    124 06:33   ---  / 0
    124 06:38   ---  / 0
    124 06:43   ---  / 0
    124 06:48   ---  / 0
    124 06:53   ---  / 0
    124 06:58   ---  / 0
    124 07:03   ---  / 0
    124 07:08   ---  / 0
    124 07:13   ---  / 0
    124 07:18   ---  / 0
    124 07:23   ---  / 0
    124 07:28   ---  / 0
    124 07:33   ---  / 0
    124 07:38   ---  / 0
    124 07:43   ---  / 0
    124 07:48   ---  / 0
    124 07:53   ---  / 0
    124 07:58   ---  / 0
    124 08:03   ---  / 0
    124 08:08   ---  / 0
    124 08:13   ---  / 0
    124 08:18   ---  / 0
    124 08:23   ---  / 0
    124 08:28   ---  / 0
    124 08:33   ---  / 0
    124 08:38   ---  / 0
    124 08:43   ---  / 0
    124 08:48   ---  / 0
    124 08:53   ---  / 0
    124 08:58   ---  / 0
    124 09:03   ---  / 0
    124 09:08   ---  / 0
    124 09:13   ---  / 0
    124 09:18   ---  / 0
    124 09:23   ---  / 0
    124 09:28   ---  / 0
    124 09:33   ---  / 0
    124 09:38   ---  / 0
    124 09:43   ---  / 0
    124 09:48   ---  / 0
    124 09:53   ---  / 0
    124 09:58   ---  / 0
    124 10:03   ---  / 0
    124 10:08   ---  / 0
    124 10:13   ---  / 0
    124 10:18   ---  / 0
    124 10:23   ---  / 0
    124 10:28   ---  / 0
    124 10:33   ---  / 0
    124 10:38   ---  / 0
    124 10:43   ---  / 0
    124 10:48   ---  / 0
    124 10:53   ---  / 0
    124 10:58   ---  / 0
    124 11:03   ---  / 0
    124 11:08   ---  / 0
    124 11:13   ---  / 0
    124 11:18   ---  / 0
    124 11:23   ---  / 0
    124 11:28   ---  / 0
    124 11:33   ---  / 0
    124 11:38   ---  / 0
    124 11:43   ---  / 0
    124 11:48   ---  / 0
    124 11:53   ---  / 0
    124 11:58   ---  / 0
    124 12:03   ---  / 0
    124 12:08   ---  / 0
    124 12:13   ---  / 0
    124 12:18   ---  / 0
    124 12:23   ---  / 0
    124 12:28   ---  / 0
    124 12:33   ---  / 0
    124 12:38   ---  / 0
    124 12:43   ---  / 0
    124 12:48   ---  / 0
    124 12:53   ---  / 0
    124 12:58   ---  / 0
    124 13:03   ---  / 0
    124 13:08   ---  / 0
    124 13:13   ---  / 0
    124 13:18   ---  / 0
    124 13:23   ---  / 0
    124 13:28   ---  / 0
    124 13:33   ---  / 0
    124 13:38   ---  / 0
    124 13:43   ---  / 0
    124 13:48   ---  / 0
    124 13:53   ---  / 0
    124 13:58   ---  / 0
    124 14:03   ---  / 0
    124 14:08   ---  / 0
    124 14:13   ---  / 0
    124 14:18   ---  / 0
    124 14:23   ---  / 0
    124 14:28   ---  / 0
    124 14:33   ---  / 0
    124 14:38   ---  / 0
    124 14:43   ---  / 0
    124 14:48   ---  / 0
    124 14:53   ---  / 0
    124 14:58   ---  / 0
    124 15:03   ---  / 0
    124 15:08   ---  / 0
    124 15:13   ---  / 0
    124 15:18   ---  / 0
    124 15:23   ---  / 0
    124 15:28   ---  / 0
    124 15:33   ---  / 0
    124 15:38   ---  / 0
    124 15:43   ---  / 0
    124 15:48   ---  / 0
    124 15:53   ---  / 0
    124 15:58   ---  / 0
    124 16:03   ---  / 0
    124 16:08   ---  / 0
    124 16:13   ---  / 0
    124 16:18   ---  / 0
    124 16:23   ---  / 0
    124 16:28   ---  / 0
    124 16:33   ---  / 0
    124 16:38   ---  / 0
    124 16:43   ---  / 0
    124 16:48   ---  / 0
    124 16:53   ---  / 0
    124 16:58   ---  / 0
    124 17:03   ---  / 0
    124 17:08   ---  / 0
    124 17:13   ---  / 0
    124 17:18   ---  / 0
    124 17:23   ---  / 0
    124 17:28   ---  / 0
    124 17:33   ---  / 0
    124 17:38   ---  / 0
    124 17:43   ---  / 0
    124 17:48   ---  / 0
    124 17:53   ---  / 0
    124 17:58   ---  / 0
    124 18:03   ---  / 0
    124 18:08   ---  / 0
    124 18:13   ---  / 0
    124 18:18   ---  / 0
    124 18:23   ---  / 0
    124 18:28   ---  / 0
    124 18:33   ---  / 0
    124 18:38   ---  / 0
    124 18:43   ---  / 0
    124 18:48   ---  / 0
    124 18:53   ---  / 0
    124 18:58  SVA ---  / 20
    124 19:03  SVA ---  / 20
    124 19:08  SVA ---  / 20
    124 19:13  SVA ---  / 20
    124 19:18  SVA ---  / 20
    124 19:23  SVA ---  / 20
    124 19:28  SVA ---  / 20
    124 19:33  SVA ---  / 20
    124 19:38  SVA ---  / 20
    124 19:43  SVA ---  / 20
    124 19:48  SVA ---  / 20
    124 19:53  SVA ---  / 20
    124 19:58  SVA ---  / 20
    124 20:03  SVA ---  / 20
    124 20:08  SVA ---  / 20
    124 20:13  SVA --- SVR / 20
    124 20:18  SVA --- SVR / 20
    124 20:23  SVA --- SVR / 20
    124 20:28  SVA --- SVR / 20
    124 20:33  SVA --- SVR / 20
    124 20:38  SVA --- SVR / 20
    124 20:43  SVA --- SVR / 20
    124 20:48  SVA --- SVR,SVR / 20
    124 20:53  SVA --- SVR,SVR / 20
    124 20:58  SVA --- SVR / 20
    124 21:03  SVA --- SVR / 20
    124 21:08  SVA --- SVR / 20
    124 21:13  SVA --- SVR / 20
    124 21:18  SVA --- SVR / 20
    124 21:23  SVR,SVA --- SVR / 30
    124 21:28  SVR,SVA --- SVR / 30
    124 21:33  SVR,SVA --- SVR / 30
    124 21:38  SVR,SVA --- SVR / 30
    124 21:43  SVR,SVA --- SVR / 30
    124 21:48  SVR,SVA ---  / 30
    124 21:53  SVR,SVA ---  / 30
    124 21:58  SVR,SVR,SVA ---  / 30
    124 22:03  SVR,SVR,SVA ---  / 30
    124 22:08  TOR,SVR,SVA ---  / 40
    124 22:13  TOR,SVR,SVA ---  / 40
    124 22:18  TOR,SVR,SVA ---  / 40
    124 22:23  SVR,SVA ---  / 30
    124 22:28  SVR,SVA ---  / 30
    124 22:33  SVR,SVA ---  / 30
    124 22:38  SVR,SVR,SVA ---  / 30
    124 22:43  SVR,SVR,SVA ---  / 30
    124 22:48  SVR,SVR,SVA ---  / 30
    124 22:53  SVR,SVR,SVA ---  / 30
    124 22:58  SVR,SVA ---  / 30
    124 23:03  SVR,SVA ---  / 30
    124 23:08  SVR,SVA ---  / 30
    124 23:13  SVR,SVA ---  / 30
    124 23:18  SVR,SVA ---  / 30
    124 23:23  SVR,SVA ---  / 30
    124 23:28  SVR,SVA ---  / 30
    124 23:33  SVR,SVA ---  / 30
    124 23:38  SVA ---  / 20
    124 23:43  SVA --- SVR / 20
    124 23:48  SVA --- SVR / 20
    124 23:53  SVA --- SVR / 20
    124 23:58  SVA --- SVR / 20
    125 00:03  SVA --- SVR / 20
    125 00:08  SVA --- SVR / 20
    125 00:13  SVA --- SVR,SVR / 20
    125 00:18  SVA --- SVR,SVR / 20
    125 00:23  SVA --- SVR,SVR / 20
    125 00:28  SVA --- SVR,SVR / 20
    125 00:33  SVA --- SVR,SVR,SVR / 20
    125 00:38  SVA --- SVR,SVR,SVR / 20
    125 00:43  SVA --- SVR,SVR / 20
    125 00:48  SVA --- SVR,SVR / 20
    125 00:53  SVA --- SVR,SVR / 20
    125 00:58   --- SVR,SVR / 20
    125 01:03   --- SVR,SVR / 20
    125 01:08   --- SVR,SVR / 20
    125 01:13   --- SVR / 20
    125 01:18   --- SVR / 20
    125 01:23   --- SVR / 20
    125 01:28   --- SVR / 20
    125 01:33   ---  / 0
    125 01:38   ---  / 0
    125 01:43   ---  / 0
    125 01:48   ---  / 0
    125 01:53  SVR ---  / 30
    125 01:58  SVR ---  / 30
    125 02:03  SVR ---  / 30
    125 02:08  SVR ---  / 30
    125 02:13  SVR ---  / 30
    125 02:18  SVR --- SVR  / 30
    125 02:23  SVR --- SVR / 30
    125 02:28  SVR --- SVR / 30
    125 02:33  SVR --- SVR / 30
    125 02:38  SVR --- SVR / 30
    125 02:43  SVR --- SVR / 30
    125 02:48  SVR --- SVR / 30
    125 02:53   --- SVR / 20
    125 02:58   --- SVR / 20
    125 03:03   --- SVR / 20
    125 03:08   --- SVR / 20
    125 03:13   --- SVR / 20
    125 03:18   ---  / 0
    125 03:23   ---  / 0
    125 03:28   ---  / 0
    125 03:33   ---  / 0
    """.split("\n")

        t = 0
        self.manager = buf = MessageCache((35.73, -78.85), "037183", default_SAME_sort, clock=lambda: t)
        watcher = Watcher()
        scorewatcher = ScoreWatcher()
        (buf + watcher + scorewatcher + Debugger()).start()
        watcher.wait_for_start()

        # Iterate through this storm system 5 minutes at a time
        aix = 0
        eix = 0
        for t in range(int(alerts[0].get_start_time_sec()),
                       int(alerts[-1].get_start_time_sec() + alerts[-1].get_duration_sec() + 1000),
                       300):
            change = False
            while aix < len(alerts) and alerts[aix].get_start_time_sec() <= t:
                change = True
                yield buf.callEvent(new_message(alerts[aix]))
                aix += 1
            if not change:
                yield buf.callEvent(update_score())

            ptime = time.strftime("%j %H:%M  ", time.gmtime(t))
            here = buf.get_active_messages()
            elsewhere = buf.get_active_messages(here=False)
            stat = ptime + ",".join([x.get_event_type() for x in here]) \
                   + " --- " + ",".join([x.get_event_type() for x in elsewhere]) \
                   + " / " + str(scorewatcher.score)

            self.assertEqual(expected[eix].strip(), stat.strip())
            eix += 1

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
        self.manager = buf = MessageCache((40.321909, -102.718192), "008125", default_VTEC_sort, clock=lambda: t)
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
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "kgld.cap.p"), "rb") as f:
            alerts = pickle.load(f)
        valerts = list(filter(lambda v: v.event_id == "KGLD.TO.W.0028", [item for sublist in [c.vtec for a, c in alerts]
                                                                         for item in sublist]))

        buf = EventMessageGroup()

        buf.add_message(valerts[0])
        self.assertTrue(buf.is_effective((40.321909, -102.718192), "008125", True, lambda: valerts[0].published))
        self.assertFalse(buf.is_effective((40.321909, -102.718192), "008125", False, lambda: valerts[0].published))

    def test_not_here_sans_polygon(self):
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "kgld.cap.p"), "rb") as f:
            alerts = pickle.load(f)
        valerts = list(filter(lambda v: v.event_id == "KGLD.TO.A.0206", [item for sublist in [c.vtec for a, c in alerts]
                                                                         for item in sublist]))

        buf = EventMessageGroup()

        buf.add_message(valerts[0])
        self.assertTrue(buf.is_effective((40.321909, -102.718192), "008125", True, lambda: valerts[0].published))
        self.assertFalse(buf.is_effective((40.321909, -102.718192), "008125", False, lambda: valerts[0].published))
