# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# Logic for parsing and manipulating SAME messages
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
import time
import logging
import threading
import functools
import calendar
import operator
from collections import Sequence
import itertools
from .CommonMessage import CommonMessage
from ..sources.radio.nwr_data import get_counties, get_wfo
from statistics import median

# See http://www.nws.noaa.gov/directives/sym/pd01017012curr.pdf
# also https://www.gpo.gov/fdsys/pkg/CFR-2010-title47-vol1/xml/CFR-2010-title47-vol1-sec11-31.xml

_ORIGINATORS = [
    ("Broadcast station or cable system", "EAS"),
    ("Civil authorities", "CIV"),
    ("National Weather Service", "WXR"),
    ("Primary Entry Point System", "PEP")
]
_ORIGINATOR_CODES = tuple([x[1] for x in _ORIGINATORS])

_EVENT_TYPES = [
    ("Blizzard Warning", "BZW", "Aviso de ventisca"),
    ("Coastal Flood Watch", "CFA", "Vigilancia de inundaciones costeras"),
    ("Coastal Flood Warning", "CFW", "Aviso de inundaciones costeras"),
    ("Dust Storm Warning", "DSW", "Aviso de vendava"),
    ("Flash Flood Watch", "FFA", "Vigilancia de inundaciones repentinas"),
    ("Flash Flood Warning", "FFW", "Aviso de inundaciones repentinas"),
    ("Flash Flood Statement", "FFS", "Comunicado de inundaciones repentinas"),
    ("Flood Watch", "FLA", "Vigilancia de inundación"),
    ("Flood Warning", "FLW", "Aviso de inundación"),
    ("Flood Statement", "FLS", "Advertencia de inundación"),
    ("High Wind Watch", "HWA", "Vigilancia de vientos fuertes"),
    ("High Wind Warning", "HWW", "Aviso de vientos fuertes"),
    ("Hurricane Watch", "HUA", "Vigilancia de huracán"),
    ("Hurricane Warning", "HUW", "Aviso de huracán"),
    ("Hurricane Statement", "HLS", "Comunicado de huracán"),
    ("Severe Thunderstorm Watch", "SVA", "Vigilancia de tronada severa"),
    ("Severe Thunderstorm Warning", "SVR", "Aviso de tronada severa"),
    ("Severe Weather Statement", "SVS", "Advertencia de tiempo severo"),
    ("Special Marine Warning", "SMW", "Aviso marítimo especial"),
    ("Special Weather Statement", "SPS", "Comunicado especial del estado del tiempo"),
    ("Tornado Watch", "TOA", "Vigilancia de tornado"),
    ("Tornado Warning", "TOR", "Aviso de tornado"),
    ("Tropical Storm Watch", "TRA", "Vigilancia de tormenta tropical"),
    ("Tropical Storm Warning", "TRW", "Aviso de tormenta tropical"),
    ("Tsunami Watch", "TSA", "Vigilancia de tsunami"),
    ("Tsunami Warning", "TSW", "Aviso de tsunami"),
    ("Winter Storm Watch", "WSA", "Vigilancia de tormenta de nieve"),
    ("Winter Storm Warning", "WSW", "Aviso de tormenta de nieve"),
    ("Emergency Action Notification", "EAN", "Anuncio de acción urgente"),
    ("Emergency Action Termination", "EAT", "Fin de acción urgente"),
    ("National Information Center", "NIC", "Mensaje del Centro Nacional de información"),
    ("National Periodic Test", "NPT", "Prueba periódica nacional"),
    ("Required Monthly Test", "RMT", "Prueba mensual obligatoria"),
    ("Required Weekly Test", "RWT", "Prueba semanal obligatoria"),
    ("Administrative Message", "ADR", "Mensaje administrativo"),
    ("Avalanche Watch", "AVA", "Vigilancia de avalancha"),
    ("Avalanche Warning", "AVW", "Aviso de avalancha"),
    ("Child Abduction Emergency", "CAE", "Emergencia de rapto de menores"),
    ("Civil Danger Warning", "CDW", "Aviso de peligro civil"),
    ("Civil Emergency Message", "CEM", "Mensaje de emergencia civil"),
    ("Earthquake Warning", "EQW", "Aviso de terremoto"),
    ("Evacuation Immediate", "EVI", "Evacuación inmediata"),
    ("Fire Warning", "FRW", "Aviso de fuego"),
    ("Hazardous Materials Warning", "HMW", "Aviso de materiales peligrosos"),
    ("Law Enforcement Warning", "LEW", "Aviso de las autoridades de la ley"),
    ("Local Area Emergency", "LAE", "Emergencia de área local"),
    ("911 Telephone Outage Emergency", "TOE", "Interrupción telefónica 911"),
    ("Nuclear Power Plant Warning", "NUW", "Aviso de riesgo nuclear"),
    ("Radiological Hazard Warning", "RHW", "Aviso de peligro radiológico"),
    ("Shelter In Place Warning", "SPW", "Aviso de refugio"),
    ("Volcano Warning", "VOW", "Aviso de actividad volcánica"),
    ("Network Message Notification", "NMN", "Anuncio de mensaje en red"),
    ("Practice/Demo Warning", "DMO", "Práctica/Demostración"),
    ("Transmitter Carrier Off", "TXF", "Frecuencia portadora de emisión"),
    ("Transmitter Carrier On", "TXO", "Frecuencia portadora de emisión activada"),
    ("Transmitter Backup On", "TXB", "Transmisor de respaldo activado"),
    ("Transmitter Primary On", "TXP", "Transmisor principal activado"),
]
_EVENT_CODES = tuple([x[1] for x in _EVENT_TYPES])

