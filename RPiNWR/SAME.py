# -*- coding: utf-8 -*-
__author__ = 'ke4roh'

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

_ORIGINATORS = [
    ("Broadcast station or cable system","EAS"),
    ("Civil authorities", "CIV"),
    ("National Weather Service", "WXR"),
    ("Primary Entry Point System", "PEP")
]
_ORIGINATOR_CODES = list([x[1] for x in _ORIGINATORS])

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
_EVENT_CODES = list([x[1] for x in _EVENT_TYPES])

def _reconcile_character(bitstrue, bitsfalse, pattern):
    """
    :param bitstrue: an array of numbers specifying the weights favoring each bit in turn being true, LSB first
    :param bitsfalse: like bitstrue, but favoring bits being false
    :param pattern: A string containing all the possible characters for the spot
    :return: confidence, char - a tuple with confidence and the character
    """
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
__SAME_CHARS = [
    '-', 'ECWP', 'AIXE', 'SVRP', '-', __ALPHA, __ALPHA, __ALPHA, '-',
    __NUMERIC, __NUMERIC, __NUMERIC, __NUMERIC, __NUMERIC, __NUMERIC, -7,
    '+', __NUMERIC, __NUMERIC, '0134', '05', '-',
    '0123', __NUMERIC, __NUMERIC, '012', __NUMERIC, '012345', __NUMERIC, '-',
    __ALPHA, __ALPHA, __ALPHA, __ALPHA, '/', 'N', 'W', 'S'
]

def average_message(messages):
    """
    Compute a weighted average of the bits of various messages supplied.
    :param messages: an array of tuples, each containing a string message and an array of confidence values.
       All arrays need to be the same length.
    :return: a tuple containing a single string corresponding to the most certain available data, and
             the combined confidence for each character (range 1-9)
    """
    size = len(messages[0][0])
    bitstrue = [0] * 8 * size
    bitsfalse = [0] * 8 * size
    confidences = [0] * size
    avgmsg = ''

    # First look through the messages and compute sums of confidence of bit values
    for (msg, confidence) in messages:
        for i in range(0, len(msg)):
            for j in range(0, 8):
                if (ord(msg[i]) >> j) & 1:
                    bitstrue[(i << 3) + j] += 1 * confidence[i]
                else:
                    bitsfalse[(i << 3) + j] += 1 * confidence[i]

    # Then combine that information into a single aggregate message
    byte_pattern_index = 0
    for i in range(0, size):
        # Assemble a character from the various bits
        c = 0
        byte_confidence = 0
        for j in range(0, 8):
            bit_weight = (bitstrue[(i << 3) + j] - bitsfalse[(i << 3) + j])
            c |= (bit_weight > 0) << j
            byte_confidence += abs(bit_weight)
        c = chr(c)

        # Check the character against the space of possible characters
        pattern = __SAME_CHARS[byte_pattern_index]
        multipath = None  # Where the pattern can repeat, multipath supports both routes
        if type(pattern) is int:
            multipath = pattern
            pattern = __SAME_CHARS[byte_pattern_index + multipath] + __SAME_CHARS[
                byte_pattern_index + 1]
        if c not in pattern:
            # That was ugly.  Now find the closest legitimate character
            byte_confidence, c = _reconcile_character(bitstrue[i:i + 8], bitsfalse[i:i + 8], pattern)
            byte_confidence <<= 3  # It will get shifted back in a moment
        if not multipath:
            byte_pattern_index += 1
        else:
            if c in __SAME_CHARS[byte_pattern_index + 1]:
                byte_pattern_index += 2
            else:
                byte_pattern_index += multipath + 1

        avgmsg += c
        confidences[i] = byte_confidence >> 3

    # TODO consider a third level of resolving ambiguity from errror by further limiting the possibilities based
    #    on strings in each segment of the message.
    return avgmsg, confidences

# -WXR-TOR-039173-039051-139069+0030-1591829-KCLE/NWS
SAME_PATTERN = re.compile('-(EAS|CIV|WXR|PEP)-([A-Z]{3})((?:-\\d{6})+)\\+(\\d{4})-(\\d{7})-([A-Z/]+)')

class SAMEMessage(object):
    def __init__(self, same_message):
        """
        The SAME message is parsed here.
        """
        m = SAME_PATTERN.match(same_message)
        (self.originator, self.event_type, geography, self.purge_time, self.issue_time, self.broadcaster) = m.group(
            *range(1, 7))
        self.geography = geography.split()[1:]
        now = time.gmtime(time.time())
        year = now.tm_year
        issue_jday = int(self.issue_time[0:3])
        if now.tm_yday < 10 and issue_jday > 355:
            year -= 1
        elif now > 355 and issue_jday < 10:
            year += 1
        self.effective_time = time.mktime(time.strptime(str(year) + self.issue_time + 'UTC', '%Y%j%H%M%Z'))
        self.exipry_time = self.effective_time + int(self.purge_time[0:2]) * 60 * 60 + int(self.purge_time[2:4]) * 60

    def __str__(self):
        return \
            "SAMEMessage: { Originator: %s  Type: %s  Places: %s  issueTime: %s  purgeTime: %s  broadcaster: %s }" % \
            (self.originator, self.event_type, self.geography.join(', '), self.issue_time, self.purge_time,
             self.broadcaster)
