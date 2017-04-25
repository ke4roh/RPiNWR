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
from .CommonMessage import CommonMessage

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


# faux-mutates a string by transforming it into a list, making changes, and casting it back to a string
def mutate_string(string, old_char, new_char):
    """
    :param string: string to "mutate"
    :param old_char: an int representing the index of the char which we want to change
    :param new_char: a char, this is what we want to change the old_char to
    """
    listmsg = list(string)
    listmsg[old_char] = new_char
    # new_str is what we're returning as the result of our mutation
    new_str = ''.join(listmsg)
    return new_str


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
    # TODO refine confidence calculation to make more sense
    end_confidence = int((confidence_chars * __median(confidences) - winner[0]) / confidence_chars)

    # Lay in the characters we just checked
    fips_count = int((len(avgmsg) - len(_END_SEQUENCE) - 8) / 7)
    frame = '-___-___' + ('-______' * fips_count) + _END_SEQUENCE
    assert len(frame) == len(avgmsg)

    for i in range(0, len(avgmsg)):
        if frame[i] != '_':
            if avgmsg[i] != frame[i]:
                avgmsg = mutate_string(avgmsg, i, frame[i])
                confidences[i] = end_confidence
            else:
                confidences[i] = max(end_confidence, confidences[i])

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
    from ..sources.radio.nwr_data import get_counties, get_wfo

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

            mutate_string(avgmsg, i, c)
        confidences[i] = min(9, byte_confidence >> 3)
    avgmsg = "".join(avgmsg)

    # Now break the message into its parts and clean up each one
    avgmsg, confidences, matched = _reconcile_word(avgmsg, confidences, 1, _ORIGINATOR_CODES)
    avgmsg, confidences, matched = _reconcile_word(avgmsg, confidences, 5, _EVENT_CODES)

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

    return unicodify(avgmsg), confidences[0:len(avgmsg)]

# -WXR-TOR-039173-039051-139069+0030-1591829-KCLE/NWS
SAME_PATTERN = re.compile('-(EAS|CIV|WXR|PEP)-([A-Z]{3})((?:-\\d{6})+)\\+(\\d{4})-(\\d{7})-([A-Z/]+)-?')


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
                self.__avg_message = (headers, '9' * len(headers))
                self.start_time = time.time()
                self.start_time = self.get_start_time_sec()
                self.timeout = float("-inf")
                event_id = self.__avg_message[0]
            else:
                self.headers = headers
                self.start_time = headers[0][2]
                self.timeout = self.start_time + 6
        else:
            self.headers = []
            self.start_time = time.time()
            self.timeout = self.start_time + 6

        self.published = self.start_time
        if event_id is None:
            event_id = "%s-%.3f" % (self.transmitter, self.start_time)
        self.event_id = event_id

    def add_header(self, header, confidence):
        if self.fully_received():
            raise ValueError("Message is already complete.")
        when = time.time()
        try:
            confidence[0] + 'a'
        except TypeError:
            confidence = "".join([str(x) for x in confidence])
        self.headers.append((unicodify(header), confidence, when))
        self.timeout = when + 6

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
                self.__avg_message = average_message(self.headers, self.transmitter)
                mtype = self.get_event_type()
                level = default_prioritization(mtype)
                logging.getLogger("RPiNWR.same.message.%s.%s" % (self.get_originator(), mtype)).log(level, "%s", self)
            return self.__avg_message
        else:
            if len(self.headers) > 0:
                return average_message(self.headers)
            else:
                return "", []

    def get_originator(self):
        return self.get_SAME_message()[0][1:4]

    def get_event_type(self):
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
        msg, confidence = self.get_SAME_message()
        for i in range(15, len(msg) - 20, 7):
            match = True
            for x in range(-1, -6, -1):
                match &= msg[i + x] == fips[x]
                if not match:
                    break
            match &= fips[0] == '0' or msg[i - 6] == '0' or fips[0] == msg[i - 6]
            if match:
                return True

        return False

    def get_broadcaster(self):
        m = self.get_SAME_message()[0]
        start = m.find('+') + 14
        return m[start:-1]

    def __str__(self):
        msg = self.get_SAME_message()
        return 'SAMEMessage: { "message":"%s", "confidence":"%s" }' % (
            unicodify(msg[0]), "".join([str(x) for x in msg[1]]))

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
    delta = bpri - apri # highest first
    if delta:
        return delta

    delta = b.get_start_time_sec() - a.get_start_time_sec() # newest first
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