VALID_DURATIONS = (
    (1, '0015'), (1, '0030'), (1.1, '0045'), (1.1, '0100'), (1, '0130'), (1.1, '0200'), (1, '0230'), (1.1, '0300'),
    (.9, '0330'), (1.1, '0400'), (.9, '0430'), (1.1, '0500'), (.9, '0530'), (1.1, '0600'))

_DURATION_NUMBERS = tuple([x[1] for x in VALID_DURATIONS])


# takes a list of codes and a list of valid codes, and checks to make sure all of the codes correspond to a valid list
# e.g. if we have a list of ['WXR', 'WXR', 'WXR'] we should get the result that this is a valid originator code

class ConfidentCharacter(tuple):
    """
    Immutable representation of a character with its confidence.
    
    R: Know the character (or lack thereof)
    R: know the bitwise confidence
    R: produce a byte-wise confidence int(sum(bitwise)/8)
    C: combine to make string w/confidence “+”
    C: combine to make a single character “&” (honor the bit values having more confidence, the confidence is winning-losing confidence)

    """
    __slots__ = []

    def __new__(cls, char, confidence=None):
        """
        :param char: the character to represent (as a character)
        :param confidence: integer indicating confidence for the whole byte
           or an array/tuple of length 8 to indicate confidence for each bit
        """
        if char == '\u0000':
            confidence = 0

        if confidence is None:
            raise ValueError("Confidence is required (int like 0-9, or array for each bit")

        if hasattr(confidence, '__len__'):
            assert len(confidence) == 8
            bitwise_confidence = confidence
        else:
            bitwise_confidence = (confidence,) * 8

        if type(bitwise_confidence) is not tuple:  # Unmodifiable
            bitwise_confidence = tuple(bitwise_confidence)

        return tuple.__new__(cls, (char, bitwise_confidence))

    @property
    def char(self):
        return tuple.__getitem__(self, 0)

    @property
    def confidence(self):
        """The byte-wise confidence for this character"""
        return sum(self.bitwise_confidence) >> 3

    @property
    def bitwise_confidence(self):
        """A tuple of length 8, representing the confidence for each bit in this character"""
        return tuple.__getitem__(self, 1)

    def __getitem__(self, item):
        raise TypeError

    def __repr__(self):
        return '<ConfidentCharacter \'%s\' %s>' % (self.char, str(self.bitwise_confidence))

    def __str__(self):
        return self.char

    def __and__(self, other):
        how_true = self.get_bit_confidences()
        other_how_true = other.get_bit_confidences()
        new_how_true = list(map(operator.add, how_true, other_how_true))
        new_byte = 0x00
        for i in range(0, 8):
            if new_how_true[i] > 0:
                new_byte |= 1 << i

        return ConfidentCharacter(chr(new_byte), confidence=list(map(operator.abs, new_how_true)))

    def __add__(self, other):
        if isinstance(self, other.__class__):
            return ConfidentString([self, other])
        else:
            raise ValueError()

    def confidence_distance_to(self, c):
        """
        :param c: a character
        :return: an integer sum of the bitwise confidences not in agreement with the given character's bits
        """
        if c == '\u0000':
            return 0
        dist = 0
        bc = self.get_bit_confidences()
        for i in range(0, 8):
            test_bit = (ord(c) >> i) & 1
            if test_bit and bc[i] < 0:
                dist += -bc[i]
            if not test_bit and bc[i] > 0:
                dist += bc[i]
        return dist

    def override_with(self, c):
        """
        :param c: a character
        :return: a new ConfidentCharacter with adjusted confidence.  Bits changed will have confidence 0,
            bits unchanged will have confidence unchanged.
        """
        if c == self.char:
            return self
        bc = self.get_bit_confidences()
        for i in range(0, 8):
            new_bit = (ord(c) >> i) & 1
            if (new_bit and bc[i] < 0) or (not new_bit and bc[i] > 0):
                bc[i] = 0
        return ConfidentCharacter(c, confidence=list(map(operator.abs, bc)))

    def get_bit_confidences(self):
        """Compute the confidence for each bit being true or false"""
        how_true = [0] * 8
        for k in range(0, 8):
            # if the last bit (e.g. 00001) is a 1:
            if (ord(self.char) >> k) & 1:
                # then add it to the bitstrue (or bitsfalse) bits with that bit's confidence level
                how_true[k] += 1 * self.bitwise_confidence[k]
            else:
                how_true[k] -= 1 * self.bitwise_confidence[k]
        return how_true


