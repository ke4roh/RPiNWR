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

import logging
from .data import *
from .events import *
from RPiNWR.messages import SAME
# import RPiNWR.messages.SAME as SAME

###############################################################################
# COMMANDS
#
# Commands are issued to the radio to manipulate it.
###############################################################################
class Command(Symbol):
    def __init__(self, mnemonic=None, value=None):
        """
        A Command represents a transactional exchange with the Si4707.

        The instance, which relates to a particular execution, contains:
          - configuration for a particular execution
          - results from an execution
          - a Future which will provide those results to callers from other thread(s)

        Class methods:
          - Communicate with radio.context to execute a transaction
          - Update state on radio as necessary
          - Dispatch user-level events relating to key events

        :param mnemonic: The short string from the manual about what this thing does, or null to use the class name
        :param value: The constant used to invoke this command
        """
        super(Command, self).__init__(mnemonic, value)
        self.future = None
        self.exception = None
        self.result = None
        self.time_complete = None
        self._logger = logging.getLogger(type(self).__name__)

    def do_command(self, radio):
        try:
            result = self.do_command0(radio)
            if result == self:
                result = "self"
            self.result = result
            if self.future:
                self.future.result(self.result)
        except Exception as e:
            self._logger.exception("failed")
            self.exception = e
            if self.future:
                self.future.exception(e)
            else:
                raise
        finally:
            self.future = None
            self.time_complete = time.time()

    def do_command0(self, radio):
        # This implementation will handle a rudimentary command with no args
        radio.context.write_bytes([self.value])
        return radio.wait_for_clear_to_send()

    def _check_interrupt(self, radio):
        pass

    def get_priority(self):
        return 2

    def __str__(self):
        return type(self).__name__ + " [" + ', '.join(
            "%s: %s" % item for item in filter(lambda x: x[1] != self, vars(self).items())) + "]"


def _bit(value, offset):
    """Prepare a binary value as a bit with the given offset)"""
    # this is just syntactic sugar
    return (value and True) << offset


class PowerUp(Command):
    """Initiates the boot process to move the device from powerdown to powerup mode.
    :param function: either 3 (WB receive) or 15 (query library ID)
    :param patch: False.  See PatchCommand for how to patch.
    :param cts_interrupt_enable: True if you want an interrupt to accompany CTS
    :param gpo2_output_enable: True to use the general-purpose output pins from teh Si4707, false otherwise
    :param crystal_oscillator_enable:
    :param opmode -
        00000101 = Analog audio outputs (LOUT/ROUT)
        00001011 = Digital audio output (DCLK, LOUT/DFS, ROUT/DIO)
        10110000 = Digital audio outputs (DCLK, DFS, DIO) (Si4743 component 2.A or higher with XOSCEN = 0)
        10110101 = Analog and digital outputs (LOUT/ROUT and DCLK, DFS, DIO) (Si4743 component 2.A or higher with XOSCEN = 0)
    """

    def __init__(self, cts_interrupt_enable=False, gpo2_output_enable=True, crystal_oscillator_enable=True,
                 patch=False, function=3, opmode=0x05):
        super(PowerUp, self).__init__("POWER_UP", 0x01)
        if function not in [3, 15]:
            raise ValueError("function 0x%02X" % function)
        if opmode not in [0x05, 0x0B, 0xB0, 0xB5]:
            raise ValueError("opmode 0x%02X" % opmode)
        self.cts_interrupt_enable = cts_interrupt_enable
        self.gpo2_output_enable = gpo2_output_enable
        self.crystal_oscillator_enable = crystal_oscillator_enable
        self.patch = patch
        self.function = function
        self.opmode = opmode
        self.status = Status([0])

    def do_command0(self, radio):
        result = self.do_command00(radio)
        if self.function == 15:
            result = radio.revision = PupRevision(radio.context.read_bytes(8))
        else:
            radio.radio_power = True
            radio._fire_event(RadioPowerEvent(True))
            if self.crystal_oscillator_enable:
                radio.tune_after = time.time() + 0.5
                radio._delay_event(ReadyToTuneEvent(), radio.tune_after)
            else:
                radio.tune_after = float("-inf")
                radio._fire_event(ReadyToTuneEvent())
        return result

    def do_command00(self, radio):
        radio.context.write_bytes([self.value,
                                   _bit(self.cts_interrupt_enable, 7) |
                                   _bit(self.gpo2_output_enable, 6) |
                                   _bit(self.patch, 5) |
                                   _bit(self.crystal_oscillator_enable, 4) |
                                   self.function,
                                   self.opmode])
        return radio.wait_for_clear_to_send()

    def get_priority(self):
        return 0


