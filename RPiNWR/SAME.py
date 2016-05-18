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
import math
from RPiNWR.nwr_data import *

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


def _reconcile_character(bitstrue, bitsfalse, pattern):
    """
    :param bitstrue: an array of numbers specifying the weights favoring each bit in turn being true, LSB first
    :param bitsfalse: like bitstrue, but favoring bits being false
    :param pattern: A string containing all the possible characters for the spot
    :return: confidence, char - a tuple with confidence and the character
    """
    if sum(bitstrue) == 0 and len(pattern) > 1:  # only nulls received, more than 1 possibility
        return 0, chr(0)
    near = []
    for t in list(pattern):
        distance = 0
        for j in range(0, 8):
            bit_weight = bitstrue[j] - bitsfalse[j]
            if ((ord(t) >> j) & 1) != (bit_weight > 0) & 1:
                distance += abs(bit_weight)
        near.append((distance, t))
    near.sort()
    if len(near) == 1 or near[0][0] != near[1][0]:
        confidence = 2
    else:
        confidence = 1
    return confidence, near[0][1]

# -WXR-TOR-039173-039051-139069+0030-1591829-KCLE/NWS
__ALPHA = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
__NUMERIC = '0123456789'
__PRINTABLE = '\x10\x13' + "".join(filter(lambda x: ord(x) != 43 and ord(x) != 45, [chr(x) for x in range(33, 127)]))
__SAME_CHARS = [
    '-', 'ECWP', 'AIXE', 'SVRP', '-', __ALPHA, __ALPHA, __ALPHA, '-',
    __PRINTABLE, __PRINTABLE, __PRINTABLE, __PRINTABLE, __PRINTABLE, __PRINTABLE, -7,
    '+', __NUMERIC, __NUMERIC, '0134', '05', '-',
    '0123', __NUMERIC, __NUMERIC, '012', __NUMERIC, '012345', __NUMERIC, '-',
    __ALPHA, __ALPHA, __ALPHA, __ALPHA, '/', 'N', 'W', 'S', '-'
]


def _word_distance(word, confidence, choice, wildcard=None):
    d = 0
    for i in range(0, len(choice)):
        if len(word) > i:
            if choice[i] != wildcard and word[i] != choice[i]:
                try:
                    d += 1 + confidence[i]
                except TypeError:
                    d += int(1 + confidence[i])
        else:
            return d + (len(word) - i + 1) * 9
    return d


def __median(lst):
    # http://stackoverflow.com/a/29870273/2544261
    quotient, remainder = divmod(len(lst), 2)
    if remainder:
        return sorted(lst)[quotient]
    return float(sum(sorted(lst)[quotient - 1:quotient + 1]) / 2)


def _reconcile_word(msg, confidences, start, choices):
    """

    :param msg: the whole message
    :param confidences: confidences for each character in the message
    :param start: the index at which to look for the choices
    :param choices: a list of choices that might appear at the given index, or tuples of weight and choice
    if there are different probabilities for different possibilities
    :return: a tuple of the corrected message, the corresponding confidence (as an array of ints range 0-9),
         and a boolean indicating if a suitable match was found
    """
    if not len(choices):
        # If there are no choices, status-quo is best we can do
        return msg, confidences, False
    if len(msg) <= start:
        return msg, confidences, False

    matched = False
    try:
        confidences[0] + 1
    except TypeError:
        confidences = list([int(x) for x in confidences])
    try:
        choices[0][0] + 0
    except TypeError:
        choices = list([(1, x) for x in choices])

    end = start + len(choices[0][1])
    word = msg[start:end]
    confidence = confidences[start:end]
    candidates = []
    for weight, c in choices:
        candidates.append(((_word_distance(word, confidence, c) + 1) / weight, c))
    candidates.sort()
    if candidates[0][0] < max(4, __median(confidences)) and (
                    len(candidates) == 1 or candidates[0][0] < candidates[1][0]):
        word = candidates[0][1]
        # Update the confidence
        base_confidence = max(0, int(max(4, max(confidences[start:end])) - candidates[0][0] / (end - start)))
        for i in range(start, end):
            if msg[i] != word[i - start]:
                confidences[i] = base_confidence
        # replace the word
        l = list(msg)
        l[start:end] = list(word)
        msg = "".join(l)
        matched = True
    return msg, confidences, matched


