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
from RPiNWR.VTEC import *
import pickle
from RPiNWR.cache import EventMessageGroup
import os


class TestVTEC(unittest.TestCase):
    def testPVTEC(self):
        v = PrimaryVTEC('/O.NEW.KGLD.TO.W.0021.160522T0039Z-160522T0115Z/')
        self.assertEqual('KGLD.TO.W.0021', v.event_id)
        self.assertEqual('NEW', v.action)
        self.assertEqual('O', v.product_class)
        self.assertEqual('KGLD', v.office_id)
        self.assertEqual('TO', v.phenomenon)
        self.assertEqual('W', v.significance)
        self.assertEqual('0021', v.tracking_number)
        self.assertEqual(1463877540.0, v.start_time)
        self.assertEqual(1463879700.0, v.end_time)

    def testHVTEC(self):
        v = HyrdologicVTEC('/SRAW4.1.ER.160521T2100Z.160522T1800Z.160524T1200Z.NR/',
                           PrimaryVTEC('/O.EXT.KCYS.FL.W.0011.160521T2100Z-160524T1800Z/'))
        self.assertEqual('SRAW4', v.nwsli)
        self.assertEqual('1', v.severity)
        self.assertEqual('ER', v.immediate_cause)
        self.assertEqual(1463864400.0, v.start_time)
        self.assertEqual(1463940000.0, v.crest_time)
        self.assertEqual(1464091200.0, v.end_time)
        self.assertEqual('NR', v.flood_record)
        self.assertEqual('SRAW4.1.ER.160521T2100Z', v.event_id)

    def testFactoryFLW(self):
        v = VTEC.VTEC("""/O.NEW.KHGX.FL.W.0133.160520T2325Z-160522T1325Z/
/EDNT2.1.ER.160520T2325Z.160521T1200Z.160522T0125Z.NO/""")
        self.assertEqual(1, len(v))
        self.assertEqual('KHGX.FL.W.0133', v[0].event_id)
        self.assertEqual(1, len(v[0].hydrologic_vtec))
        self.assertEqual('EDNT2.1.ER.160520T2325Z', v[0].hydrologic_vtec[0].event_id)

    def testFactoryCANNEW(self):
        v = VTEC.VTEC("""/O.CAN.KALY.SN.Y.0011.040519T1600Z-050620T0300Z/
/O.NEW.KALY.WW.Y.0023.040519T1600Z-040520T0300Z/""")
        self.assertEqual(2, len(v))
        self.assertEqual('CAN', v[0].action)
        self.assertEqual('NEW', v[1].action)

    def testSequence(self):
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "kddc.cap.p"), "rb") as f:
            alerts = pickle.load(f)
        vv = list(filter(lambda v: v.event_id == "KDDC.TO.W.0052",
                         [item for sublist in [c.vtec for a, c in alerts] for item in sublist]))

        # vv = [VTEC.VTEC(v)[0] for v in ['/O.NEW.KDDC.TO.W.0052.160525T0113Z-160525T0145Z/',
        #                                '/O.CON.KDDC.TO.W.0052.000000T0000Z-160525T0145Z/',
        #                                '/O.EXP.KDDC.TO.W.0052.000000T0000Z-160525T0145Z/']]
        container = EventMessageGroup()

        self.assertEqual(1464138780.0, vv[0].get_start_time_sec())
        self.assertEqual(1464138780, vv[1].get_start_time_sec())
        self.assertEqual(1464139440, vv[2].get_start_time_sec())

        container.add_messages(vv)
        self.assertEqual(1464138780.0, container.get_start_time_sec())
        container.add_message(vv[1])
        container.add_message(vv[2])
        self.assertEqual(1464138780.0, container.get_start_time_sec())

        # This is a point in the tiny part that was excluded from the warned area on the first update
        ll = (37.791, -99.2400)
        fips = "020047"
        self.assertTrue(container.is_effective(ll, fips, True, container.messages[0].get_start_time_sec()))
        self.assertFalse(container.is_effective(ll, fips, True, container.messages[1].published))

    def test_applicable(self):
        ll = (40.321909, -102.718192)
        fips = "008125"
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "kgld.cap.p"), "rb") as f:
            alerts = pickle.load(f)
        valerts = list(filter(lambda v: v.event_id == "KGLD.TO.A.0206",
                              [item for sublist in [c.vtec for a, c in alerts] for item in sublist]))

        container = EventMessageGroup()
        for v in valerts:
            container.add_message(v)

        # self.assertEqual(len(valerts), 2)
        print("\n".join([str(v.container) for v in valerts]))
        self.assertTrue(container.is_effective(ll, fips, True, valerts[0].get_start_time_sec()))
        self.assertTrue(container.is_effective(ll, fips, True, valerts[1].get_start_time_sec()))
        self.assertFalse(container.is_effective(None, "031145", True, valerts[0].get_start_time_sec()))
        self.assertTrue(container.is_effective(None, "031145", True, valerts[-1].get_start_time_sec()))

        # TODO make a location object that knows its lat/lon, FIPS, state code, and zone.

    def test_vtec_sort(self):
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "kgld.cap.p"), "rb") as f:
            alerts = pickle.load(f)
        valerts = list([item for sublist in [c.vtec for a, c in alerts] for item in sublist])

        # Compare every pair in both directions
        # This would be better as an explicit test of the various clauses, but for today, this at least exercises
        # the code
        for i in range(0, len(valerts)):
            default_VTEC_sort(valerts[i], valerts[i])
            for j in range(1, len(valerts)):
                self.assertIsNotNone(default_VTEC_sort(valerts[i], valerts[j]), str(valerts[i]) + str(valerts[j]))
                self.assertIsNotNone(default_VTEC_sort(valerts[j], valerts[i]), str(valerts[j]) + str(valerts[i]))

