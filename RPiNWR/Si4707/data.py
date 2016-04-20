# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# A Python translation of the Si4707 instructions
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

import struct
from RPiNWR.Si4707.exceptions import StatusError

DEFAULT_CONFIG = {
    "properties": {
        "GPO_IEN": 207,
        "WB_RSQ_SNR_HI_THRESHOLD": 127,
        "WB_RSQ_SNR_LO_THRESHOLD": 1,
        "WB_RSQ_RSSI_HI_THRESHOLD": 77,
        "WB_RSQ_RSSI_LO_THRESHOLD": 7,
        "WB_SAME_INTERRUPT_SOURCE": 9,
        "WB_ASQ_INT_SOURCE": 1,
    },

    "power_on": {
        "cts_interrupt_enable": False,
        "gpo2_output_enable": True,
        "crystal_oscillator_enable": True,
        "patch":
            b"""
            eJwTZWBgWeerskvMfKPyGgYGBlEGhojXxce5xA7WvhTMW3BH7AmjVvzKlc5iJsbS0odc8sQOia1+1CNnJFZfNz1ys9ADsey
            De5a9yZIR2/bnQueOopViKYdbpLhrbMROWYs1cjdeF2uROe7JazBBrE9nBuPLirViamXruYXLD4rJfk5Ug9jHYjir763Y05
            KEBVB+gvY6fbGVrybOgPBVTkw5YCDWnX43lE0uXyzgw73/ph/ExWZtXvArf5ukWJXWMjUV9bVii+fLJ7EqcYgFMYAByJyyC
            v7HYn0bW3KgfPmiU8fEilMPXYHwmTKn3MgVu/UWpp7pjF5Qm5iAGYwPBBenAgBnLVz7
            """,
        "patch_id": 0xD195
    }
}

# TODO replace the default value with a map of bits where appropriate, including the mnemonic and offset
# and populate the value based on that in the Property object
PROPERTIES = [
    (0x0001, "GPO_IEN", "Enables interrupt sources.", 0x0000, lambda x: (x & 0xF030) == 0),
    # (0x0102, "DIGITAL_OUTPUT_FORMAT Configure digital audio outputs.", 0x0000, "Si4737/39/43"),
    # (0x0104, "DIGITAL_OUTPUT_SAMPLE_RATE Configure digital audio output sample rate.", 0x0000, "Si4737/39/43"),
    (0x0201,
     "REFCLK_FREQ",
     "Hz Sets frequency of reference clock in Hz. The range is 31130 to 34406 Hz, or 0 to disable the AFC. Default is 32768 Hz.",
     0x8000, lambda x: 31130 <= x <= 34406 or x == 0),
    (0x0202, "REFCLK_PRESCALE", "Sets the prescaler value for RCLK input.", 0x0001, lambda x: 1 <= x <= 4095),
    (0x5108, "WB_MAX_TUNE_ERROR",
     "kHz Sets the maximum freq error allowed before setting the AFC_RAIL indicator. Default value is 10 kHz.",
     0x000A, lambda x: 1 <= x <= 15),
    (0x5200, "WB_RSQ_INT_SOURCE", "Configures interrupt related to Received Signal Quality metrics.", 0x0000,
     lambda x: 0 <= x <= 15),
    (0x5201, "WB_RSQ_SNR_HI_THRESHOLD", "dB Sets high threshold for SNR interrupt.", 0x007F, lambda x: 0 <= x <= 127),
    (0x5202, "WB_RSQ_SNR_LO_THRESHOLD", "dB Sets low threshold for SNR interrupt.", 0x0000, lambda x: 0 <= x <= 127),
    (0x5203, "WB_RSQ_RSSI_HI_THRESHOLD", "dBµV Sets high threshold for RSSI interrupt.", 0x007F,
     lambda x: 0 <= x <= 127),
    (
        0x5204, "WB_RSQ_RSSI_LO_THRESHOLD", "dBµV Sets low threshold for RSSI interrupt.", 0x0000,
        lambda x: 0 <= x <= 127),
    (0x5403, "WB_VALID_SNR_THRESHOLD", "dBµV Sets SNR threshold to indicate a valid channel", 0x0003,
     lambda x: 0 <= x <= 127),
    (0x5404, "WB_VALID_RSSI_THRESHOLD", "dBµV Sets RSSI threshold to indicate a valid channel", 0x0014,
     lambda x: 0 <= x <= 127),
    (0x5500, "WB_SAME_INTERRUPT_SOURCE", "Configures SAME interrupt sources.", 0x0000, lambda x: 0 <= x <= 15),
    # Si4707 only
    (0x5600, "WB_ASQ_INT_SOURCE", "Configures interrupt related to the 1050 kHz alert tone", 0x0000,
     lambda x: 0 <= x <= 3),
    (0x4000, "RX_VOLUME", "Sets the output volume.", 0x003F, lambda x: 0 <= x <= 63),
    (0x4001, "RX_HARD_MUTE", "Mutes the audio output. L and R audio outputs may not be muted independently.",
     0x0000, lambda x: x == 0 or x == 3),
]


