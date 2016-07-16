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

class TestCache(unittest.TestCase):
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

        expected = """123 20:03  SVR --- SVR
    123 20:08  SVR --- SVR
    123 20:13  SVR --- SVR
    123 20:18  SVR --- SVR
    123 20:23  SVR --- SVR,SVR
    123 20:28  SVR --- SVR,SVR,SVR
    123 20:33  SVR --- SVR,SVR
    123 20:38  SVR --- SVR,SVR
    123 20:43  SVR --- SVR,SVR
    123 20:48  SVR --- SVR,SVR
    123 20:53  SVR --- SVR,SVR
    123 20:58  SVR --- SVR,SVR
    123 21:03  SVR --- SVR,SVR
    123 21:08  SVR --- SVR
    123 21:13  SVR --- SVR,SVR
    123 21:18  SVR --- SVR,SVR,SVR
    123 21:23  SVR --- SVR,SVR,SVR
    123 21:28  SVR --- SVR,SVR
    123 21:33   --- SVR,SVR
    123 21:38   --- SVR,SVR
    123 21:43   --- SVR,SVR
    123 21:48   --- SVR,SVR
    123 21:53   --- SVR,SVR
    123 21:58   --- SVR
    123 22:03   ---
    123 22:08   ---
    123 22:13   --- FFW
    123 22:18   --- FFW
    123 22:23   --- FFW
    123 22:28   --- FFW
    123 22:33   --- FFW
    123 22:38   --- FFW
    123 22:43   --- FFW
    123 22:48   --- FFW
    123 22:53   --- FFW
    123 22:58   --- FFW
    123 23:03   --- FFW
    123 23:08   --- FFW
    123 23:13   --- FFW
    123 23:18   --- FFW
    123 23:23   --- FFW
    123 23:28   --- FFW
    123 23:33   --- FFW
    123 23:38   --- FFW
    123 23:43   --- FFW
    123 23:48   --- FFW
    123 23:53   --- FFW
    123 23:58   --- FFW
    124 00:03   --- FFW
    124 00:08   --- FFW
    124 00:13   --- FFW
    124 00:18   --- FFW
    124 00:23   --- FFW
    124 00:28   --- FFW
    124 00:33   --- FFW
    124 00:38   --- FFW
    124 00:43   --- FFW
    124 00:48   --- FFW
    124 00:53   --- FFW
    124 00:58   --- FFW
    124 01:03   --- FFW
    124 01:08   --- FFW
    124 01:13   ---
    124 01:18   ---
    124 01:23   ---
    124 01:28   ---
    124 01:33   ---
    124 01:38   ---
    124 01:43   ---
    124 01:48   ---
    124 01:53   ---
    124 01:58   ---
    124 02:03   ---
    124 02:08   ---
    124 02:13   ---
    124 02:18   ---
    124 02:23   ---
    124 02:28   ---
    124 02:33   ---
    124 02:38   ---
    124 02:43   ---
    124 02:48   ---
    124 02:53   ---
    124 02:58   ---
    124 03:03   ---
    124 03:08   ---
    124 03:13   ---
    124 03:18   ---
    124 03:23   ---
    124 03:28   ---
    124 03:33   ---
    124 03:38   ---
    124 03:43   ---
    124 03:48   ---
    124 03:53   ---
    124 03:58   ---
    124 04:03   ---
    124 04:08   ---
    124 04:13   ---
    124 04:18   ---
    124 04:23   ---
    124 04:28   ---
    124 04:33   ---
    124 04:38   ---
    124 04:43   ---
    124 04:48   ---
    124 04:53   ---
    124 04:58   ---
    124 05:03   ---
    124 05:08   ---
    124 05:13   ---
    124 05:18   ---
    124 05:23   ---
    124 05:28   ---
    124 05:33   ---
    124 05:38   ---
    124 05:43   ---
    124 05:48   ---
    124 05:53   ---
    124 05:58   ---
    124 06:03   ---
    124 06:08   ---
    124 06:13   ---
    124 06:18   ---
    124 06:23   ---
    124 06:28   ---
    124 06:33   ---
    124 06:38   ---
    124 06:43   ---
    124 06:48   ---
    124 06:53   ---
    124 06:58   ---
    124 07:03   ---
    124 07:08   ---
    124 07:13   ---
    124 07:18   ---
    124 07:23   ---
    124 07:28   ---
    124 07:33   ---
    124 07:38   ---
    124 07:43   ---
    124 07:48   ---
    124 07:53   ---
    124 07:58   ---
    124 08:03   ---
    124 08:08   ---
    124 08:13   ---
    124 08:18   ---
    124 08:23   ---
    124 08:28   ---
    124 08:33   ---
    124 08:38   ---
    124 08:43   ---
    124 08:48   ---
    124 08:53   ---
    124 08:58   ---
    124 09:03   ---
    124 09:08   ---
    124 09:13   ---
    124 09:18   ---
    124 09:23   ---
    124 09:28   ---
    124 09:33   ---
    124 09:38   ---
    124 09:43   ---
    124 09:48   ---
    124 09:53   ---
    124 09:58   ---
    124 10:03   ---
    124 10:08   ---
    124 10:13   ---
    124 10:18   ---
    124 10:23   ---
    124 10:28   ---
    124 10:33   ---
    124 10:38   ---
    124 10:43   ---
    124 10:48   ---
    124 10:53   ---
    124 10:58   ---
    124 11:03   ---
    124 11:08   ---
    124 11:13   ---
    124 11:18   ---
    124 11:23   ---
    124 11:28   ---
    124 11:33   ---
    124 11:38   ---
    124 11:43   ---
    124 11:48   ---
    124 11:53   ---
    124 11:58   ---
    124 12:03   ---
    124 12:08   ---
    124 12:13   ---
    124 12:18   ---
    124 12:23   ---
    124 12:28   ---
    124 12:33   ---
    124 12:38   ---
    124 12:43   ---
    124 12:48   ---
    124 12:53   ---
    124 12:58   ---
    124 13:03   ---
    124 13:08   ---
    124 13:13   ---
    124 13:18   ---
    124 13:23   ---
    124 13:28   ---
    124 13:33   ---
    124 13:38   ---
    124 13:43   ---
    124 13:48   ---
    124 13:53   ---
    124 13:58   ---
    124 14:03   ---
    124 14:08   ---
    124 14:13   ---
    124 14:18   ---
    124 14:23   ---
    124 14:28   ---
    124 14:33   ---
    124 14:38   ---
    124 14:43   ---
    124 14:48   ---
    124 14:53   ---
    124 14:58   ---
    124 15:03   ---
    124 15:08   ---
    124 15:13   ---
    124 15:18   ---
    124 15:23   ---
    124 15:28   ---
    124 15:33   ---
    124 15:38   ---
    124 15:43   ---
    124 15:48   ---
    124 15:53   ---
    124 15:58   ---
    124 16:03   ---
    124 16:08   ---
    124 16:13   ---
    124 16:18   ---
    124 16:23   ---
    124 16:28   ---
    124 16:33   ---
    124 16:38   ---
    124 16:43   ---
    124 16:48   ---
    124 16:53   ---
    124 16:58   ---
    124 17:03   ---
    124 17:08   ---
    124 17:13   ---
    124 17:18   ---
    124 17:23   ---
    124 17:28   ---
    124 17:33   ---
    124 17:38   ---
    124 17:43   ---
    124 17:48   ---
    124 17:53   ---
    124 17:58   ---
    124 18:03   ---
    124 18:08   ---
    124 18:13   ---
    124 18:18   ---
    124 18:23   ---
    124 18:28   ---
    124 18:33   ---
    124 18:38   ---
    124 18:43   ---
    124 18:48   ---
    124 18:53   ---
    124 18:58  SVA ---
    124 19:03  SVA ---
    124 19:08  SVA ---
    124 19:13  SVA ---
    124 19:18  SVA ---
    124 19:23  SVA ---
    124 19:28  SVA ---
    124 19:33  SVA ---
    124 19:38  SVA ---
    124 19:43  SVA ---
    124 19:48  SVA ---
    124 19:53  SVA ---
    124 19:58  SVA ---
    124 20:03  SVA ---
    124 20:08  SVA ---
    124 20:13  SVA --- SVR
    124 20:18  SVA --- SVR
    124 20:23  SVA --- SVR
    124 20:28  SVA --- SVR
    124 20:33  SVA --- SVR
    124 20:38  SVA --- SVR
    124 20:43  SVA --- SVR
    124 20:48  SVA --- SVR,SVR
    124 20:53  SVA --- SVR,SVR
    124 20:58  SVA --- SVR
    124 21:03  SVA --- SVR
    124 21:08  SVA --- SVR
    124 21:13  SVA --- SVR
    124 21:18  SVA --- SVR
    124 21:23  SVR,SVA --- SVR
    124 21:28  SVR,SVA --- SVR
    124 21:33  SVR,SVA --- SVR
    124 21:38  SVR,SVA --- SVR
    124 21:43  SVR,SVA --- SVR
    124 21:48  SVR,SVA ---
    124 21:53  SVR,SVA ---
    124 21:58  SVR,SVR,SVA ---
    124 22:03  SVR,SVR,SVA ---
    124 22:08  TOR,SVR,SVA ---
    124 22:13  TOR,SVR,SVA ---
    124 22:18  TOR,SVR,SVA ---
    124 22:23  SVR,SVA ---
    124 22:28  SVR,SVA ---
    124 22:33  SVR,SVA ---
    124 22:38  SVR,SVR,SVA ---
    124 22:43  SVR,SVR,SVA ---
    124 22:48  SVR,SVR,SVA ---
    124 22:53  SVR,SVR,SVA ---
    124 22:58  SVR,SVA ---
    124 23:03  SVR,SVA ---
    124 23:08  SVR,SVA ---
    124 23:13  SVR,SVA ---
    124 23:18  SVR,SVA ---
    124 23:23  SVR,SVA ---
    124 23:28  SVR,SVA ---
    124 23:33  SVR,SVA ---
    124 23:38  SVA ---
    124 23:43  SVA --- SVR
    124 23:48  SVA --- SVR
    124 23:53  SVA --- SVR
    124 23:58  SVA --- SVR
    125 00:03  SVA --- SVR
    125 00:08  SVA --- SVR
    125 00:13  SVA --- SVR,SVR
    125 00:18  SVA --- SVR,SVR
    125 00:23  SVA --- SVR,SVR
    125 00:28  SVA --- SVR,SVR
    125 00:33  SVA --- SVR,SVR,SVR
    125 00:38  SVA --- SVR,SVR,SVR
    125 00:43  SVA --- SVR,SVR
    125 00:48  SVA --- SVR,SVR
    125 00:53  SVA --- SVR,SVR
    125 00:58   --- SVR,SVR
    125 01:03   --- SVR,SVR
    125 01:08   --- SVR,SVR
    125 01:13   --- SVR
    125 01:18   --- SVR
    125 01:23   --- SVR
    125 01:28   --- SVR
    125 01:33   ---
    125 01:38   ---
    125 01:43   ---
    125 01:48   ---
    125 01:53  SVR ---
    125 01:58  SVR ---
    125 02:03  SVR ---
    125 02:08  SVR ---
    125 02:13  SVR ---
    125 02:18  SVR --- SVR
    125 02:23  SVR --- SVR
    125 02:28  SVR --- SVR
    125 02:33  SVR --- SVR
    125 02:38  SVR --- SVR
    125 02:43  SVR --- SVR
    125 02:48  SVR --- SVR
    125 02:53   --- SVR
    125 02:58   --- SVR
    125 03:03   --- SVR
    125 03:08   --- SVR
    125 03:13   --- SVR
    125 03:18   ---
    125 03:23   ---
    125 03:28   ---
    125 03:33   ---
    """.split("\n")

        buf = MessageCache((35.73, -78.85), "037183", default_SAME_sort)
        # Iterate through this storm system 5 minutes at a time
        aix = 0
        eix = 0
        for t in range(int(alerts[0].get_start_time_sec()),
                       int(alerts[-1].get_start_time_sec() + alerts[-1].get_duration_sec() + 1000),
                       300):
            while aix < len(alerts) and alerts[aix].get_start_time_sec() <= t:
                buf.add_message(alerts[aix])
                aix += 1

            ptime = time.strftime("%j %H:%M  ", time.gmtime(t))
            here = buf.get_active_messages(when=t)
            elsewhere = buf.get_active_messages(when=t, here=False)
            stat = ptime + ",".join([x.get_event_type() for x in here]) \
                   + " --- " + ",".join([x.get_event_type() for x in elsewhere])
            self.assertEqual(expected[eix].strip(), stat.strip())
            eix += 1

    def test_net_alerts(self):
        expected = """146 01:24  KGLD.TO.W.0028 --- KGLD.TO.A.0204
146 01:26  KGLD.TO.W.0028 --- KGLD.TO.A.0204
146 01:34  KGLD.TO.W.0028 --- KGLD.TO.A.0204
146 01:36  KGLD.TO.W.0028 --- KGLD.TO.A.0204
146 01:45  KGLD.TO.W.0029 --- KGLD.TO.A.0204
146 02:02   --- KGLD.TO.W.0029,KGLD.TO.A.0204
146 02:13  KGLD.TO.A.0206 --- KGLD.TO.W.0029,KGLD.TO.A.0204
146 02:17  KGLD.TO.A.0206 --- KGLD.TO.W.0030,KGLD.TO.A.0204
146 02:33  KGLD.TO.A.0206 --- KGLD.TO.W.0030,KGLD.TO.A.0204
146 02:33  KGLD.TO.A.0206 --- KGLD.TO.W.0030,KGLD.TO.A.0204
146 02:46  KGLD.TO.A.0206 --- KGLD.TO.W.0031,KGLD.TO.A.0204
146 03:04  KGLD.TO.A.0206 --- KGLD.TO.W.0031,KGLD.TO.A.0204
146 03:13  KGLD.TO.A.0206 --- KGLD.TO.W.0031,KGLD.TO.A.0204
146 03:16  KGLD.TO.A.0206 --- KGLD.TO.W.0032,KGLD.TO.A.0204
146 03:39  KGLD.TO.A.0206 --- KGLD.TO.W.0032,KGLD.TO.A.0204
146 03:50  KGLD.TO.A.0206 --- KGLD.TO.W.0032,KGLD.TO.A.0204
146 04:05  KGLD.TO.A.0206 --- KGLD.TO.A.0204
146 04:33  KGLD.TO.A.0206 --- KGLD.SV.W.0094,KGLD.TO.A.0204
146 04:55  KGLD.TO.A.0206 --- KGLD.SV.W.0094,KGLD.TO.A.0204
146 04:56  KGLD.TO.A.0206 --- KGLD.SV.W.0094,KGLD.TO.A.0204
146 05:09  KGLD.TO.A.0206 --- KGLD.SV.W.0094
146 05:10  KGLD.TO.A.0206 --- KGLD.SV.W.0094""".split("\n")
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "kgld.cap.p"), "rb") as f:
            alerts = pickle.load(f)

        # https://mesonet.agron.iastate.edu/vtec/#2016-O-NEW-KGLD-TO-W-0029/USCOMP-N0Q-201605250145

        buf = MessageCache((40.321909, -102.718192), "008125", default_VTEC_sort)

        aix = eix = 0
        for t in range(alerts[0][0], alerts[-1][0] + 2):
            delta = False
            while aix < len(alerts) and alerts[aix][0] <= t:
                for v in alerts[aix][1].vtec:
                    buf.add_message(v)
                aix += 1
                delta = True
            if delta:
                here = buf.get_active_messages(when=t)
                display_time = time.strftime("%j %H:%M  ", time.gmtime(t))
                try:
                    elsewhere = buf.get_active_messages(when=t, here=False)
                except TypeError:
                    # TODO fix the comparator to handle null times
                    print([str(x) for x in filter(lambda m: m.is_effective(t), buf._MessageCache__messages.values())])
                    raise
                line = display_time + ",".join([x.get_event_id() for x in here]) \
                       + " --- " + ",".join([x.get_event_id() for x in elsewhere])
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
        self.assertTrue(buf.is_effective((40.321909, -102.718192), "008125", True, valerts[0].published))
        self.assertFalse(buf.is_effective((40.321909, -102.718192), "008125", False, valerts[0].published))

    def test_not_here_sans_polygon(self):
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "kgld.cap.p"), "rb") as f:
            alerts = pickle.load(f)
        valerts = list(filter(lambda v: v.event_id == "KGLD.TO.A.0206", [item for sublist in [c.vtec for a, c in alerts]
                                                                         for item in sublist]))

        buf = EventMessageGroup()

        buf.add_message(valerts[0])
        self.assertTrue(buf.is_effective((40.321909, -102.718192), "008125", True, valerts[0].published))
        self.assertFalse(buf.is_effective((40.321909, -102.718192), "008125", False, valerts[0].published))
