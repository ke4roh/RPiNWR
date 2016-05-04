# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# Mimic the Si4707 chip to test things that depend on it
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


from RPiNWR.Si4707 import Context, PROPERTIES, Property
import threading
import time
from RPiNWR.SAME import SAME_PATTERN
import struct
import logging
import re


class MockContext(Context):
    """
    This class provides a Context that behaves approximately like the Si4707.  It can produce messages and adjust
    signal quality.

    This class is intended for two purposes:
    * Testing implementations using Si4707
    * Testing the Si4707 implementation itself
    """
    # This mock includes an i2c facade because of how it came to be.
    # It would be nice to remove that feature...
    # TODO split out the I2C mock, Context, and the Si4707 mock
    def write_bytes(self, data):
        if len(data) == 1:
            self.write8(data[0], 0)
        else:
            self.writeList(data[0], data[1:])

    def read_bytes(self, num_bytes):
        return self.readList(0, num_bytes)

    def reset_radio(self):
        self.__init__()

    @staticmethod
    def getPiRevision():
        return 2

    @staticmethod
    def getPiI2CBusNumber():
        return 2

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __init__(self):
        self.bus = {
            0: [0] * 5
        }
        self.registers = {
            0: [128, 1, 2, 3, 4, 5, 6, 7]
        }
        self.OPMODE = 0  # 5 = Analog audio,
        self.props = dict([(x[0], x[3]) for x in PROPERTIES])
        self.power = False
        self.interrupts = 0
        self.asq_stopped = False
        self.asq_started = False
        self.asq_tone = False
        self.asq_lock = threading.Lock()
        self.same_status = [0] * 4
        self.same_buffer = [0] * 255
        self.same_confidence = [0] * 255
        self.same_lock = threading.Lock()

        # TODO add signal quality metrics for each channel
        self.rssi = 20
        self.snr = 29
        self.rsq_interrupts = 0  #
        self.afc_valid = 1  # 2= AFCRAIL (freqoff>WB_MAX_TUNE_ERROR), 1=valid
        self.freqoff = 1
        self._logger = logging.getLogger(type(self).__name__)
        self.agc = 1
        self.set_signal_quality()  # set the receive status interrupts appropriately

    def reverseByteOrder(self, data):
        "Reverses the byte order of an int (16-bit) or long (32-bit) value"
        # Courtesy Vishal Sapre
        byteCount = len(hex(data)[2:].replace('L', '')[::2])
        val = 0
        for i in range(byteCount):
            val = (val << 8) | (data & 0xff)
            data >>= 8
        return val

    def errMsg(self):
        raise NotImplemented()

    def write8(self, reg, value):
        self.bus[value][0] = reg
        self.__op(reg)

    def write16(self, reg, value):
        raise NotImplemented()

    def writeRaw8(self, value):
        raise NotImplemented()

    def writeList(self, reg, l):
        if type(l) is not list or len(l) < 1 or len(l) > 32:
            raise TypeError("Third argument must be a list of at least one, but not more than 32 integers")

        self.bus[reg] = l
        self.__op(reg)

    def readList(self, reg, length):
        while len(self.registers[reg]) < min(32, length):
            self.registers[reg].append(0)
        return self.registers[reg][0:length]

    def readU8(self, reg):
        raise NotImplemented()

    def readS8(self, reg):
        raise NotImplemented()

    def readU16(self, reg, little_endian=True):
        raise NotImplemented()

    def readS16(self, reg, little_endian=True):
        raise NotImplemented()

    def __op(self, reg):
        if reg == 0x01:  # Power up
            # CTSIEN GPO2OEN PATCH XOSCEN FUNC[3:0]
            # ARG2 OPMODE[7:0]
            # [(self.GPO2EN | self.PATCH | self.XOSCEN | self.WB), self.OPMODE
            self.CTSIEN = self.bus[reg][0] >> 7
            self.GPO2OEN = self.bus[reg][0] >> 6 & 1
            self.PATCH = self.bus[reg][0] >> 5 & 1
            self.XOSCEN = self.bus[reg][0] >> 4 & 1
            FUNC = self.bus[reg][0] & 15
            self.OPMODE = self.bus[reg][1]

            if FUNC == 3:  # WB Receive
                self.power = True
                self.registers[0][0] = 128
            elif FUNC == 15:  # Query Library ID
                self.registers[0] = [128, 7, 50, 48, 252, 255, 66, 9]
            else:
                self.registers[0][0] = 192  # CTS & ERR
        elif reg == 0x10:  # GET_REV
            self.registers[0] = [128, 7, 50, 48, 209, 149, 50, 48, 0]
        elif reg == 0x11:  # POWER_DOWN
            self.power = False
        elif reg == 0x12:  # SET_PROPERTY
            self.props[struct.unpack(">H", bytes(self.bus[reg][1:3]))] = struct.unpack(">H", bytes(self.bus[reg][3:5]))
            self.set_signal_quality()  # Check if the thresholds have been crossed
        elif reg == 0x13:  # GET_PROPERTY
            prop = struct.unpack(">H", bytes(self.bus[reg][1:3]))[0]
            propval = struct.pack(">H", self.props[prop])
            self.registers[0] = [128, 0, propval[0], propval[1], 0, 0, 0]
        elif reg == 0x14:  # GET_INT_STATUS (interrupt)
            self.registers[0][0] |= self.interrupts
        elif reg == 0x15 or reg == 0x16:  # patch data
            pass
        elif reg == 0x50:  # WB_TUNE_FREQ - tune the radio
            self.registers[0x50] = self.bus[reg][1:3]
            self.rsq_interrupts = 0
            self.afc_valid = 0

            def set_stc():
                self.set_signal_quality()
                self.interrupts |= 0x01

            threading.Timer(0.5, set_stc).start()
        elif reg == 0x52:  # WB_TUNE_STATUS
            if self.bus[reg][0]:
                self.interrupts ^= 1  # clear STCINT
            self.registers[0] = [128 | self.interrupts, self.afc_valid, self.registers[0x50][0],
                                 self.registers[0x50][1], self.rssi, self.snr]
        elif reg == 0x53:  # WB_RSQ_STATUS
            rsq = self.rsq_interrupts
            afc_valid = self.afc_valid
            if self.bus[reg][0]:
                self.interrupts ^= 9  # This clears RSQINT & STCINT
                self.rsq_interrupts = 0
                self.afc_valid ^= 2
            self.registers[0] = [128 | self.interrupts, rsq, afc_valid, 0, self.rssi, self.snr, 0, self.freqoff]
        elif reg == 0x54:  # WB_SAME_STATUS
            with self.same_lock:
                if self.bus[reg][0] & 1:  # INTACK
                    self.interrupts ^= 4
                if self.bus[reg][0] & 2:  # CLEARBUF
                    for i in range(0, len(self.same_buffer)):
                        self.same_buffer[i] = 0
                        self.same_confidence[i] = 0
                    for i in range(0, len(self.same_status)):
                        self.same_status[i] = 0

                # Now assemble the response
                resp = self.registers[0] = [0] * 14
                resp[0] = 128 | self.interrupts
                for i in range(1, 4):
                    resp[i] = self.same_status[i]
                for i in range(0, 8):
                    if self.bus[reg][1] + i < len(self.same_buffer):
                        resp[i + 6] = self.same_buffer[self.bus[reg][1] + i]
                        resp[int((7 - i) / 4) + 4] |= self.same_confidence[i] << (i % 4 * 2)

                if self.bus[reg][0] & 1:  # INTACK
                    self.same_status[1] = 0
        elif reg == 0x55:  # WB_ASQ_STATUS - alert tone detection
            with self.asq_lock:
                if self.bus[reg][0]:
                    self.interrupts ^= 2

                self.registers[0] = [128 | self.interrupts, self.asq_started | self.asq_stopped << 1, self.asq_tone]

                if self.bus[reg][0]:
                    self.asq_stopped = 0
                    self.asq_started = 0
        elif reg == 0x57:  # WB_AGC_STATUS
            self.registers[0] = [128 | self.interrupts, self.agc]
        elif reg == 0x58:  # WB_AGC_OVERRIDE
            self.agc = self.bus[reg][0]
        else:
            logging.error("Command not mocked 0x%02X" % reg)
            self.registers[0][0] = 192

    def alert_tone(self, playing=False):
        with self.asq_lock:
            if self.asq_tone != playing:
                self.asq_stopped |= not playing
                self.asq_started |= playing
                self.asq_tone = playing
                self.interrupts |= 2

    def send_message(self,
                     message='-WXR-RWT-020103-020209-020091-020121-029047-029165-029095-029037+0030-3031700-KEAX/NWS',
                     tone=8.0, noise=None, header_count=3, voice_duration=15.0, eom=3, time_factor=1.0,
                     invalid_message=False):
        """
        :param message: A valid SAME message
        :param tone: the number of seconds for which to sound the tone, None for no tone
        :param noise: A factor 0-1 (no more than 0.04ish for success), indicating how much noise to sprinkle into the
           messages.  None indicates that noise should not be added.
        :param header_count: The number of headers to send (3 or fewer in case of sketchy circumstances)
        :param voice_duration: The number of seconds to wait before EOM
        :param eom: The number of EOMs to send (3 or fewer)
        :param time_factor: Multiply all the timings by this to expedite testing
        :param invalid_message: to permit an invalid message going into the Si4707 emulation as if by noise
        """
        # There is some parameter checking here because it is much easier to diagnose here than in a separate thread.
        # TODO Add noise commensurate with SNR and RSSI by default
        if not invalid_message and not SAME_PATTERN.match(message):
            raise ValueError()
        for num in [tone, noise, header_count, voice_duration, eom]:
            if num is not None:  # None should be fine for these things
                num + 1  # This will give a ValueError if it's not a number
        time_factor + 1  # This needs to be a number

        threading.Timer(0, self.send_message0,
                        [message, tone, time_factor, noise, header_count, voice_duration, eom]).start()

    def send_message0(self, message, tone, time_factor, noise, header_count, voice_duration, eom):
        ###
        # Do these things in turn:
        # SOM
        # 3x:
        #   PREAMBLE
        #   (populate the message)
        #   HDRRDY
        # TONE?
        # voice?
        # EOM
        ###
        try:
            with self.same_lock:
                self.same_status[1] |= 4  # SOMDET - start of message
                self.interrupts |= 4  # SAMEINT

            # Messages come in at 520.83 baud, 8 bits per char, 65.1 chars/sec = .0154 sec/char
            CHAR_TIME = 1 / 520.83 * 8

            for m in range(0, header_count):
                time.sleep(CHAR_TIME * 16 * time_factor)  # Preamble - 16 bytes
                with self.same_lock:
                    self.same_status[1] |= 2  # PREDET
                    self.same_status[2] = 1  # Preamble detected
                    self.interrupts |= 4  # SAMEINT

                time.sleep(CHAR_TIME * 4 * time_factor)  # ZCZC
                msg_start_time = time.time()
                for i in range(0, len(message)):
                    with self.same_lock:
                        self.same_buffer[i] = ord(message[i]) & 0xFF
                        self.same_confidence[i] = 3  # unless we introduce noise
                        self.same_status[3] = max(i, self.same_status[3])
                        self.same_status[2] = 2  # receiving SAME header
                    sleep_for = CHAR_TIME * time_factor * i + msg_start_time - time.time()
                    if sleep_for > 0:
                        time.sleep(sleep_for)

                with self.same_lock:
                    self.same_status[2] = 3  # SAME header message complete
                    self.same_status[1] |= 1  # HDRRDY
                    self.interrupts |= 4  # SAMEINT
                time.sleep(1 * time_factor)  # 1 sec pause between messages

            if tone:
                self.alert_tone(True)
                time.sleep(tone * time_factor)
                self.alert_tone(False)

            if voice_duration:
                time.sleep(voice_duration * time_factor)

            for m in range(0, eom):
                time.sleep(1 * time_factor)
                time.sleep(CHAR_TIME * 4 * time_factor)
                with self.same_lock:
                    self.same_status[1] |= 8  # EOMDET
                    self.same_status[2] = 0  # EOM detected
                    self.interrupts |= 4  # SAMEINT

        except Exception:
            self._logger.exception("Exception in message generator")

    @staticmethod
    def _parse_cmd(cmd, regex, func):
        re.compile(regex)
        m = re.match(cmd)
        if m:
            func(*m.groups())
            return True
        return None

    def _get_property(self, mnemonic):
        return self.props.get(Property(mnemonic).code)

    def set_signal_quality(self, rssi=None, snr=None, freqoff=None):
        """
        Set signal quality & compute interrupts and flags accordingly.
        Protip: if you set_signal_quality in the first half second after issuing the tune command,
           the signal quality you set is the signal quality for that channel.  Implementation may be
            slightly challenging, though, because this Si4707 class blocks the command thread until STCINT
            which comes at that time.
        :param rssi: signal strength
        :param snr: signal to noise ratio
        :param freqoff:
        :return:
        """
        if rssi is not None:
            self.rssi = rssi
        if snr is not None:
            self.snr = snr
        if freqoff is not None:
            self.freqoff = freqoff
        self.afc_valid |= 1
        if self.snr < self._get_property("WB_RSQ_SNR_LO_THRESHOLD"):
            self.rsq_interrupts |= 4
            self.interrupts |= 8
            self.afc_valid ^= 1
        if self.snr > self._get_property("WB_RSQ_SNR_HI_THRESHOLD"):
            self.rsq_interrupts |= 8
            self.interrupts |= 8
            self.afc_valid ^= 1
        if self.rssi < self._get_property("WB_RSQ_RSSI_LO_THRESHOLD"):
            self.rsq_interrupts |= 1
            self.interrupts |= 8
            self.afc_valid ^= 1
        if self.rssi > self._get_property("WB_RSQ_RSSI_HI_THRESHOLD"):
            self.rsq_interrupts |= 2
            self.interrupts |= 8
            self.afc_valid ^= 1
        if self.freqoff > self._get_property("WB_MAX_TUNE_ERROR"):
            self.afc_valid |= 2
            self.interrupts |= 8
            self.afc_valid ^= 1

    def run_script(self, script):
        """
        Control the mock of the radio for simulating receipt of messages etc..

        :param script: One line per instruction
        :return: None, upon completion
        """
        for line in filter(lambda x: len(x), [x.strip() for x in script]):
            if MockContext._parse_cmd(line, "sleep (\d(?:\.\d))", lambda t: time.sleep(t)) or \
                    MockContext._parse_cmd(line, "send (-[^ ]*)",
                                           lambda msg: self.send_message(message=msg, tone=0, voice_duration=1)) or \
                    MockContext._parse_cmd(line, "alert (-[^ ]*)",
                                           lambda msg: self.send_message(message=msg, voice_duration=1)):
                pass
            else:
                raise ValueError("Unknown command %s" % line)