class ROSlice(Sequence, tuple):
    """
    https://stackoverflow.com/a/3485490/8221937
    """
    __slots__ = []

    def __new__(cls, alist, start, stop):
        start = (start is not None and start) or 0
        if start < 0:
            start += len(alist)
        stop = (stop is not None and stop) or len(alist)
        if stop < 0:
            stop += len(alist)
        if stop > len(alist):
            raise IndexError("start > len")
        if start > len(alist):
            raise IndexError("start < len")
        if stop < start:
            raise IndexError("start < stop")
        return tuple.__new__(cls, (alist, start, stop))

    @property
    def alist(self):
        return tuple.__getitem__(self, 0)

    @property
    def start(self):
        return tuple.__getitem__(self, 1)

    @property
    def stop(self):
        return tuple.__getitem__(self, 2)

    def __len__(self):
        return self.stop - self.start

    def adj(self, i):
        if i < 0:
            i += len(self)
        return i + self.start

    def __getitem__(self, item):
        if isinstance(item, slice):
            return ROSlice(self.alist,
                           (self.start + item.start is not None and item.start) or 0,
                           (self.stop + item.stop is not None and item.stop) or len(self))
        if item >= len(self) or item < -len(self):
            raise IndexError

        return self.alist[self.adj(item)]

    def __repr__(self):
        return "<ROSlice(%s)>" % ",".join(repr(x) for x in self)

    def __eq__(self, other):
        try:
            for x, y in itertools.zip_longest(self, other, fillvalue="NOPE_NOT_THIS_ONE"):
                if x != y:
                    return False
        except AttributeError:
            return False
        return True