class PatchCommand(PowerUp):
    def __init__(self, patch, patch_id=None, cts_interrupt_enable=True, gpo2_output_enable=True,
                 crystal_oscillator_enable=True, opmode=0x05):
        """
        This command will patch the firmware while powering up the radio.

        See PowerUp.__init__ for descriptions of the other arguments.
        :param patch: base64 encoded, zlib-compressed patch
        :param patch_id: the 4-byte hex code to verify the patch has been applied correctly
        """
        super(PatchCommand, self).__init__(
            cts_interrupt_enable=cts_interrupt_enable, gpo2_output_enable=gpo2_output_enable,
            crystal_oscillator_enable=crystal_oscillator_enable, patch=True, function=3,
            opmode=opmode
        )
        self.patch = patch
        self.patch_id = patch_id

    def do_command00(self, radio):
        super(PatchCommand, self).do_command00(radio)
        patch = self.__decompress_patch(self.patch)

        for i in range(0, len(patch), 8):
            radio.context.write_bytes(list(patch[i:i + 8]))
            radio.wait_for_clear_to_send()

        new_rev = GetRevision().do_command0(radio)
        # Revision [mchip_rev: 0, patch_id: 53653, component_revision: 2.0, part_number: 7, firmware: 2.0]
        if self.patch_id:
            assert new_rev.patch_id == self.patch_id
        # TODO check chip/Firmware/Comp[onent] Rev

        return new_rev


    @staticmethod
    def __decompress_patch(patch):
        import zlib
        import base64

        # Revision [mchip_rev: 0, patch_id: 53653, component_revision: 2.0, part_number: 7, firmware: 2.0]
        return zlib.decompress(base64.b64decode(patch))


class CommandRequiringPowerUp(Command):
    """
    Most commands require the radio power to be on, so this checks.
    """

    def do_command(self, radio):
        if not radio.radio_power:
            raise ValueError("Attempted %s when powered down" % type(self).__name__)
        return super(CommandRequiringPowerUp, self).do_command(radio)


class GetRevision(CommandRequiringPowerUp):
    def __init__(self):
        super(GetRevision, self).__init__(mnemonic="GET_REV", value=0x10)

    def do_command0(self, radio):
        super(GetRevision, self).do_command0(radio)
        revision = radio.revision = Revision(radio.context.read_bytes(9))
        return revision


class PowerDown(CommandRequiringPowerUp):
    """Switch off the receiver."""

    def __init__(self):
        super(PowerDown, self).__init__("POWER_DOWN", 0x11)

    def do_command0(self, radio):
        super(PowerDown, self).do_command0(radio)
        radio.radio_power = False
        radio._fire_event(RadioPowerEvent(False))

    def get_priority(self):
        return 0


class SetProperty(CommandRequiringPowerUp):
    def __init__(self, property_mnemonic, new_value):
        super(SetProperty, self).__init__(mnemonic="SET_PROPERTY", value=0x12)
        p = self.property = Property(property_mnemonic, new_value)
        if not p.validator(new_value):
            raise ValueError("0x%04X out of range" % new_value)

    def do_command0(self, radio):
        c = [self.value]
        c.extend(list(struct.pack(">bHH", 0, self.property.code, self.property.value)))
        radio.context.write_bytes(c)


class GetProperty(CommandRequiringPowerUp):
    def __init__(self, property_mnemonic):
        super(GetProperty, self).__init__(mnemonic="GET_PROPERTY", value=0x13)
        self.property = Property(property_mnemonic)

    def do_command0(self, radio):
        radio.context.write_bytes([self.value, 0, self.property.code >> 8, self.property.code & 0xFF])
        radio.wait_for_clear_to_send()
        self.property.value = struct.unpack(">xxH", bytes(radio.context.read_bytes(4)))[0]
        return self.property.value


