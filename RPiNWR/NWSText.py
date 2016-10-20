# -*- coding: utf-8 -*-
__author__ = 'ke4roh'

from RPiNWR.CommonMessage import CommonMessage
from RPiNWR.VTEC import VTEC
import re
import dateutil.parser
from shapely.geometry import Polygon

_TZDATA = {
    'UTC': '+0000',
    'Z': '+0000',
    'AST': '-0400',
    'EST': '-0500',
    'EDT': '-0400',
    'CST': '-0600',
    'CDT': '-0500',
    'MST': '-0700',
    'MDT': '-0600',
    'PST': '-0800',
    'PDT': '-0700',
    'AKST': '-0900',  # The old code was AST, overloaded with Atlantic
    'AKDT': '-0800',
    'ADT': '-0800',
    'HST': '-1000',
    'SST': '-1100',
    'CHST': '+1000',
    'GUAM LST': '+1000',
    'LST': '+1000'
}

STATE_FIPS = {
    'AK': '02', 'AL': '01', 'AR': '05', 'AZ': '04', 'CA': '06', 'CO': '08', 'CT': '09', 'DC': '11', 'DE': '10',
    'FL': '12', 'GA': '13', 'HI': '15', 'IA': '19', 'ID': '16', 'IL': '17', 'IN': '18', 'KS': '20', 'KY': '21',
    'LA': '22', 'MA': '25', 'MD': '24', 'ME': '23', 'MI': '26', 'MN': '27', 'MO': '29', 'MS': '28', 'MT': '30',
    'NC': '37', 'ND': '38', 'NE': '31', 'NH': '33', 'NJ': '34', 'NM': '35', 'NV': '32', 'NY': '36', 'OH': '39',
    'OK': '40', 'OR': '41', 'PA': '42', 'PR': '72', 'RI': '44', 'SC': '45', 'SD': '46', 'TN': '47', 'TX': '48',
    'UT': '49', 'VA': '51', 'VT': '50', 'WA': '53', 'WI': '55', 'WV': '54', 'WY': '56',
}

FIPS_STATE = {y: x for x, y in STATE_FIPS.items()}


def _parse_nws_date(date):
    date = re.sub("^(\d+ [AP]M )(\w+)", lambda m: m.group(1) + _TZDATA.get(m.group(2), m.group(2)), date)
    date = re.sub("^(\d{1,2}?)(\d{2}) ", "\\1:\\2 ", date)
    return dateutil.parser.parse(date).timestamp()


def _split_ugc(ugcs):
    ugc = []
    fips = []
    ugcdate = None
    ugcplaces = []
    for u in ugcs.split("-"):
        if ugcdate is None:
            if len(u) == 6 and u.isdigit():
                ugcdate = u
            else:
                if u[0:3].isalpha():
                    state = u[0:2]
                    cz = u[2]
                    u = u[3:]
                if '>' in u:
                    low, high = [int(x) for x in u.split(">")]
                    locals = ["%03d" % y for y in range(low, high + 1)]
                else:
                    locals = [u]
                for loc in locals:
                    if cz == 'C':
                        fips.append('0' + STATE_FIPS[state] + loc)
                    ugc.append(state + cz + loc)
        elif len(u) > 0:
            ugcplaces.append(u)
    if not len(fips):
        fips = None
    return ugc, fips, ugcplaces


class NWSText(CommonMessage):
    """
    http://www.nws.noaa.gov/directives/sym/pd01017001curr.pdf
    """

    @staticmethod
    def factory(text):
        return list(filter(lambda nt: nt.ugc, [NWSText(t) for t in text.split("\n$$\n")]))

    def __init__(self, text):
        self.raw = text
        parts = text.split("\n&&\n")

        publish_pattern = re.compile('^\d{3,4} [AP]M [A-Z]+ [A-Z]{3} [A-Z]{3} \d+ \d+')
        ugc_pattern = re.compile('^[A-Z0-9\->][A-Z0-9\-> ]+-$')
        vtec_pattern = re.compile('^/O\.[^/]+/$')

        ugcs = ''
        vms = []
        for line in parts[0].split("\n"):
            pub = publish_pattern.search(line)  # Maybe multiple TZ expressions on one line
            um = ugc_pattern.match(line)  # http://www.nws.noaa.gov/directives/sym/pd01017002curr.pdf
            vm = vtec_pattern.match(line)
            if pub:
                self.published = _parse_nws_date(line)
            elif um:
                ugcs += line
            elif vm:
                vms.append(line)
        if len(ugcs):
            self.ugc, self.FIPS6, self.ugc_places = _split_ugc(ugcs)
        else:
            self.ugc = self.FIPS6 = self.ugc_places = None

        polygon = None
        polygon_pattern = re.compile("^(?:LAT...LON|    )\s*?( \d{4}[0-9 ]+)")
        if len(parts) > 1:
            polygon = ""
            for line in parts[1].split("\n"):
                m = polygon_pattern.match(line)
                if m:
                    polygon += m.group(1)
            if len(polygon):
                polygon = re.sub("\s+", " ", polygon)
                polygon = list([int(x) / 100.0 for x in polygon.strip().split(" ")])
                polygon = Polygon(zip(polygon[0::2], polygon[1::2]))
        self.polygon = polygon

        self.vtec = VTEC.VTEC(vms, self)

    def get_areas(self):
        return self.FIPS6


def applies_to_fips(self, fips):
    if fips.sub("^\d", "0") in self.FIPS6:
        return True
    for u in self.ugc:
        if u[3:6] in ['ALL', '000'] and STATE_FIPS[u[0:2]] == fips[1:3]:
            return True
    return False
