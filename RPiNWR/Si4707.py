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

import queue
import time
import heapq
import threading
import struct
import logging

# This file is an implementation of the software-level concerns for operating the Si4707 chip.
# It turns on the radio, receives messages, alert tones, and so forth, but it does not do any
# further processing of the data to, for example, decide what to do with a message.
#
# Ref http://www.silabs.com/Support%20Documents/TechnicalDocs/AN332.pdf
#

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
        return _simple_members(self)


class Status(Symbol):
    def __init__(self, value):
        super(Status, self).__init__("STATUS", value[0])
        if self.is_clear_to_send() and self.is_error():
            raise StatusError(self)

    def is_clear_to_send(self):  # CTS
        return self.value & 1 << 7

    def is_error(self):
        return self.value & 1 << 6

    def is_rqs_interrupt(self):
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


###############################################################################
# COMMANDS
#
# Commands are issued to the radio to manipulate it.
###############################################################################
class Command(Symbol):
    def __init__(self, mnemonic=None, value=None):
        """
        An instance of a command represents a postulated invocation of that command against the radio.

        :param mnemonic: The short string from the manual about what this thing does, or null to use the class name
        :param value: The constant used to invoke this command
        """
        super(Command, self).__init__(mnemonic, value)
        self.future = None
        self.exception = None
        self.result = None
        self.time_complete = None

    def do_command(self, radio):
        try:
            self.result = self.do_command0(radio)
            if self.future:
                self.future.result(self.result)
        except Exception as e:
            logging.exception(type(self).__name__ + " failed")
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
        radio.hardware_io.write8(self.value, 0)
        return radio.wait_for_clear_to_send()

    def _check_interrupt(self, radio):
        pass

    def get_priority(self):
        return 2

    def __str__(self):
        return _simple_members(self)


class UninterruptableCommand(Command):
    """Commands extending this abstract type will not be preempted for interrupts."""

    def get_priority(self):
        return 0


def _bit(value, offset):
    """Prepare a binary value as a bit with the given offset)"""
    # this is just syntactic sugar
    return (value and True) << offset


class PowerUp(UninterruptableCommand):
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
            result = radio.revision = PupRevision(radio.hardware_io.readList(0, 8))
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
        radio.hardware_io.writeList(self.value, [
            _bit(self.cts_interrupt_enable, 7) |
            _bit(self.gpo2_output_enable, 6) |
            _bit(self.patch, 5) |
            _bit(self.crystal_oscillator_enable, 4) |
            self.function,
            self.opmode])
        return radio.wait_for_clear_to_send()


class PatchCommand(PowerUp):
    def __init__(self, patch, patch_id=None, cts_interrupt_enable=True, gpo2_output_enable=True, crystal_oscillator_enable=True, opmode=0x05):
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
            radio.hardware_io.writeList(patch[i], list(patch[i + 1:i + 8]))
            radio.wait_for_clear_to_send()

        new_rev = GetRevision().do_command0(radio)
        if self.patch_id:
            assert new_rev.patch_id == self.patch_id
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
            raise ValueError("Power up before " + type(self).__name__)
        return super(CommandRequiringPowerUp, self).do_command(radio)


class GetRevision(CommandRequiringPowerUp):
    def __init__(self):
        super(GetRevision, self).__init__(mnemonic="GET_REV", value=0x10)

    def do_command0(self, radio):
        super(GetRevision, self).do_command0(radio)
        revision = radio.revision = Revision(radio.hardware_io.readList(0, 9))
        return revision


class PowerDown(CommandRequiringPowerUp):
    """Switch off the receiver."""

    def __init__(self):
        """
        :param stop - if radio commands are to stop processing after this one, false otherwise
        """
        super(PowerDown, self).__init__("POWER_DOWN", 0x11)

    def do_command0(self, radio):
        super(PowerDown, self).do_command0(radio)
        radio.radio_power = False
        radio._fire_event(RadioPowerEvent(False))

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
        return _simple_members(self)


class SetProperty(CommandRequiringPowerUp):
    def __init__(self, property_mnemonic, new_value):
        super(SetProperty, self).__init__(mnemonic="SET_PROPERTY", value=0x12)
        p = self.property = Property(property_mnemonic, new_value)
        if not p.validator(new_value):
            raise ValueError("0x%04X out of range" % new_value)

    def do_command0(self, radio):
        radio.hardware_io.writeList(
            self.value,
            list(struct.pack(">bHH", 0, self.property.code, self.property.value))
        )


class GetProperty(CommandRequiringPowerUp):
    def __init__(self, property_mnemonic):
        super(GetProperty, self).__init__(mnemonic="GET_PROPERTY", value=0x13)
        self.property = Property(property_mnemonic)

    def do_command0(self, radio):
        radio.hardware_io.writeList(self.value, [0, self.property.code >> 8, self.property.code & 0xFF])
        radio.wait_for_clear_to_send()
        self.property.value = struct.unpack(">xxH", bytes(radio.hardware_io.readList(0, 4)))[0]
        return self.property.value


