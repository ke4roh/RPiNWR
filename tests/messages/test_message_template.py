# -*- coding: utf-8 -*-

import unittest
import datetime
from message_mocker import mocker as env, TZ

__author__ = 'jscarbor'


class TestMessageMocking(unittest.TestCase):
    def test_tow_new(self):
        t = env.get_template('tow-new.txt')
        z = TZ['EDT']
        self.assertEqual(t.render({
            "start": datetime.datetime(2017, 9, 1, hour=17, minute=58, second=0, microsecond=0, tzinfo=z),
            "end": datetime.datetime(2017, 9, 1, hour=18, minute=45, second=0, microsecond=0, tzinfo=z)
        }), """427
WFUS52 KRAH 012158
TORRAH
NCC085-012245-
/O.NEW.KRAH.TO.W.0018.170901T2158Z-170901T2245Z/

BULLETIN - EAS ACTIVATION REQUESTED
Tornado Warning
National Weather Service Raleigh NC
558 PM EDT FRI SEP 1 2017

The National Weather Service in Raleigh has issued a

* Tornado Warning for...
  Harnett County in central North Carolina...

* Until 645 PM EDT

* At 558 PM EDT, a severe thunderstorm capable of producing a tornado
  was located 10 miles northwest of Pope AFB, or 12 miles northwest
  of Fort Bragg, moving east at 45 mph.

  HAZARD...Tornado.

  SOURCE...Radar indicated rotation.

  IMPACT...Flying debris will be dangerous to those caught without
           shelter. Mobile homes will be damaged or destroyed.
           Damage to roofs, windows, and vehicles will occur.  Tree
           damage is likely.

* Locations impacted include...
  Lillington, Dunn, Angier, Erwin, Coats, Pineview, Anderson Creek,
  Timberlake, Raven Rock State Park and Buies Creek.

PRECAUTIONARY/PREPAREDNESS ACTIONS...

TAKE COVER NOW! Move to a basement or an interior room on the lowest
floor of a sturdy building. Avoid windows. If you are outdoors, in a
mobile home, or in a vehicle, move to the closest substantial shelter
and protect yourself from flying debris.

To report severe weather contact your nearest law enforcement agency.
They will send your report to the National Weather Service office in
Raleigh.

&&

LAT...LON 3521 7913 3525 7916 3532 7917 3536 7913
      3553 7877 3541 7863 3526 7864 3526 7880
      3521 7898 3521 7903 3519 7910
TIME...MOT...LOC 2158Z 251DEG 39KT 3529 7910

TORNADO...RADAR INDICATED
HAIL...<.75IN

$$

GIH""")