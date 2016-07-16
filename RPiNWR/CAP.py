# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# Logic for parsing and manipulating CAP messages
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
import re
import iso8601
from RPiNWR.VTEC import VTEC
from RPiNWR.CommonMessage import CommonMessage
from shapely.geometry import Polygon
import time


class CAPMessage(CommonMessage):
    def __init__(self, dom):
        #       self.status = dom.find('{urn:oasis:names:tc:emergency:cap:1.1}status').text
        #       self.id = dom.find('{http://www.w3.org/2005/Atom}id').text
        #       self.published, self.updated = [
        #           iso8601.parse_date(self.__dom.find('{http://www.w3.org/2005/Atom}' + x).text).timestamp() for x in
        #           ('published', 'updated')]

        k = None
        for x in dom.iter():
            if x.tag == '{http://www.w3.org/2005/Atom}valueName':
                k = x.text.strip()
            elif k is not None and x.tag == '{http://www.w3.org/2005/Atom}value':
                self.__dict__[k] = CAPMessage.__parse_date_or_text(x.text)
            elif x.tag not in ["{urn:oasis:names:tc:emergency:cap:1.1}geocode",
                               "{urn:oasis:names:tc:emergency:cap:1.1}parameter"]:
                self.__dict__[x.tag[x.tag.find('}') + 1:]] = CAPMessage.__parse_date_or_text(x.text)

        if self.FIPS6:
            self.FIPS6 = re.sub("[\n\t ] +", " ", self.FIPS6.strip()).split(" ")

        if self.polygon is not None and len(self.polygon.strip()) > 0:
            self.polygon = re.sub("[\n\t ] +", " ", self.polygon)
            self.polygon = Polygon([(float(x), float(y)) for x, y in [x.split(",") for x in self.polygon.split(" ")]])
        else:
            self.polygon = None

        try:
            if self.__dict__['VTEC'] and len(self.VTEC):
                self.vtec = VTEC.VTEC(self.VTEC, self)
            else:
                self.vtec = (NOVTEC(dom, self),)
            if len(self.vtec) == 0:  # True if there was an invalid vtec code
                self.vtec = (NOVTEC(dom, self),)
        except KeyError:
            self.vtec = (NOVTEC(dom, self),)

    @staticmethod
    def __parse_date_or_text(str):
        try:
            str = str.strip()
        except AttributeError:
            return str
        try:
            return iso8601.parse_date(str).timestamp()
        except iso8601.iso8601.ParseError:
            return str

    def __str__(self):
        return "CAP [ %s %s %s %s ]" % (
            time.asctime(time.gmtime(self.published)), self.get_event_type(), self.vtec[-1], self.FIPS6)

    def get_event_type(self):
        return self.vtec[-1].get_event_type()

    def get_start_time_sec(self):
        return self.effective

    def get_end_time_sec(self):
        return self.expires

    def get_event_id(self):
        return self.id

    def get_areas(self):
        return self.FIPS6

    def applies_to_fips(self, fips):
        if not self.FIPS6:
            return False
        if fips.startswith('0'):
            fips = '.' + fips[1:]
        else:
            fips = '[0' + fips[0] + ']' + fips[1:]
        fips = '^' + fips + '$'
        fp = re.compile(fips)
        return len(list(filter(lambda c: fp.match(c), self.FIPS6))) > 0


class NOVTEC(VTEC):
    """
    For the occasion when the VTEC string isn't there (special weather statements, non-weather, etc.)
    """

    def __init__(self, dom, container):
        super().__init__(None, container)
        self.event_id = container.id
        self.start_time = container.effective
        self.end_time = container.expires
        self.event_type = container.event

    def get_event_type(self):
        return self.container.event

    def __str__(self):
        return "None"
