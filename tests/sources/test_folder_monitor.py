# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# test the folder_monitor code
#
# Copyright © 2017 James E. Scarborough
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
from .test_sources import ManagerTest, Watcher
from RPiNWR.sources import FolderMonitor
from shutil import rmtree
import time
import os

class TestPollFolder(ManagerTest):
    def tearDown(self):
        super().tearDown()
        rmtree("dropzone")

    def testFileDrop(self):
        location = {'warnzone': "ILZ001", 'warncounty': "ILC085",
                    'firewxzone': "ILZ001", 'local_place1': "6 Miles W Stockton IL",
                    'lat': 42.36, 'lon': -90.12}
        if not os.path.exists("dropzone"):
            os.makedirs("dropzone")
        fm = FolderMonitor(location, "dropzone", .25)
        mockmonitor = Watcher()
        system = fm + mockmonitor
        self.manager.append(system)
        system.start()
        mockmonitor.wait_for_start()
        time.sleep(1)

        with open("dropzone/wxreport", "w") as f:
            f.write("""
SEVERE THUNDERSTORM WARNING
MEC001-005-015-023-232100-
/O.NEW.KGYX.SV.W.0082.160723T2016Z-160723T2100Z/

BULLETIN - IMMEDIATE BROADCAST REQUESTED
SEVERE THUNDERSTORM WARNING
NATIONAL WEATHER SERVICE GRAY ME
416 PM EDT SAT JUL 23 2016

THE NATIONAL WEATHER SERVICE IN GRAY MAINE HAS ISSUED A

* SEVERE THUNDERSTORM WARNING FOR...
  SOUTHEASTERN SAGADAHOC COUNTY IN SOUTH CENTRAL MAINE...
  SOUTHWESTERN LINCOLN COUNTY IN SOUTH CENTRAL MAINE...
  SOUTHEASTERN ANDROSCOGGIN COUNTY IN SOUTHWESTERN MAINE...
  EAST CENTRAL CUMBERLAND COUNTY IN SOUTHWESTERN MAINE...

* UNTIL 500 PM EDT

* AT 415 PM EDT...A SEVERE THUNDERSTORM WAS LOCATED NEAR
  FREEPORT...OR NEAR BRUNSWICK...MOVING SOUTHEAST AT 30 MPH.

  HAZARD...60 MPH WIND GUSTS AND QUARTER SIZE HAIL.

  SOURCE...RADAR INDICATED.

  IMPACT...HAIL DAMAGE TO VEHICLES IS EXPECTED. EXPECT WIND DAMAGE
           TO ROOFS...SIDING...AND TREES.

* LOCATIONS IMPACTED INCLUDE...
  BRUNSWICK...BATH...FREEPORT...GEORGETOWN...YARMOUTH...HARPSWELL...
  AROWSIC...PHIPPSBURG AND WEST BATH.

PRECAUTIONARY/PREPAREDNESS ACTIONS...

FOR YOUR PROTECTION MOVE TO AN INTERIOR ROOM ON THE LOWEST FLOOR OF A
BUILDING.

LARGE HAIL AND DAMAGING WINDS AND CONTINUOUS CLOUD TO GROUND
LIGHTNING IS OCCURRING WITH THIS STORM. MOVE INDOORS IMMEDIATELY.
LIGHTNING IS ONE OF NATURE`S LEADING KILLERS. REMEMBER...IF YOU CAN
HEAR THUNDER...YOU ARE CLOSE ENOUGH TO BE STRUCK BY LIGHTNING.

TORRENTIAL RAINFALL IS OCCURRING WITH THIS STORM...AND MAY LEAD TO
FLASH FLOODING. DO NOT DRIVE YOUR VEHICLE THROUGH FLOODED ROADWAYS.

&&

LAT...LON 4374 6970 4363 6981 4378 7015 4393 7010
      4385 6970
TIME...MOT...LOC 2015Z 299DEG 24KT 4384 7004

HAIL...1.00IN
WIND...60MPH

$$
EKSTER

            """)
        nm = mockmonitor.wait_for_n_events(1, lambda x: x[0].name == "new_message", 2)
        self.assertEqual(1, len(nm))
        self.assertEqual("/O.NEW.KGYX.SV.W.0082.160723T2016Z-160723T2100Z/", nm[0][1][0].raw)