class ConfidentString(Sequence, tuple):
    """
    Immutable String w/confidence
    R: Compute confidence for the string
    C: Combine with a regular string to produce another String w/confidence, reducing confidence for bytes changed
    C: Concatenate to another string w/confidence “+”
    C: Concatenate a character with “+”
    R: Know characters (in order)
    """
    __slots__ = []

    def __new__(cls, data=None, confidence=None, start=0, end=None):
        """

        :param data: An array or tuple of ConfidentCharacters or a String, with confidence provided separately
        :param confidence: If data is ConfidentCharacters, None.  Otherwise, an array of integer confidences
            (or a string of confidence digits).
        :param start: The index of the first character of data to consider
        :param end: The index of the last character of data to consider
        """
        if data is None:
            data = []

        if end is None:
            end = len(data)

        if start is not None and start == end:
            return tuple.__new__(cls, ([],))

        if confidence is not None and hasattr(confidence, "isnumeric"):
            assert confidence.isnumeric()
            confidence = [int(c) for c in confidence]

        # if data is a string, build it into ConfidentCharacters
        if "lower" in dir(data):
            str_data = data
            data = tuple(ConfidentCharacter(str_data[i], confidence[i]) for i in range(start, end))
            start = 0
            end = len(data)
        elif not all(isinstance(x, ConfidentCharacter) for x in data):
            raise ValueError("Only ConfidentCharacters can be in data")

        if not isinstance(data, tuple):
            data = tuple(data)

        if start != 0 or end != len(data):
            data = ROSlice(data, start, end)

        return tuple.__new__(cls, (data,))

    @property
    def data(self):
        return tuple.__getitem__(self, 0)

    def __add__(self, other):
        """Concatenate"""
        if isinstance(self, other.__class__):
            new_data = list(self.data)
            new_data.extend(other.data)
            return ConfidentString(new_data)
        elif isinstance(other, ConfidentCharacter):
            new_data = list(self.data)
            new_data.append(other)
            return ConfidentString(new_data)
        else:
            raise ValueError(other.__class__)

    def __str__(self):
        s = ""
        for c in self.data:
            s += c.char
        return s

    def __getitem__(self, item):
        if isinstance(item, slice):
            if not (item.step is None or item.step == 1):
                raise ValueError("Steps are unsupported")
            return ConfidentString(
                self.data,
                start=item.start,
                end=item.stop)
        return self.data.__getitem__(item)

    @property
    def confidence(self):
        """Return byte-wise confidence"""
        conf = []
        for i in self.data:
            conf.append(i.confidence)
        return tuple(conf)

    def __len__(self):
        return len(self.data)

    def __eq__(self, other):
        if isinstance(self, other.__class__):
            return self.data == other.data
        return False

    def __repr__(self):
        return "<%s(\'%s\',%s)>" % (self.__class__.__name__, str(self), str(self.confidence))

    def __and__(self, other):
        """Merge two ConfidentStrings together, increasing confidence where same"""
        if isinstance(self, other.__class__):
            result = []
            for i in range(0, min(len(other), len(self))):
                result.append(self[i] & other[i])
            if len(other) < len(self):
                result.extend(self.data[len(other):])
            elif len(self) < len(other):
                result.extend(other.data[len(self):])

            return ConfidentString(result)
        else:
            raise ValueError("ConfidentStrings only AND with other ConfidentStrings")

    def confidence_distance_to(self, candidate):
        """
        Calculate the bitwise confidence distance from this string to the candidate.
        If this string is longer than the candidate, then every bit is wrong for the missing bytes.
        If this string is shorter than the candidate, bits are also wrong by the best confidence in this string.
        Null (\u0000) have confidence 0, both directions.
        :param candidate: A regular string to compare
        :return: an integer representing the sum of confidences of bits to change
        """
        distance = 0
        for i in range(0, min(len(candidate), len(self))):
            distance += self[i].confidence_distance_to(candidate[i])
        if len(candidate) < len(self):
            distance += sum(sum(c.bitwise_confidence) for c in self.data[len(candidate):])
        if len(self) < len(candidate):
            distance += 8 * (len(candidate) - len(self) - candidate.count('\u0000', len(self))) * max(
                c.confidence for c in self.data)
        return distance

    def override_with(self, valid_str):
        """
        :param valid_str: A valid string to use.  Null values in this string will be passed over.
        :return: A new ConfidentString, whose length is the same as valid_str, and whose content has been
        updated to match valid_str and confidence docked for any mismatches, for all but the \u0000
        characters in valid_str.
        """

        # Short circuit no change
        changed = len(self) != len(valid_str)
        if not changed:
            for i in range(0, len(self)):
                changed |= self[i].char != valid_str[i]
                if changed:
                    break
        if not changed:
            return self

        d = list(self.data)
        if len(valid_str) > len(self):
            d.extend((ConfidentCharacter('\u0000', 0),) * (len(valid_str) - len(self)))
        d = d[:len(valid_str)]

        confidence_sum = 0
        confidence_count = 0
        for i in range(0, len(d)):
            if valid_str[i] != '\u0000':
                d[i] = d[i].override_with(valid_str[i])
                if len(self) > i: # and self[i].char != '\u0000':
                    confidence_sum += d[i].confidence
                    confidence_count += 1

        # The confidence of a character substutited for null is the mean confidence of the string
        # based on all the non-null characters
        mean_confidence = int(confidence_sum / confidence_count)
        for i in range(0, len(d)):
            if valid_str[i] != '\u0000' and (i >= len(self) or self[i].char == '\u0000'):
                d[i] = ConfidentCharacter(d[i].char, mean_confidence)

        return ConfidentString(d)

    def closest(self, possibilities, max_distance=float("inf")):
        """

        :param possibilities: Either a list of str OR a list of tuples of (weight, str).  All strings must be
        the same length.
        :param max_distance: The maximum distance, per character, by which strings may differ and still perform
        replacement - otherwise it's left as-is.
        :return: The best matched string
        """
        if isinstance(possibilities[0], str):
            possibilities = [(1, p) for p in possibilities]

        # While it is not strictly necessary to perform all the comparisons necessary to produce the completely
        # sorted list, the practical number of possibilities makes it silly to worry over the log(n) extra comparisons
        distances = sorted([((1 + self.confidence_distance_to(p)) / float(w), p) for w, p in possibilities])
        if len(distances) > 1 and distances[0][0] == distances[1][0]:
            raise AmbiguousSAMEMessage("message: %s possibilities: %s" % (str(self), str(possibilities)))
        if distances[0][0] <= max_distance:
            return self.override_with(distances[0][1])
        else:
            return self

    def index(self, value, start=0, stop=None):
        """
        Return the first index of the given value, which may be specified as a ConfidentCharacter or a character
        (string of length 1).  If a ConfidentCharacter is provided, then its confidence must also match.
        Raises ValueError if the value is not present.

        :param value:
        :param start:
        :param stop:
        :return:
        """
        if isinstance(value, ConfidentCharacter):
            return self.data.index(value, start is not None or 0, stop is not None or len(self))
        if isinstance(value, str) and len(value) == 1:
            for i in range(0, len(self)):
                if self.data[i].char == value:
                    return i
        raise ValueError()

    def find(self, value, start=0, stop=None):
        """
        Return the first index of the given value, which may be specified as a String, ConfidentString, or
           ConfidentCharacter.  Confidences are not matched.

           Returns -1 if the element is not found
        """
        return str(self).find(str(value), start, stop)