class TuneFrequency(CommandRequiringPowerUp):
    def __init__(self, frequency):
        """
        :param frequency in MHz (will be converted for the radio)
        """
        super(TuneFrequency, self).__init__(mnemonic="WB_TUNE_FREQ", value=0x50)
        if not 162.4 <= frequency <= 162.55:
            raise ValueError("%.2f MHz out of range" % frequency)
        self.frequency = int(400 * frequency)
        self.rssi = None
        self.snr = None

    def do_command0(self, radio):
        if time.time() < radio.tune_after:
            time.sleep(radio.tune_after - time.time())

        radio.hardware_io.writeList(self.value, list(struct.pack(">bH", 0, self.frequency)))
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
    def __init__(self, ack_stc=False):
        super(TuneStatus, self).__init__(mnemonic="WB_TUNE_STATUS", value=0x52)
        self.frequency = None
        self.rssi = None
        self.snr = None

    def do_command0(self, radio):
        radio.hardware_io.writeList(self.value, [0x01])  # Acknowledge STC, get tune status
        radio.wait_for_clear_to_send()
        bl = radio.hardware_io.readList(0, 6)
        logging.debug(str(bl))
        self.frequency, self.rssi, self.snr = struct.unpack(">xxHbb", bytes(bl))
        return self.frequency / 400.0, self.rssi, self.snr


###############################################################################
# EVENTS
#
# Events occur after significant activity having to do with the radio.
###############################################################################
class Si4707Event(object):
    """
    Some radio-level thing happened.
    """

    def __init__(self):
        self.time = time.time()

    def __str__(self):
        return _simple_members(self)


class RadioError(Si4707Event):
    """
    This event occurs if a command was not processed properly.
    """

    def __init__(self, command):
        super(RadioError, self).__init__()
        self.command = command


class CommandExceptionEvent(Si4707Event):
    """
    There was a problem executing commands
    """

    def __init__(self, exception, passed_back):
        """
        :param exception - what went wrong
        :param passed_back - true if the exception has been passed back to the caller (in which case
        it's mostly useful for diagnostics).
        """

        super(CommandExceptionEvent, self).__init__()
        self.exception = exception
        self.passed_back = passed_back


class EventProcessingExceptionEvent(Si4707Event):
    """
    There was a problem executing commands
    """

    def __init__(self, exception):
        super(EventProcessingExceptionEvent, self).__init__()
        self.exception = exception


class NotClearToSend(Exception):
    """
    Clear To Send did not happen before the timeout
    """
    pass


class RadioPowerEvent(Si4707Event):
    """
    Sent when the radio is turned on or off.
    """

    def __init__(self, power_on):
        super(RadioPowerEvent, self).__init__()
        self.power_on = power_on


class ReadyToTuneEvent(Si4707Event):
    """
    Sent after power-up when the oscillator has had time to stabilize
    """
    pass


