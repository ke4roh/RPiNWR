#!/usr/bin/env python3
# -*- coding: utf-8 -*
# Play a prerecorded message and flip a relay when a tornado warning comes up
#
# Copyright © 2016 Audrey Copeland
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

from datetime import datetime, timedelta
import sys

basis="""
028
WFUS52 KRAH 161959
TORRAH
NCC069-077-101-127-181-183-162045-
/O.NEW.KRAH.TO.W.0023.110416T1959Z-110416T2045Z/

BULLETIN - EAS ACTIVATION REQUESTED
TORNADO WARNING
NATIONAL WEATHER SERVICE RALEIGH NC
ISSUED BY NATIONAL WEATHER SERVICE BLACKSBURG VA
359 PM EDT SAT APR 16 2011

THE NATIONAL WEATHER SERVICE IN RALEIGH HAS ISSUED A

* TORNADO WARNING FOR...
  NORTH CENTRAL JOHNSTON COUNTY IN CENTRAL NORTH CAROLINA
  WAKE COUNTY IN CENTRAL NORTH CAROLINA
  WEST CENTRAL NASH COUNTY IN CENTRAL NORTH CAROLINA
  FRANKLIN COUNTY IN CENTRAL NORTH CAROLINA
  SOUTH CENTRAL VANCE COUNTY IN CENTRAL NORTH CAROLINA
  SOUTHEASTERN GRANVILLE COUNTY IN CENTRAL NORTH CAROLINA

* UNTIL 445 PM EDT.

* AT 354 PM EDT...NATIONAL WEATHER SERVICE DOPPLER RADAR WAS TRACKING
  A LARGE AND EXTREMELY DANGEROUS TORNADO NEAR RALEIGH...MOVING
  NORTHEAST AT 50 MPH.

THIS IS AN EXTREMELY DANGEROUS AND LIFE THREATENING SITUATION. THIS
STORM IS CAPABLE OF PRODUCING STRONG TO VIOLENT TORNADOES. IF YOU ARE
IN THE PATH OF THIS TORNADO...TAKE COVER IMMEDIATELY!

PLEASE RELAY SEVERE WEATHER REPORTS TO THE NATIONAL WEATHER SERVICE
BY CALLING TOLL FREE...1...8 6 6...2 1 5...4 3 2 4.

LAT...LON 3590 7795 3578 7824 3581 7826 3564 7855
      3586 7881 3603 7860 3601 7855 3607 7855
      3622 7834
TIME...MOT...LOC 2000Z 232DEG 42KT 3582 7858

$$

AMS
"""

def time_string(t):
    if t[0] is "0":
        t = t[1:]
    return t

def vtec_date(dt):
    return dt.strftime("%y%m%dT%H%MZ")

def pvtec(vtec, vtec_start, vtec_end):
    vtec_arr = vtec.split('.')
    new_vtec = '.'.join(vtec_arr[0:6])
    new_vtec += '.' + vtec_start + '-' + vtec_end + '/'
    return new_vtec

def mock_tornado_now(basis):
    arr = basis.split("\n")
    f = sys.stdout
    t_start = datetime.now()
    t_end = t_start + timedelta(minutes=3)
    vtec_start = vtec_date(datetime.utcnow())
    vtec_end = vtec_date(datetime.utcnow() + timedelta(minutes=3))
    new_pvtec = pvtec(arr[5], vtec_start, vtec_end)
    arr[5] = new_pvtec
    arr[11] = time_string(t_start.strftime("%I%M %p EDT %a %b %d").upper())
    arr[23] = "* UNTIL " + time_string(t_end.strftime("%I%M %p EDT").upper())
    arr[25] = "* AT " +  time_string(t_start.strftime("%I%M %p").upper()) + arr[25][11::]
    f.write('\n'.join(arr))

mock_tornado_now(basis)
