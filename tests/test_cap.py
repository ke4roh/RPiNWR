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

# https://alerts.weather.gov/cap/pdf/CAP%20v12%20guide%20web%2006052013.pdf

import unittest
import os
from glob import glob
import xml.etree.ElementTree as etree
import RPiNWR.CAP as CAP
import time
from shapely.geometry import Point


class TestCAP(unittest.TestCase):
    @staticmethod
    def _get_test_messages():
        root = etree.parse(os.path.join(os.path.dirname(os.path.realpath(__file__)), "test_cap.xml"))
        return root.findall('{http://www.w3.org/2005/Atom}entry')

    def testTOW(self):
        cm = CAP.CAPMessage(TestCAP._get_test_messages()[0])
        self.assertEqual('TO.W', cm.get_event_type())
        self.assertEqual('http://alerts.weather.gov/cap/wwacapget.php?x=KS1255FCC0A5BC.TornadoWarning.1255FCC0C36CKS.GLDTORGLD.3a1fc090003ef1448f822dfd9b2ddee2', cm.get_event_id())
        self.assertEqual('KGLD.TO.W.0021', cm.vtec[-1].event_id)
        self.assertEqual(cm, cm.vtec[-1].container)
        self.assertEqual(1463877540.0, cm.get_start_time_sec())
        self.assertEqual(1463879700.0, cm.get_end_time_sec())
        self.assertFalse(cm.is_effective(when=1463877539.9))
        self.assertTrue(cm.is_effective(when=1463877540.0))
        self.assertTrue(cm.is_effective(when=1463877541.0))
        self.assertTrue(cm.is_effective(when=1463879700.0))
        self.assertFalse(cm.is_effective(when=1463879700.1))
        self.assertTrue(cm.polygon.contains(Point(38.80, -101.45)))
        self.assertFalse(cm.polygon.contains(Point(38.90, -101.45)))
        self.assertEqual("CAP [ Sun May 22 00:39:00 2016 TO.W /O.NEW.KGLD.TO.W.0021.160522T0039Z-160522T0115Z/ ['020109', '020199'] ]",str(cm))

    def testFFW(self):
        cm = CAP.CAPMessage(TestCAP._get_test_messages()[1])
        self.assertEqual('FL.W', cm.get_event_type())
        self.assertEqual('http://alerts.weather.gov/cap/wwacapget.php?x=TX1255FCB3FAC4.FloodWarning.1255FCDF22D0TX.EWXFLWEWX.3a455869c958e7386bea0d696e29a8ec', cm.get_event_id())
        self.assertEqual('KEWX.FL.W.0043', cm.vtec[-1].event_id)
        self.assertEqual('GBCT2', cm.vtec[-1].hydrologic_vtec[-1].nwsli)
        self.assertEqual(cm, cm.vtec[-1].container)
        # VTEC relates to the time of high water, which can be anticipated.  CAP is about the alert itself, so the
        # start time of the ALERT is the lesser of the two.
        self.assertEqual(1463852220.0, cm.get_start_time_sec())
        self.assertEqual(1464049200.0, cm.get_end_time_sec())
        self.assertTrue(cm.polygon.contains(Point(29.6011519, -98.0439125)))
        self.assertFalse(cm.polygon.contains(Point(29.582935, -97.969713)))