class Property(object):
    def __init__(self, mnemonic, value=None):
        found = False
        for (c, mn, description, default_value, validator) in PROPERTIES:
            if mn == mnemonic or c == mnemonic:
                found = True
                self.code = c
                self.mnemonic = mn
                self.validator = validator
                break
        if not found:
            raise KeyError(mnemonic)
        self.value = value

    def __str__(self):
        return type(self).__name__ + " [" + ', '.join("%s: %s" % item for item in vars(self).items()) + "]"


###############################################################################
# SYMBOLS
#
# A symbol corresponds to a term in the manual.
#
# Data symbols encapsulate the encoding and decoding of same.
# Command symbols (see below), encapsulate the execution of a command and the
# retrieval of its result.
###############################################################################
class Symbol(object):
    def __init__(self, mnemonic=None, value=None, valid_values=None):
        if mnemonic is None:
            self.mnemonic = type(self).__name__
        else:
            self.mnemonic = mnemonic
        self.value = value
        if valid_values is None:
            self.valid_values = value
        else:
            self.valid_values = valid_values

    def __str__(self):
        return type(self).__name__ + " [" + ', '.join("%s: %s" % item for item in vars(self).items()) + "]"


class Status(Symbol):
    def __init__(self, value):
        super(Status, self).__init__("STATUS", value[0])
        if self.is_clear_to_send() and self.is_error():
            raise StatusError(self)

    def is_clear_to_send(self):  # CTS
        return self.value & 1 << 7

    def is_error(self):
        return self.value & 1 << 6

    def is_received_signal_quality_interrupt(self):
        return self.value & 1 << 3

    def is_same_interrupt(self):
        return self.value & 1 << 2

    def is_audio_signal_quality_interrupt(self):
        return self.value & 1 << 1

    def is_seek_tune_complete(self):  # STC
        return self.value & 1

    def is_interrupt(self):
        return self.value & 0x0F


class PupRevision(Symbol):
    """
    Revision information coming from PowerUp function 15
    """

    def __init__(self, value):
        super(PupRevision, self).__init__()
        self.part_number, fmaj, fmin, chip_rev, self.library_id = \
            struct.unpack('>xBBBxxBB', bytes(value))
        self.firmware = chr(fmaj) + "." + chr(fmin)
        self.chip_revision = chr(chip_rev)


class Revision(Symbol):
    """
    Revision information from the GetRev command
    """

    def __init__(self, value):
        super(Revision, self).__init__()
        self.part_number, fmaj, fmin, self.patch_id, cmaj, cmin, self.chip_rev = \
            struct.unpack('>xBBBHBBB', bytes(value))
        self.firmware = chr(fmaj) + "." + chr(fmin)
        self.component_revision = chr(cmaj) + "." + chr(cmin)