class Si4707(object):
    def __init__(self, hardware_io):
        self.__event_queue = queue.Queue(maxsize=50)
        self.__command_queue = queue.PriorityQueue(maxsize=50)
        self.__command_serial_number = 0
        self.__command_serial_number_lock = threading.Lock()
        self.__event_listeners = []
        self.__delayed_events = []
        self.__delayed_event_lock = threading.Lock()
        self.tune_after = float("inf")
        self.hardware_io = hardware_io
        self.radio_power = False  # Off to begin with
        self.status = None  # Gonna fix this in __enter__
        self.stop = False  # True to stop threads
        self.__shutdown = False  # True once shutdown has commenced

    def __enter__(self):
        for t in [threading.Thread(target=self.__command_loop),
                  threading.Thread(target=self.__event_loop)]:
            t.setDaemon(False)
            t.start()
        try:
            self.wait_for_clear_to_send(timeout=5)
            logging.info("Si4707 ready")
        except Exception:
            logging.exception("Startup failed")
            raise
        return self

    def __command_loop(self):
        while not self.stop:
            command = None
            try:
                # TODO look for an interrupt here
                # self.is_interrupted(...)
                # radio.wait_for_clear_to_send()
                # self._check_interrupt(radio)
                command = self.__command_queue.get_nowait()[1]
                logging.debug("Executing " + str(command))
                command.do_command(self)
                if command.exception:
                    self._fire_event(CommandExceptionEvent(command.exception, passed_back=True))
                else:
                    self._fire_event(command)
            except queue.Empty:
                # Take this opportunity to reset the command serial number
                if self.__command_serial_number > 5000:
                    with self.__command_serial_number_lock:
                        if self.__command_queue.empty():
                            self.__command_serial_number = 0
                time.sleep(0.05)
            except Exception as e:
                logging.exception("Surprise in command queue processing")
                self._fire_event(CommandExceptionEvent(e, passed_back=False))
            finally:
                if command is not None:
                    self.__command_queue.task_done()

        # Empty out the queue
        try:
            raise Si4707StoppedException()
        except Si4707StoppedException as se:
            stopped_exception = se
        while not self.__command_queue.empty():
            try:
                cmd = self.__command_queue.get(block=False)[1]
                if cmd.future:
                    cmd.future.exception(stopped_exception)
            except queue.Empty:
                pass  # Success!
        self.__command_queue = None

    def __event_loop(self):
        def dispatch_event(event):
            for listener in self.__event_listeners:
                listener(event)

        def get_delayed_events():
            """
            :return: As many delayed events as are due to be executed, empty array if none.
            """
            events = []
            with self.__delayed_event_lock:
                while len(self.__delayed_events) and heapq.nsmallest(1, self.__delayed_events)[0][0] <= time.time():
                    events.append(heapq.heappop(self.__delayed_events))
            for ev in events:
                ev[1].time = time.time()
                logging.debug("Firing for t=%f (%d ms late)" % (ev[0], int((time.time() - ev[0]) * 1000)))
            return list([x[1] for x in events])

        # Here begins the body of __event_loop
        while not self.stop or not self.__event_queue.empty():
            try:
                for e in get_delayed_events():
                    dispatch_event(e)
                dispatch_event(self.__event_queue.get(block=True, timeout=0.05))
                self.__event_queue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                self._fire_event(EventProcessingExceptionEvent(e))
        self.__event_queue = None

    def _delay_event(self, event, when):
        """
        Fire an event after a time
        :param event: the event
        :param when: the time.time() at which to fire the event
        """
        with self.__delayed_event_lock:
            heapq.heappush(self.__delayed_events, (when, event))
        logging.debug("Scheduled " + str(event) + " for " + str(when) + " which is " + str(
            int((when - time.time()) * 1000)) + " ms in the future.")

    def wait_for_clear_to_send(self, timeout=1.0):
        """
        :param: timeout - in seconds, how long to wait.  Default=1
        :return: the current status which can be inspected for CTS
        :raises: StatusError if the status indicates CTS and an error
                 NotClearToSend if the time expires without getting a CTS
        """
        if timeout is not None:
            expiry = timeout + time.time()
        while expiry is None or time.time() < expiry:
            self.status = Status(self.hardware_io.readList(0, 1))
            if self.status.is_clear_to_send():
                return self.status
            else:
                time.sleep(.002)
        raise NotClearToSend()

    def check_interrupts(self):
        """
        Ask the chip if there are interrupts.  Update status accordingly.

        :return: the result of Status.is_interrupt() which is true if there are any, and bitwise indicates
        the actual interrupts at hand, but subsequent examination of self.status is preferable for identifying
        which interrupts.
        """
        self.wait_for_clear_to_send(timeout=5)
        self.hardware_io.write8(0x14, 0)  # GET_INT_STATUS Tell Si4707 to populate interrupt bits
        return self.wait_for_clear_to_send(timeout=.1)

    def register_event_listener(self, callback):
        """
        :param callback: A function taking one parameter, an SI4707Event.  This method will be called for every event.
        """
        self.__event_listeners.append(callback)

    def _fire_event(self, event):
        """
        Put an event on the event queue
        """
        self.__event_queue.put_nowait(event)

    def power_on(self, configuration=None):
        config = DEFAULT_CONFIG
        if configuration is not None:
            config = dict(DEFAULT_CONFIG)
            config.update(configuration)

        if config["power_on"].get("patch"):
            # TODO check if the revision makes sense
            # PupRevision [chip_revision: B, library_id: 9, part_number: 7, firmware: 2.0]
            # Revision [mchip_rev: 0, patch_id: 53653, component_revision: 2.0, part_number: 7, firmware: 2.0]
            self.do_command(PatchCommand(**config["power_on"]))
        else:
            self.do_command(PowerUp())

        for (prop, value) in config["properties"].items():
            self.set_property(prop, value)

        if config.get("frequency"):
            self.tune(config["frequency"])
        else:
            self.scan()

    def power_off(self):
        return self.do_command(PowerDown()).get()

    def shutdown(self, hard=True):
        """Shut down the radio completely.  Turn off, stop threads.  Finished.
        :param hard - if True, preempt any commands that might already be in the command queue, and fail them.
          Otherwise, put the PowerDown at the end of the command queue and let it execute
        """
        logging.debug("Shutting down Si4707")
        if not self.__shutdown:
            self.__shutdown = True
            if self.radio_power:
                if hard:
                    # Put in a PowerDown command immediately
                    off = PowerDown()
                    off.future = Future()
                    self.__command_queue.put_nowait((0, off))
                    # wait for it to finish
                    off.future.get()
                else:
                    self.power_off()
            self.stop = True

            while self.__event_queue is not None or self.__command_queue is not None:
                time.sleep(.002)
            logging.debug("Si4707 stopped")

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.shutdown(False)
        except Exception as e:
            print(str(e))
        finally:
            self.__shutdown = True
            self.stop = True

    def do_command(self, command):
        """
        Put a command on the queue for execution.

        """
        if self.stop:
            raise Si4707StoppedException()

        # The serial number is important for scheduling and sequencing
        with self.__command_serial_number_lock:
            serial = self.__command_serial_number
            self.__command_serial_number += 1

        command.future = Future()
        self.__command_queue.put_nowait((serial << command.get_priority(), command))
        return command.future

    def get_property(self, property_mnemonic):
        """
        :param property_mnemonic: The name of the property to get
        :return: The value of the property
        :raise KeyError if property_mnemonic is unknown
        """
        return self.do_command(GetProperty(property_mnemonic)).get()

    def set_property(self, property_mnemonic, value):
        """
        :param property_mnemonic: The name of the property to set
        :param value: the new value of the property
        :raise ValueError if the value is out of range for the property
               KeyError if property_mnemonic is unknown
        """
        return self.do_command(SetProperty(property_mnemonic, value)).get()

    def tune(self, frequency):
        """
        Change the channel
        :param frequency: MHz
        :return: a tuple of RSSI (dBµV), SNR (dB), and frequency
        """
        return self.do_command(TuneFrequency(frequency)).get()

    def tune_status(self):
        """
        Check on the radio
        :return: a tuple of frequency (MHz), RSSI (dBµV), and SNR (dB)
        """
        return self.do_command(TuneStatus()).get()

    def set_volume(self, loud):
        """
        :param loud: 0<=loud<=63
        """
        if loud > 63:
            loud = 63
        if loud < 0:
            loud = 0
        self.set_property("RX_VOLUME", int(loud))

    def get_volume(self):
        """
        :return:  0<=loud<=63
        """
        return self.get_property("RX_VOLUME")

    def get_mute(self):
        return self.get_property("RX_HARD_MUTE") > 0

    def mute(self, hush):
        """
        :param hush: True to mute the speaker, False otherwise
        """
        self.set_property("RX_HARD_MUTE", (hush & 1) * 3)

    def scan(self):
        """
        Check the signal strength on every channel and pick the best one
        :return: a tuple containing rssi, snr, and frequency
        """
        mute = self.get_mute()
        self.mute(True)
        frequencies = [162.400, 162.425, 162.450, 162.475, 162.500, 162.525, 162.550]
        rates = []
        for f in frequencies:
            rsf = self.tune(f)
            rates.append((rsf[1], rsf[0], rsf[2]))
        logging.info("Scanned " + str(rates))
        best = max(rates)
        self.tune(best[2])
        self.mute(mute)
        return best