def check_if_valid_code(codes, valid_list):
    # Check if we have three matching and valid codes
    if set(valid_list).issuperset(codes) and codes[0] == codes[1] and codes[1] == codes[2]:
        return codes[0]

    # Check the character against the space of possible characters and approximate the closest valid char

    '''
    [
    '-', 'ECWP', 'AIXE', 'SVRP', '-', __ALPHA, __ALPHA, __ALPHA, '-', ***HERE***
    __PRINTABLE, __PRINTABLE, __PRINTABLE, __PRINTABLE, __PRINTABLE, __PRINTABLE, -7,
    '+', __NUMERIC, __NUMERIC, '0134', '05', '-',
    '0123', __NUMERIC, __NUMERIC, '012', __NUMERIC, '012345', __NUMERIC, '-',
    __ALPHA, __ALPHA, __ALPHA, __ALPHA, '/', 'N', 'W', 'S', '-'
    ]
    
    '-WḀR-SVR-0Ḁ7183+00Ḁ5-12320Ḁ3-KRAH/ḀWS-ḀḀḀḖḀỻờ~ỿ'
    '''


# CLEAN: -WXR-TOR-039173-039051-139069+0030-1591829-KCLE/NWS
# DIRTY: -WḀR-SVR-0Ḁ7183+00Ḁ5-12320Ḁ3-KRAH/ḀWS-ḀḀḀḖḀỻờ~ỿ
__ALPHA = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
__NUMERIC = '0123456789'
_PRINTABLE = '\x10\x13' + "".join(filter(lambda x: ord(x) != 43 and ord(x) != 45, [chr(x) for x in range(33, 127)]))
_SAME_CHARS = [
    '-', 'ECWP', 'AIXE', 'SVRP', '-', __ALPHA, __ALPHA, __ALPHA, '-',
    _PRINTABLE, _PRINTABLE, _PRINTABLE, _PRINTABLE, _PRINTABLE, _PRINTABLE, -7,
    '+', __NUMERIC, __NUMERIC, '0134', '05', '-',
    '0123', __NUMERIC, __NUMERIC, '012', __NUMERIC, '012345', __NUMERIC, '-',
    __ALPHA, __ALPHA, __ALPHA, __ALPHA, '/', 'N', 'W', 'S', '-'
]

# -WXR-TOR-039173-039051-139069+0030-1591829-KCLE/NWS
SAME_PATTERN = re.compile('-(EAS|CIV|WXR|PEP)-([A-Z]{3})((?:-\\d{6})+)\\+(\\d{4})-(\\d{7})-([A-Z/]+)-?')


class SAMEHeader(ConfidentString, tuple):
    """
    Contain a single instance of the message sent from the radio, or
    the result of aggregation with another instance.
    Responsibilities:
    Combine with other SAMEHeaders
    Know its time received (in case of combination, that's the first time
    Know its ConfidentString
    """
    __slots__ = []

    def __new__(cls, data=None, confidence=None, received_time=None):
        """
        :param data: A ConfidentString or String of characters from the radio
        :param confidence: If data is a String, the string (or numeric array) of confidences for the data
        :param time: The time this header was fully received
        """
        if isinstance(data, SAMEHeader) and confidence is None and received_time is None:
            return data

        if isinstance(data, ConfidentString):
            if confidence is not None:
                raise ValueError("Confidence should not be specified in conjunction with a ConfidentString")
        else:
            data = ConfidentString(data, confidence)

        # Make sure it's all ASCII, set nulls to \u0000 (which get 0 confidence)
        if max([ord(c.char) >> 8 for c in data]):
            def ascii_mask(char):
                c = ord(str(char)) & 0xff
                if c == 0:
                    c = '\u0000'
                else:
                    c = chr(c)
                return ConfidentCharacter(c, char.bitwise_confidence)

            data = ConfidentString([ascii_mask(c) for c in data])

        if received_time is None:
            received_time = time.time()

        return tuple.__new__(cls, (data.data, received_time))

    @property
    def time(self):
        return tuple.__getitem__(self, 1)

    def __add__(self, other):
        """Concatenation"""
        raise NotImplemented()

    def __and__(self, other):
        """Combining"""
        if isinstance(other, SAMEHeader):
            return SAMEHeader(ConfidentString.__and__(self, other), received_time=min((self.time, other.time)))
        elif isinstance(other, ConfidentString):
            return SAMEHeader(ConfidentString.__and__(self, other), received_time=self.time)
        else:
            raise ValueError("Can't and with %s" % other.__class__.__name__)

    def find(self, value, start=0, stop=None):
        if value == '+' and self.data[len(self) - len(_END_SEQUENCE)].char == '+':
            return len(self) - len(_END_SEQUENCE)
        return super(ConfidentString).find(value, start, stop)