def __rindex(lst, thing):
    """:return the last occurrence of thing, None if it wasn't there."""
    lst.reverse()
    try:
        ix = -1 - lst.index(thing)
    except ValueError:
        ix = None
    lst.reverse()
    return ix


_END_SEQUENCE = "+0___-_______-____/NWS-"


def _truncate(avgmsg, confidences):
    """
    Compute the length of the message and fill in the punctuation characters.

    :param avgmsg:
    :param confidences:
    :return: tuple same as the parameters, with updated values
    """
    if len(avgmsg) < 38:
        # It's too short; there's no hope
        return avgmsg, confidences

    candidates = []
    for l in range(38, len(avgmsg) + 1, 7):
        candidates.append((_word_distance(avgmsg[l - 23:l], confidences, _END_SEQUENCE, '_'), l))

    winner = min(candidates)
    l = winner[1]
    avgmsg = avgmsg[0:l]
    confidences = confidences[0:l]

    confidence_chars = len(_END_SEQUENCE.replace("_", ""))
    # The confidence is greater for a match than each character being right.
    end_confidence = int((confidence_chars * __median(confidences) - winner[0]) / pow(confidence_chars, -2))

    # Lay in the characters we just checked
    avgmsg[-23] = '+'
    confidences[-23] = end_confidence
    avgmsg[-5] = '/'
    confidences[-5] = end_confidence
    avgmsg[-1] = '-'
    confidences[-1] = end_confidence

    # And infer every other separator from those
    avgmsg[0] = '-'
    confidences[0] = end_confidence
    avgmsg[4] = '-'
    confidences[4] = end_confidence
    for i in range(8, len(avgmsg) - 23, 7):
        avgmsg[i] = '-'
    confidences[i] = end_confidence
    avgmsg[-18] = '-'
    confidences[-18] = end_confidence
    avgmsg[-10] = '-'
    confidences[-10] = end_confidence
    return avgmsg, confidences