class TuneFrequency(CommandRequiringPowerUp):
    def __init__(self, frequency):
        """
        :param frequency in MHz (will be converted for the radio)
        """
        super(TuneFrequency, self).__init__(mnemonic="WB_TUNE_FREQ", value=0x50)
        if not 162.4 <= frequency <= 162.55:
            raise ValueError("%.2f MHz out of range" % frequency)
        self.frequency = int(400 * frequency + 0.5)
        self.rssi = None
        self.snr = None

    def do_command0(self, radio):
        while time.time() < radio.tune_after:
            # check back occasionally to see if the tune_after might have changed favorably
            time.sleep(max(.1, radio.tune_after - time.time()))
        c = [self.value]
        c.extend(list(struct.pack(">bH", 0, self.frequency)))
        radio.context.write_bytes(c)
        radio.tone_start = None
        while not radio.check_interrupts().is_seek_tune_complete():  # wait for STC
            time.sleep(0.02)
        ts = TuneStatus(True)
        ts.do_command(radio)
        if ts.frequency != self.frequency:
            raise ValueError("Frequency didn't stick: requested %02X != %02X" % (self.frequency, ts.frequency))
        self.rssi = ts.rssi
        self.snr = ts.snr
        return self.rssi, self.snr, ts.frequency / 400.0


class TuneStatus(CommandRequiringPowerUp):
    def __init__(self, intack=False):
        super(TuneStatus, self).__init__(mnemonic="WB_TUNE_STATUS", value=0x52)
        self.intack = intack
        self.frequency = None
        self.rssi = None
        self.snr = None

    def do_command0(self, radio):
        radio.context.write_bytes([self.value, self.intack & 1])  # Acknowledge STC, get tune status
        radio.wait_for_clear_to_send()
        bl = radio.context.read_bytes(6)
        self.frequency, self.rssi, self.snr = struct.unpack(">xxHbb", bytes(bl))
        return self.frequency / 400.0, self.rssi, self.snr


class InterruptHandler(CommandRequiringPowerUp):
    def get_priority(self):
        return 1


class ReceivedSignalQualityCheck(InterruptHandler):
    def __init__(self, intack=False):
        super(ReceivedSignalQualityCheck, self).__init__(mnemonic="WB_RSQ_STATUS", value=0x53)
        self.intack = intack
        self.rssi = None
        self.asnr = None
        self.frequency_offset = None
        self.afc_rail = None
        self.valid_channel = None
        self.snr_high = None
        self.snr_low = None
        self.rssi_high = None
        self.rssi_low = None

    def do_command0(self, radio):
        radio.context.write_bytes([self.value, self.intack & 1])
        radio.wait_for_clear_to_send()
        violation_flags, validity, self.rssi, self.asnr, self.frequency_offset = \
            struct.unpack(">xbbxbbxb", bytes(radio.context.read_bytes(8)))
        self.afc_rail = validity & 2 != 0
        self.valid_channel = validity & 1 != 0
        self.snr_high = violation_flags & 8 != 0
        self.snr_low = violation_flags & 4 != 0
        self.rssi_high = violation_flags & 2 != 0
        self.rssi_low = violation_flags & 1 != 0
        return self


class AlertToneCheck(InterruptHandler):
    def __init__(self, intack=False):
        super(AlertToneCheck, self).__init__(mnemonic="WB_ASQ_STATUS", value=0x55)
        self.intack = intack
        self.tone_start = None
        self.tone_end = None
        self.tone_on = None
        self.duration = None

    def do_command0(self, radio):
        radio.context.write_bytes([self.value, self.intack & 1])
        radio.wait_for_clear_to_send()
        history, present = \
            struct.unpack(">xbb", bytes(radio.context.read_bytes(3)))
        self.tone_start = history & 1 != 0
        self.tone_end = history & 2 != 0
        self.tone_on = present != 0
        radio._dispatch_any_message(True)
        if self.tone_on:
            radio.tone_start = time.time()
        else:
            if radio.tone_start is not None:
                self.duration = time.time() - radio.tone_start
                radio.tone_start = None