# For sequences, we define what characters are expected in certain positions in the string.
# We don't want to specify most characters yet - that will come.  But first we'll specify
# The shape of the message, and leave blank (\u0000) characters that could be anything.
_END_SEQUENCE = "+0___-_______-____/NWS-".replace('_', '\u0000')
_START_SEQUENCE = "-___-___".replace('_', '\u0000')
_COUNTY_SEQUENCE = "-______".replace('_', '\u0000')
# The shell candidates are the shape of the message, which only varies based on the number of county codes.
# The shell is padded at the end because sometimes the string from the radio has a few characters of
# noise after the message, and those should not penalize the sequence for not matching.
_SHELL_CANDIDATES = [_START_SEQUENCE + _COUNTY_SEQUENCE * c + _END_SEQUENCE + '\u0000' * 9 for c in range(1, 32)]


class SAMEMessageScrubber(object):
    """
    Responsibilities:
    * Identify the correct length of a message (and correct those characters)
    * Adjust characters that aren't legit and also aren't far off from the spec
    * Know the
    Collaborations:
    * SAMEMessage calls this with some headers
    * ConfidentString
    """

    def __init__(self, headers, transmitter=None):
        """
        :param headers: An iterable of ConfidentStrings based on the headers
        """
        self.headers = headers
        if not isinstance(headers[0], SAMEHeader):
            msg = SAMEHeader(headers[0])
        else:
            msg = headers[0]
        if len(headers) > 1:
            for i in range(1, len(headers)):
                h = headers[i]
                if not isinstance(h, SAMEHeader):
                    h = SAMEHeader(h)
                msg &= h

        # self.message will contain our best of 3 string, computed bitwise, and we'll improve on that as we go.
        self.message = msg
        self.transmitter = transmitter
        if transmitter is None:
            self.counties = None
            self.wfo = None
        else:
            self.counties = sorted(get_counties(transmitter))
            self.wfo = get_wfo(transmitter)

    def fix_length(self):
        # Find the length, set the sentinel characters
        msg = self.message.closest(_SHELL_CANDIDATES)
        self.message = msg[:msg.find('+') + len(_END_SEQUENCE)]

    def sub_valid_codes(self, offset, choices, max_distance=float("inf")):
        if isinstance(choices[0], str):
            first_choice = choices[0]
        else:
            first_choice = choices[0][1]  # assuming tuple with weight first
        # All the choices have to be the same length or it doesn't make sense.
        msg_word = self.message[offset:offset + len(first_choice)]
        clean_word = msg_word.closest(choices, max_distance)
        if msg_word != clean_word:
            self.message = self.message[0:offset] + clean_word + self.message[offset + len(clean_word):]

    def sub_printable(self, start, end):
        pc = list(_PRINTABLE)
        for j in range(start, end):
            self.sub_valid_codes(start + j, pc)

    def scrub(self):
        self.fix_length()
        self.sub_valid_codes(1, _ORIGINATOR_CODES)
        self.sub_valid_codes(5, _EVENT_CODES)
        plus_ix = self.message.index('+')
        self.sub_valid_codes(plus_ix + 1, VALID_DURATIONS)

        if self.wfo is not None:
            self.sub_valid_codes(plus_ix + 14, [self.wfo])
        else:
            self.sub_printable(plus_ix + 14, plus_ix + 19)

        # Prefer times near to now
        valid_times = []
        for weight, offset in ((.5, -4), (.7, -3), (.9, -2), (1.1, -1), (1, 0)):
            valid_times.append(
                (weight, time.strftime('%j%H%M', time.gmtime(self.headers[0].time + 60 * offset))))

        self.sub_valid_codes(plus_ix + 6, valid_times)

        self.sub_counties(plus_ix)
        return self.message

    def sub_counties(self, plus_ix):
        assert plus_ix % 7 == 1

        # Substitute for counties with known set or unknown sets
        if self.counties is None:
            for i in range(9, plus_ix, 7):
                self.sub_printable(i, i + 7)
        else:
            weighted_counties = [(1 - (cx / 48.0), self.counties[cx]) for cx in range(0, len(self.counties))]
            for i in range(9, plus_ix, 7):
                self.sub_valid_codes(i, weighted_counties, median(self.message.confidence))
                while i+7 < plus_ix and len(weighted_counties) > 0 and weighted_counties[0][1] != str(self.message[i:i + 6]):
                    weighted_counties.pop(0)

        return self.message


class IncompleteSAMEMessage(Exception):
    pass


class AmbiguousSAMEMessage(Exception):
    def __init__(self, message):
        self.message = message