def average_message(headers, transmitter):
    """
    Compute the correct message by averaging headers, restricting input to the valid character set, and filling
    in expected values when it's unambiguous based on other parts of the message.

    :param headers: an array of tuples, each containing a string message and an array (or string) of confidence values.
       The complete message is assumed to be as long as the longest message, and messages align at the start.
    :return: a tuple containing a single string corresponding to the most certain available data, and
             the combined confidence for each character (range 1-9)
    """
    # This implementation undertakes several steps
    # 1. Compute the best 2 out of 3 for every bit, weighted by confidence
    # 2. Compute the confidence of each byte (agreeing confidences - disagreeing confidences)
    # 3. Figure out what the length is by looking at sentinel characters
    # 4. Lay down all the sentinel characters
    # 5. Check that characters are in the valid set for the section of the message
    # 6. Substitute any low-confidence data with data from the list of possible values
    # TODO factor this into different functions to do the work and test them separately
    size = max([len(x[0]) for x in headers])
    bitstrue = [0] * 8 * size
    bitsfalse = [0] * 8 * size
    confidences = [0] * size

    # First look through the messages and compute sums of confidence of bit values
    for (msg, c, when) in headers:
        if type(c) is str:
            confidence = [int(x) for x in c]
        else:
            confidence = c
        # Loop through the characters of the message
        for i in range(0, len(msg)):
            if ord(msg[i]):  # null characters don't count b/c they indicate no data, not all 0 bits
                # Loop through bits and apply confidence for true or false
                for j in range(0, 8):
                    if (ord(msg[i]) >> j) & 1:
                        bitstrue[(i << 3) + j] += 1 * confidence[i]
                    else:
                        bitsfalse[(i << 3) + j] += 1 * confidence[i]

    # Then combine that information into a single aggregate message
    avgmsg = []
    byte_pattern_index = 0
    for i in range(0, size):
        # Assemble a character from the various bits
        c = 0
        confidences[i] = 0
        for j in range(0, 8):
            bit_weight = (bitstrue[(i << 3) + j] - bitsfalse[(i << 3) + j])
            c |= (bit_weight > 0) << j
            confidences[i] += abs(bit_weight)
        if c == 0:
            confidences[i] = 0
        avgmsg.append(chr(c))

    # Figure out the length
    avgmsg, confidences = _truncate(avgmsg, confidences)

    # Check the character against the space of possible characters
    for i in range(0, len(avgmsg)):
        c = avgmsg[i]
        byte_confidence = confidences[i]
        if False and len(__SAME_CHARS) <= byte_pattern_index:
            confidences[i] = 0
        else:
            pattern = __SAME_CHARS[byte_pattern_index]
            multipath = None  # Where the pattern can repeat, multipath supports both routes
            if type(pattern) is int:
                multipath = pattern
                pattern = __SAME_CHARS[byte_pattern_index + multipath] + __SAME_CHARS[
                    byte_pattern_index + 1]
            if c not in pattern:
                # That was ugly.  Now find the closest legitimate character
                byte_confidence, c = _reconcile_character(bitstrue[i * 8:(i + 1) * 8], bitsfalse[i * 8:(i + 1) * 8],
                                                          pattern)
                byte_confidence <<= 3  # It will get shifted back in a moment
            if not multipath:
                byte_pattern_index += 1
            else:
                if c in __SAME_CHARS[byte_pattern_index + 1]:
                    byte_pattern_index += 2
                else:
                    byte_pattern_index += multipath + 1

            avgmsg[i] = c
        confidences[i] = min(9, byte_confidence >> 3)
    avgmsg = "".join(avgmsg)

    # Now break the message into its parts and clean up each one
    if avgmsg[1:4] not in _ORIGINATOR_CODES:
        avgmsg, confidences, matched = _reconcile_word(avgmsg, confidences, 1, _ORIGINATOR_CODES)
    if avgmsg[5:8] not in _EVENT_CODES:
        avgmsg, confidences, matched = _reconcile_word(avgmsg, confidences, 5, _ORIGINATOR_CODES)

    # Reconcile FIPS codes (which, in some non-weather types of messages, may not be FIPS)
    try:
        candidate_fips = list(get_counties(transmitter))
    except KeyError:
        candidate_fips = []

    try:
        wfo = [get_wfo(transmitter)]
    except KeyError:
        wfo = []

    def check_fips(avgmsg, confidences, ixlist):
        recheck = []
        matched1 = False
        for ix in ixlist:
            avgmsg, confidences, matched = _reconcile_word(avgmsg, confidences, ix - 1, ['-'])
            avgmsg, confidences, matched = _reconcile_word(avgmsg, confidences, ix,
                                                           [(1.1, '0'), (1, '1'), (1, '2'), (1, '3'), (1, '4'),
                                                            (1, '5'), (1, '6'), (1, '7'), (1, '8'), (1, '9')])
            avgmsg, confidences, matched = _reconcile_word(avgmsg, confidences, ix + 1,
                                                           list([x[-5:] for x in candidate_fips]))
            matched1 |= matched
            if matched:
                if avgmsg[ix:ix + 6] in candidate_fips:
                    candidate_fips.remove(avgmsg[ix:ix + 6])
            else:
                recheck.append(ix)
        return avgmsg, confidences, matched1, recheck

    # Check off counties until the maximum number have been reconciled
    matched = True
    recheck = range(9, len(avgmsg) - 23, 7)
    while matched and len(recheck) > 0:
        avgmsg, confidences, matched, recheck = check_fips(avgmsg, confidences, recheck)
    # TODO add a modest bias for adjacent counties to resolve ties in bytes

    # Reconcile purge time
    ix = len(avgmsg) - 23
    avgmsg, confidences, matched = _reconcile_word(avgmsg, confidences, ix, ['+'])
    ix += 1
    avgmsg, confidences, matched = _reconcile_word(avgmsg, confidences, ix, VALID_DURATIONS)

    # Reconcile issue time
    ix += 5
    valid_times = []
    for weight, offset in ((.5, -4), (.7, -3), (.9, -2), (1.1, -1), (1, 0)):
        valid_times.append((weight, time.strftime('%j%H%M', time.gmtime(headers[0][2] + 60 * offset))))
    avgmsg, confidences, matched = _reconcile_word(avgmsg, confidences, ix, valid_times)

    # Reconcile the end
    ix += 8
    avgmsg, confidences, matched = _reconcile_word(avgmsg, confidences, ix, wfo)

    ix += 5
    avgmsg, confidences, matched = _reconcile_word(avgmsg, confidences, ix, ['NWS'])

    return _unicodify(avgmsg), confidences[0:len(avgmsg)]