class SameInterruptCheck(InterruptHandler):
    def __init__(self, intack=False, clearbuf=False):
        super(SameInterruptCheck, self).__init__(mnemonic="WB_SAME_STATUS", value=0x54)
        self.status = None
        self.intack = intack
        self.clearbuf = clearbuf

    def do_command0(self, radio):
        def dispatch_message(message):
            if radio.same_message == message:
                radio.same_message = None
                self.__get_status(radio, clearbuf=True)
            if len(message.headers) > 0:
                radio._fire_event(SAMEMessageReceivedEvent(message))

        self.status = status = self.__get_status(radio, intack=self.intack, clearbuf=self.clearbuf)
        if self.intack:
            if status["EOMDET"]:
                if radio.same_message:
                    radio.same_message.fully_received(True)
                if time.time() - radio.last_EOM > 5:  # Send EOM only once for 3 repetitions
                    radio.last_EOM = time.time()
                    radio._fire_event(EndOfMessage())
            if status["PREDET"]:
                if not radio.same_message or radio.same_message.fully_received(extend_timeout=True):
                    radio.same_message = SAME.SAMEMessage(radio.transmitter, received_callback=dispatch_message)
            if status["HDRRDY"]:
                if not radio.same_message or radio.same_message.fully_received():
                    radio.same_message = SAME.SAMEMessage(radio.transmitter, received_callback=dispatch_message)
                msg = list(self.status["MESSAGE"])
                conf = list(self.status["CONFIDENCE"])
                msg_len = self.status["MSGLEN"]
                while len(msg) < msg_len:
                    st = self.__get_status(radio, readaddr=len(msg))
                    msg.extend(st["MESSAGE"])
                    conf.extend(st["CONFIDENCE"])
                msg = msg[0:msg_len + 1]
                conf = conf[0:msg_len + 1]
                radio.same_message.add_header(SAME.SAMEMessage("".join([chr(c) for c in msg]), conf))
                self.__get_status(radio, clearbuf=True)
                radio._fire_event(SAMEHeaderReceived(radio.same_message))

    def __str__(self):
        msg = type(self).__name__ + " ["
        if self.status:
            if self.status["EOMDET"]:
                msg += "EOMDET "
            if self.status["SOMDET"]:
                msg += "SOMDET "
            if self.status["PREDET"]:
                msg += "PREDET "
            if self.status["HDRRDY"]:
                msg += "HDRRDY "

        if self.clearbuf:
            msg += "clearbuf "
        if self.intack:
            msg += "intack "

        if self.status is not None:
            msg += "len = %d " % self.status["MSGLEN"]
            msg += "state = %d " % self.status["STATE"]
            msg += "m=%s " % self.status["MESSAGE"]
        msg += "]"
        return msg

    def __get_status(self, radio, readaddr=0, clearbuf=False, intack=False):
        radio.context.write_bytes([self.value, (clearbuf & 1) << 1 | (intack & 1), readaddr])
        radio.wait_for_clear_to_send()
        data = radio.context.read_bytes(14)
        confidence = [0] * 8
        for i in range(0, 8):
            confidence[i] = data[int((7 - i) / 4) + 4] >> (i % 4 * 2) & 0x3

        return {
            "EOMDET": (data[1] & 8) != 0,
            "SOMDET": (data[1] & 4) != 0,
            "PREDET": (data[1] & 2) != 0,
            "HDRRDY": (data[1] & 1) != 0,
            "STATE": data[2],
            "MSGLEN": data[3],
            "CONFIDENCE": confidence,
            "MESSAGE": data[6:14]
        }


class GetAGCStatus(CommandRequiringPowerUp):
    def __init__(self):
        super(GetAGCStatus, self).__init__(mnemonic="WB_AGC_STATUS", value=0x57)

    def do_command0(self, radio):
        super(GetAGCStatus, self).do_command0(radio)
        return radio.context.read_bytes(2)[1] != 0


class SetAGCStatus(CommandRequiringPowerUp):
    def __init__(self, enable):
        super(SetAGCStatus, self).__init__(mnemonic="WB_AGC_OVERRIDE", value=0x58)
        self.enable = enable

    def do_command0(self, radio):
        radio.context.write_bytes([self.value, self.enable & 1])
        radio.wait_for_clear_to_send()


class Callback(Command):
    """
    As a convenience to call a function from the command queue (to change an LED or a relay which might
    be related to the context and not thread-safe, for example).  Do not make this take long, because
    we have to get back over to checking the interrupts fairly quickly.  If you have something that will
    take a long time, run it from the event queue or some other thread.
    """

    def __init__(self, function, args=None, kw_args=None):
        super(Callback, self).__init__(mnemonic="Callback")
        self.function = function
        self.args = args
        self.kw_args = kw_args

    def do_command0(self, radio):
        a = self.args
        if a is None:
            a = []
        k = self.kw_args
        if k is None:
            k = {}
        return self.function(*a, **k)
