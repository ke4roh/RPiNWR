# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# Logic for parsing and manipulating VTEC messages
#
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
import time
import calendar
import logging
from RPiNWR.CommonMessage import CommonMessage

# see http://www.nws.noaa.gov/om/vtec/
# http://www.nws.noaa.gov/directives/sym/pd01017003curr.pdf
# http://www.nws.noaa.gov/om/vtec/pdfs/User%20Training%20-%20Hydro%20VTEC%20-%20slides%20and%20notes.pdf

_logger = logging.getLogger("RPiNWR.VTEC")


def _parse_vtec_time(str):
    if str == '000000T0000Z':
        return None
    return calendar.timegm(time.strptime(str.replace("Z", "UTC"), '%y%m%dT%H%M%Z'))


class VTEC(CommonMessage):
    def __init__(self, vtec, container):
        """
        :param vtec: The VTEC string, unparsed
        :param container: The CommonMessage containing this message.  Geographic applicability will be delegated to
            the container.
        """
        self.raw = vtec
        self.action = None
        self.container = container
        if container is not None:
            self.polygon = container.polygon
            self.published = container.published
        else:
            self.polygon = None
            self.published = None

    def __str__(self):
        return self.raw

    def get_start_time_sec(self):
        if self.start_time is not None:
            return self.start_time
        else:
            return self.container.get_start_time_sec()

    def get_end_time_sec(self):
        if self.end_time is not None:
            return self.end_time
        else:
            return None

    def get_areas(self):
        return self.container.get_areas()

    def applies_to_fips(self, fips):
        return self.container.applies_to_fips(fips)

    def __eq__(self, other):
        return super(VTEC, self).__eq__(other) and self.container.get_areas() == other.container.get_areas() and \
               self.container.published == other.container.published

    def _fields_to_skip_for_eq(self):
        return set(["container"])

    @staticmethod
    def VTEC(vtecs, container=None):
        """
        Parse the VTEC part of a message into its PrimaryVTEC and HydrologicVTEC components as appropriate.
        A flood warning may contain a hydrologic code to give more informaiton about peak time and such.
        A single message may contain multpile pVTEC codes for example when one alert expires and another is
        initiated.

        An invalid VTEC code is logged info.

        :param vtec: One or more VTEC codes separated by newline, or an iterable of VTEC codes-
        :return: A parsed data structure to allow retrieval of details
        """
        vv = []
        pv = None
        try:
            vi = vtecs.split("\n")
        except AttributeError:
            vi = vtecs
        for vtec in vi:
            vtec = vtec.strip()
            if len(vtec) == 0:
                continue
            elif not vtec.startswith("/") or not vtec.endswith("/"):
                raise ValueError(vtec)
            if vtec[2] == '.':
                pv = PrimaryVTEC(vtec, container)
                vv.append(pv)
            elif vtec[8] == '.':
                pv.hydrologic_vtec.append(HyrdologicVTEC(vtec, pv))
            else:
                _logger.info("Bad VTEC [%s]" % vtec)
        return vv


_vtec_phenomena_priority = ["FA", "FF", "SV", "TO"]


def default_VTEC_sort(aa, bb):
    try:
        a = aa.messages[-1]
        b = bb.messages[-1]
    except AttributeError:
        a = aa
        b = bb

    if a.raw == b.raw:
        return 0
    if a.raw is None:
        return -1
    if b.raw is None:
        return 1
    try:
        significance = "WAY".find(a.significance) - "WAY".find(b.significance)
        if significance != 0:
            return significance
    except TypeError:
        if a.significance != b.significance and (a.significance is None or b.significance is None):
            return a.significance is None

    if a.phenomenon != b.phenomenon:
        if a.phenomenon in _vtec_phenomena_priority:
            if b.phenomenon in _vtec_phenomena_priority:
                delta = _vtec_phenomena_priority.index(a.phenomenon) - _vtec_phenomena_priority.index(b.phenomenon)
                if delta != 0:
                    return delta
            else:
                return 1
        elif b.phenomenon in _vtec_phenomena_priority:
            return -1

    return int(a.tracking_number) - int(b.tracking_number)


class PrimaryVTEC(VTEC):
    # /k.aaa.cccc.pp.s.####.yymmddThhnnZB-yymmddThhnnZE/
    def __init__(self, vtec, container=None):
        super().__init__(vtec, container)
        self.product_class, self.action, self.office_id, self.phenomenon, self.significance, \
        self.tracking_number, times = vtec.strip("/").split(".")
        self.start_time, self.end_time = [_parse_vtec_time(x) for x in times.split("-")]
        if self.significance == "A" and self.phenomenon in ["TO", "SV"]:
            # The SPC issues SV.A and TO.A as KWNS, but updates are from the local office
            self.event_id = vtec[12:21]
        else:
            self.event_id = vtec[7:21]
        self.hydrologic_vtec = []

    def __lt__(self, other):
        return default_VTEC_sort(self, other) < 0

    def get_event_type(self):
        return self.phenomenon + '.' + self.significance


class HyrdologicVTEC(object):
    # /nwsli.s.ic.yymmddThhnnZB.yymmddThhnnZC.yymmddThhnnZE.fr/
    def __init__(self, vtec, pvtec):
        super().__init__()
        self.raw = vtec
        self.parent = pvtec
        self.nwsli, self.severity, self.immediate_cause, t1, t2, t3, self.flood_record = \
            vtec.strip("/").split(".")
        self.start_time, self.crest_time, self.end_time = \
            [_parse_vtec_time(x) for x in (t1, t2, t3)]
        self.event_id = vtec[1:24]
