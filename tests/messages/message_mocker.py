# -*- coding: utf-8 -*-
__author__ = 'jscarbor'

from jinja2 import Environment, PackageLoader, select_autoescape
from RPiNWR.messages.NWSText import _TZDATA
from dateutil.tz import tzoffset

mocker = Environment(
    loader=PackageLoader('tests.messages', 'templates'),
    autoescape=select_autoescape()
)


def _offset_secs(offset):
    """ Compute the number of seconds from a 5-character string tz offset"""
    return (offset.startswith('-') * -1) * (int(offset[1:3]) * 60 + int(offset[3:5])) * 60


TZ = {z: tzoffset(z, _offset_secs(o)) for z, o in _TZDATA.items()}


def _flat_poly(d):
    if d:
        nums = [("%.2f" % x).replace('.', '') for x in d]
        return "      \n".join([" ".join(nums[n:n + 8]) for n in range(0, len(nums), 8)])
    else:
        return d and True


mocker.globals['vtec_ts'] = lambda d: d.astimezone(TZ['Z']).strftime("%y%m%dT%H%M")
mocker.globals['header_time'] = lambda d: d.strftime("%-I%M %p EDT %a %b %-d %Y").upper()
mocker.globals['flat_poly'] = _flat_poly