class SAMEMessage(CommonMessage):
    """
    A SAMEMessage represents a message from NWR.

    Responsibilities:
       - Collect the multiple headers
       - Know when it is fully received (timeout, enough messages, or external signal)
       - Aggregate headers
       - Know the certainty for aggregated headers
       - Know how to extract the information from the various fields of the SAME message
       - Implementation of the structure found in http://www.nws.noaa.gov/directives/sym/pd01017012curr.pdf
    """

    def __init__(self, transmitter, headers=None, received_callback=None):
        """
        :param transmitter: Call letters for the transmitter, so that FIPS codes can be checked.
        :param headers:  Headers for a legacy message to reconstitute, None if this is a new message,
           and a string if it's just for parsing.
        :param received_callback: A callable taking one parameter, this SAMEMessage, to be called once, on the
           occasion that this message is first fully received
        :return:
        """
        if transmitter is not None and transmitter[0] == '-':
            headers = transmitter
            transmitter = None

        self.transmitter = transmitter
        self.__avg_message = None
        self.received_callback = received_callback
        self.timeout = 0
        event_id = None
        if headers:
            if hasattr(headers, 'lower'):
                self.headers = None
                self.__avg_message = ConfidentString(headers, [9] * len(headers))
                self.start_time = time.time()
                try:
                    self.start_time = self.get_start_time_sec()
                except IncompleteSAMEMessage:
                    pass
                self.timeout = float("-inf")
                event_id = str(self.__avg_message)
            else:
                if not all(isinstance(x, SAMEHeader) for x in headers):
                    raise ValueError("Only SAMEHeaders or a single string can be in header")
                self.headers = headers
                self.start_time = headers[0].time
                self.timeout = self.start_time + 6
        else:
            self.headers = []
            self.start_time = time.time()
            self.timeout = self.start_time + 6

        self.published = self.start_time
        if event_id is None:
            event_id = "%s-%.3f" % (self.transmitter, self.start_time)
        self.event_id = event_id

    def add_header(self, header):
        if self.fully_received():
            raise ValueError("Message is already complete.")
        if not isinstance(header, SAMEHeader):
            raise ValueError("Only SAMEHeaders belong")
        self.headers.append(header)
        self.timeout = header.time + 6

    def get_areas(self):
        return self.get_counties()

    def fully_received(self, make_it_so=False, extend_timeout=False):
        """
        :param make_it_so: True to assert that the message has been fully received
        :param extend_timeout: True to extend the timeout if it has not been reached
        :return True if the message has been fully received, False otherwise
        """
        if make_it_so:
            self.timeout = float("-inf")
        complete = self.timeout < time.time() or len(self.headers) >= 3
        if complete and self.received_callback:
            cb = self.received_callback
            self.received_callback = None
            cb(self)
        if not complete and extend_timeout:
            self.timeout = time.time() + 6
        return complete

    def get_SAME_message(self):
        if self.fully_received():
            if self.__avg_message is None:
                self.__avg_message = SAMEMessageScrubber(self.headers, self.transmitter).scrub()
                mtype = str(self.__avg_message[5:8])
                level = default_prioritization(mtype)
                logging.getLogger("RPiNWR.same.message.%s.%s" % (self.get_originator(), mtype)).log(level, "%s", self)
            return self.__avg_message
        else:
            if len(self.headers) > 0:
                return SAMEMessageScrubber(self.headers, self.transmitter).scrub()
            else:
                return "", []

    def __getitem__(self, item):
        return self.get_SAME_message().__getitem__(item)

    def __len__(self):
        return self.get_SAME_message().__len__()

    def get_originator(self):
        return self[1:4]

    def get_event_type(self):
        return self[5:8]

    def get_counties(self):
        return str(self[9:self.__find_plus()]).split("-")

    def __find_plus(self):
        ix = self.get_SAME_message().find('+')
        if ix < 0:
            raise IncompleteSAMEMessage()
        return ix

    def get_duration_str(self):
        start = self.__find_plus() + 1
        return str(self[start:start + 4])

    def get_start_time_str(self):
        start = self.__find_plus() + 6
        return str(self[start:start + 7])

    def get_duration_sec(self):
        d_str = self.get_duration_str()
        return int(d_str[0:2]) * 60 * 60 + int(d_str[2:4]) * 60

    def get_start_time_sec(self):
        now = time.gmtime(self.start_time)
        year = now.tm_year
        issue_jday = int(self.get_start_time_str()[0:3])
        if now.tm_yday < 10 and issue_jday > 355:
            year -= 1
        elif now.tm_yday > 355 and issue_jday < 10:
            year += 1
        return calendar.timegm(time.strptime(str(year) + self.get_start_time_str() + 'UTC', '%Y%j%H%M%Z'))

    def get_end_time_sec(self):
        return self.get_start_time_sec() + self.get_duration_sec()

    def applies_to_fips(self, fips):
        """
        :param fips: A string representing the FIPS code with optional leading P component to indicate subset of county
        :return: True if the county was clearly included in the message, False if it was clearly not in the message,
            and None if there was uncertainty.
        """
        if len(fips) == 5:
            fips = '0' + fips
        if len(fips) != 6:
            raise ValueError()

        # TODO identify an uncertain match (i.e. there was ambiguity in the counties received)
        counties = [c[1:] for c in self.get_counties()]
        # TODO account for the partial counties
        return fips in counties

    def get_broadcaster(self):
        start = self.__find_plus() + 14
        return self[start:-1]

    def __str__(self):
        msg = self.get_SAME_message()
        return 'SAMEMessage: { "message":"%s", "confidence":"%s" }' % (
            unicodify(str(msg)), "".join([str(x) for x in msg.confidence]))

    def __repr__(self):
        return "SameMessage(%r,%r,%r)" % (self.transmitter, self.headers, self.received_callback)

    def to_dict(self):
        return {
            "message": self.get_SAME_message()[0],
            'confidence': self.get_SAME_message()[1],
            'headers': self.headers,
            "time": self.start_time
        }