class FutureException(RuntimeError):
    """Something bad went down instead of your future getting fulfilled."""
    pass


class Si4707Exception(Exception):
    """
    Thrown for problems with Si4707 commands
    """
    pass


class Si4707StoppedException(Si4707Exception):
    """
    Thrown to queued commands at radio shutdown.
    """
    pass


class StatusError(Si4707Exception):
    """
    The status received from Si4707 indicates an error in the command it received.  The command that caused
    this exception is suspected of having done something bad.
    """

    def __init__(self, status):
        self.status = status


class Future(object):
    """
    A container for a result that is expected after some time.
    """

    def __init__(self):
        self.__condition = threading.Condition()
        self.__value = None
        self.__exception = None
        self.__complete = False

    def get(self, timeout=None):
        """
        :return: the result of the operation once it is ready, blocking until then
        """
        if not self.__complete:
            with self.__condition:
                while not self.__complete:
                    self.__condition.wait(timeout=timeout)
                    if not self.__complete:
                        raise TimeoutError()

        if self.__exception:
            raise FutureException from self.__exception

        return self.__value

    def result(self, value):
        """
        This result will be returned to the consumer
        """
        with self.__condition:
            self.__value = value
            self.__complete = True
            self.__condition.notify_all()

    def exception(self, exception):
        """
        This exception will be raised from get for the consumer
        """
        with self.__condition:
            self.__exception = exception
            self.__complete = True
            self.__condition.notify()


def _simple_members(c):
    """
    :param c: An object to inspect
    :return: A string containing human-readable class name & key-value pairs for members
    """
    return type(c).__name__ + " [" + ', '.join("%s: %s" % item for item in vars(c).items()) + "]"


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