# -WXR-TOR-039173-039051-139069+0030-1591829-KCLE/NWS
SAME_PATTERN = re.compile('-(EAS|CIV|WXR|PEP)-([A-Z]{3})((?:-\\d{6})+)\\+(\\d{4})-(\\d{7})-([A-Z/]+)-?')


class SAMEMessage(object):
    """
    A SAMEMessage represents a message from NWR.

    Responsibilities:
       - Collect the multiple headers
       - Know when it is fully received (timeout, enough messages, or external signal)
       - Aggregate headers
       - Know the certainty for aggregated headers
       - Know how to extract the information from the various fields of the SAME message
       - Render itself in CAP and a dict
    """

    def __init__(self, transmitter, headers=None):
        """
        :param transmitter: Call letters for the transmitter, so that FIPS codes can be checked.
        :param headers:  Headers for a legacy message to reconstitute, None if this is a new message,
           and a string if it's just for parsing.
        :return:
        """
        if transmitter is not None and transmitter[0] == '-':
            headers = transmitter
            transmitter = None

        self.transmitter = transmitter
        self.__avg_message = None
        self.timeout = 0
        if headers:
            if hasattr(headers, 'lower'):
                self.headers = None
                self.__avg_message = (headers, '9' * len(headers))
                self.start_time = time.time()
                self.start_time = 0
                self.timeout = float("-inf")
            else:
                self.headers = headers
                self.start_time = headers[0][2]
                self.timeout = self.start_time + 6
        else:
            self.headers = []
            self.start_time = time.time()
            self.timeout = self.start_time + 6

    def add_header(self, header, confidence):
        if self.fully_received():
            raise ValueError("Message is already complete.")
        when = time.time()
        try:
            confidence[0] + 'a'
        except TypeError:
            confidence = "".join([str(x) for x in confidence])
        self.headers.append((_unicodify(header), confidence, when))
        self.timeout = when + 6

    def fully_received(self, make_it_so=False):
        if make_it_so:
            self.timeout = float("-inf")
        return self.timeout < time.time() or len(self.headers) >= 3

    def extend_timeout(self):
        if self.fully_received():
            raise ValueError("Message is already complete.")
        self.timeout = time.time() + 6

    def get_SAME_message(self):
        if self.fully_received():
            if self.__avg_message is None:
                self.__avg_message = average_message(self.headers, self.transmitter)
                mtype = self.get_message_type()
                if mtype == "TOR" or mtype == "SVR" or mtype[2] == "W":
                    level = logging.CRITICAL
                elif mtype == "EVI" or mtype[2] == "E":
                    level = logging.WARNING  # Emergencies are not immediate threats
                else:
                    level = logging.INFO
                logging.getLogger("RPiNWR.same.message.%s.%s" % (self.get_originator(), mtype)).log(level, "%s", self)
            return self.__avg_message
        else:
            if len(self.headers) > 0:
                return average_message(self.headers)
            else:
                return "", []

    def get_originator(self):
        return self.get_SAME_message()[0][1:4]

    def get_message_type(self):
        return self.get_SAME_message()[0][5:8]

    def get_counties(self):
        m = self.get_SAME_message()[0]
        return m[9:m.find('+')].split("-")

    def get_duration_str(self):
        m = self.get_SAME_message()[0]
        start = m.find('+') + 1
        return m[start:start + 4]

    def get_start_time_str(self):
        m = self.get_SAME_message()[0]
        start = m.find('+') + 6
        return m[start:start + 7]

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
        return time.mktime(time.strptime(str(year) + self.get_start_time_sec() + 'UTC', '%Y%j%H%M%Z'))

    def get_broadcaster(self):
        m = self.get_SAME_message()[0]
        start = m.find('+') + 14
        return m[start:-1]

    def __str__(self):
        msg = self.get_SAME_message()
        return 'SAMEMessage: { "message":"%s", "confidence":"%s" }' % (
            _unicodify(msg[0]), "".join([str(x) for x in msg[1]]))

    def to_dict(self):
        return {
            "message": self.get_SAME_message()[0],
            'confidence': self.get_SAME_message()[1],
            'headers': self.headers,
            "time": self.start_time
        }


def _unicodify(str):
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