def default_prioritization(event_type):
    """
    :param event_type: The event type code (3 letters)
    :return: a larger number for warnings, smaller for watches & emergencies, smaller for statements,
    and even smaller for tests.
    """
    if event_type == "EQW":
        return logging.CRITICAL + 10
    if event_type == "TOR":
        return logging.CRITICAL + 5
    elif event_type == "SVR" or event_type[2] == "W":
        return logging.CRITICAL
    elif event_type == "EVI" or event_type[2] == "E":
        return logging.WARNING  # Emergencies are not immediate threats
    elif event_type[2] == "T":
        return logging.DEBUG
    else:
        return logging.INFO


def default_SAME_sort(a, b):
    apri = default_prioritization(a.get_event_type())
    bpri = default_prioritization(b.get_event_type())
    delta = bpri - apri  # highest first
    if delta:
        return delta

    delta = b.get_start_time_sec() - a.get_start_time_sec()  # newest first
    if delta:
        return delta

    if a.get_event_type() > b.get_event_type():
        return 1
    elif a.get_event_type() < b.get_event_type():
        return -1

    if a.get_SAME_message() > b.get_SAME_message():
        return 1
    elif a.get_SAME_message() < b.get_SAME_message():
        return -1

    return 0


class SAMECache(object):
    """
    SAMECache holds a collection of (presumably recent) SAME messages.

    Responsibilities:
    0. Know its county
    1. Receive SAME messages
    3. Provide a list of effective messages for a specific county in priority order
    4. Clear out inactive messages upon request

    Collaborators:
    Si4707 to populate via SAME message events
    A consumer, to monitor the messages and clear out inactive messages
    """

    # TODO track the time since last received message for my fips, alert if >8 days
    # TODO monitor RSSI & SNR and alert if out of spec (what is spec)?
    def __init__(self, county_fips, same_sort=default_SAME_sort):
        self.__messages_lock = threading.Lock()
        self.__messages = []
        self.__elsewhere_messages = []
        self.__local_messages = []
        self.county_fips = county_fips
        self.same_sort = same_sort

    def add_message(self, message):
        with self.__messages_lock:
            if self.county_fips is None or message.applies_to_fips(self.county_fips):
                self.__messages.append(message)
            else:
                self.__elsewhere_messages.append(message)

    def get_active_messages(self, when=time.time, event_pattern=None, here=True):
        """
        :param when: the time for which to check effectiveness of the messages, default = the present time
        :param event_pattern: a regular expression to match the desired event codes.  default = all.
        :param here: True to retrieve local messages, False to retrieve those for other locales
        """
        if event_pattern is None:
            event_pattern = re.compile(".*")
        elif not hasattr(event_pattern, 'match'):
            event_pattern = re.compile(event_pattern)

        if here:
            msgs = self.__messages
        else:
            msgs = self.__elsewhere_messages

        l = list(filter(lambda m: m.is_effective(when) and event_pattern.match(m.get_event_type()), msgs))
        l.sort(key=functools.cmp_to_key(self.same_sort))
        return l

    def clear_inactive(self, when=None):
        with self.__messages_lock:
            self.__messages = self.get_active_messages(when)
            self.__elsewhere_messages = self.get_active_messages(when, here=False)


def unicodify(str):
    """
    :param str: An ASCII string
    :return: A string such that all the characters are printable, and the LSB of the Unicode representation
       is the same as the ASCII
    """
    # Put all the special ASCII characters into some readable place on the unicode character set
    # All of these transformations are chosen so that ord(c) & 0xFF is the ASCII character represented
    str = list(str)
    for i in range(0, len(str)):
        c = str[i]
        if ord(c) == 0:
            c = "⨀"
        elif ord(c) <= 0x1F:  # put these in the Unicode Control Pictures block
            c = chr(ord(c) | 0x2400)
        elif ord(c) > 126:  # grab some unicode symbols
            c = chr((ord(c) & 0xFF) | 0x1E00)
        str[i] = c
    return "".join(str)
