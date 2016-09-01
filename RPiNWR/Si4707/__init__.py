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

# This package is an implementation of the software-level concerns for operating the Si4707 chip.
# It turns on the radio, receives messages, alert tones, and so forth, but it does not do any
# further processing of the data to, for example, decide what to do with a message.
#
# Ref http://www.silabs.com/Support%20Documents/TechnicalDocs/AN332.pdf
# http://web.archive.org/web/20160324082647/http://www.silabs.com/Support%20Documents/TechnicalDocs/AN332.pdf

import queue
import heapq
import threading
from RPiNWR.Si4707.commands import *
from RPiNWR.Si4707.data import *
from RPiNWR.Si4707.events import *
from RPiNWR.Si4707.exceptions import *
from RPiNWR.nwr_data import *


class Si4707(object):
    def __init__(self, context):
        self.__event_queue = queue.Queue(maxsize=50)
        self.__command_queue = queue.PriorityQueue(maxsize=50)
        self.__command_serial_number = 0
        self.__command_serial_number_lock = threading.Lock()
        self.__event_listeners = []
        self.__delayed_events = []
        self.__delayed_event_lock = threading.Lock()
        self.tune_after = float("inf")
        self.context = context
        self.radio_power = False  # Off to begin with
        self.status = None  # Gonna fix this in __enter__
        self.stop = False  # True to stop threads
        self.shutdown_pending = False  # True once shutdown has commenced
        self.tone_start = None
        self._logger = logging.getLogger(type(self).__name__)
        self.same_message = None
        self.last_EOM = 0
        self.transmitter = None

    def __enter__(self):
        try:
            retries = 2
            while retries >= 0:
                retries -= 1
                self.context.reset_radio()
                try:
                    self.wait_for_clear_to_send(timeout=5)
                except IOError:
                    if retries == 0:
                        raise

            for t in [threading.Thread(target=self.__command_loop),
                      threading.Thread(target=self.__event_loop)]:
                t.setDaemon(False)
                t.start()
            self._logger.info("Si4707 ready")
        except Exception:
            self._logger.exception("Startup failed")
            raise
        return self

    def _dispatch_any_message(self, finished=False):
        """
        If there is a same_message pending, dispatch it if it is done.
        :param finished: True if the message is asserted to be complete, False if it's checking against the timeout
        :return: None
        """
        if self.same_message and self.same_message.fully_received(make_it_so=finished):
            # checking message.fully_received() will dispatch it if it's finished
            pass

    def __command_loop(self):
        while not self.stop:
            command = None
            try:
                # Check for interrupts
                status = self.check_interrupts()
                if status.is_same_interrupt():
                    self.do_command(SameInterruptCheck(intack=True))
                if status.is_audio_signal_quality_interrupt():
                    self.do_command(AlertToneCheck(True))
                if status.is_received_signal_quality_interrupt():
                    self.do_command(ReceivedSignalQualityCheck(True))

                # Check for a SAME message to dispatch
                self._dispatch_any_message()

                # Run any pending command
                command = self.__command_queue.get(block=True, timeout=0.05)[1]
                command.do_command(self)
                self._logger.debug("Executed " + str(command))
                if command.exception:
                    # Logged where it's caught in command
                    self._fire_event(CommandExceptionEvent(command.exception, passed_back=True))
                else:
                    self._fire_event(command)
            except queue.Empty:
                try:
                    # Reset the command serial number if it gets big
                    if self.__command_serial_number > 50000:
                        with self.__command_serial_number_lock:
                            if self.__command_queue.empty():
                                self.__command_serial_number = 0
                except Exception:
                    self._logger.exception("housekeeping failed")
            except Exception as e:
                self._logger.exception("queue processing failed")
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
                try:
                    listener(event)
                except Exception as e:
                    self._logger.exception("Event processing")

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
                self._logger.debug("Firing for t=%f (%d ms late)" % (ev[0], int((time.time() - ev[0]) * 1000)))
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
        self.__event_queue = None

    def _delay_event(self, event, when):
        """
        Fire an event after a time
        :param event: the event
        :param when: the time.time() at which to fire the event
        """
        with self.__delayed_event_lock:
            heapq.heappush(self.__delayed_events, (when, event))
        self._logger.debug("Scheduled " + str(event) + " for " + str(when) + " which is " + str(
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
            try:
                self.status = Status(self.context.read_bytes(1))
                if self.status.is_clear_to_send():
                    return self.status
                else:
                    time.sleep(.002)
            except OSError as e:
                if e.errno == 5:  # I/O error - GPIO is busted
                    self.stop = 1
                    self._logger.fatal("I/O error")
                    self._logger.exception("I/O error")
                raise
        raise NotClearToSend()

    def check_interrupts(self):
        """
        Ask the chip if there are interrupts.  Update status accordingly.

        :return: the result of Status.is_interrupt() which is true if there are any, and bitwise indicates
        the actual interrupts at hand, but subsequent examination of self.status is preferable for identifying
        which interrupts.
        """
        self.wait_for_clear_to_send(timeout=5)
        self.context.write_bytes([0x14])  # GET_INT_STATUS Tell Si4707 to populate interrupt bits
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
        try:
            self.__event_queue.put_nowait(event)
        except AttributeError:
            raise Si4707StoppedException()

    def power_on(self, configuration=None):
        config = DEFAULT_CONFIG
        if configuration is not None:
            config = dict(DEFAULT_CONFIG)
            config.update(configuration)

        if config["power_on"].get("patch"):
            self.do_command(PatchCommand(**config["power_on"]))
        else:
            self.do_command(PowerUp())

        for (prop, value) in config["properties"].items():
            self.set_property(prop, value)

        if config.get("transmitter", None):
            self.tune(config.get("transmitter"))
        elif config.get("frequency"):
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
        self._logger.debug("Shutting down Si4707")
        if not self.shutdown_pending:
            self.shutdown_pending = True
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
            self._logger.debug("Si4707 stopped")

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.shutdown(True)
        except Exception as e:
            self._logger.exception("cleaning up")
        finally:
            self.shutdown_pending = True
            self.stop = True

    def do_command(self, command):
        """
        Put a command on the queue for execution.  Call .get() on the result to get the return value, any
        exceptions, and to block until the command's completion.
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

    def queue_callback(self, func, args=None, kw_args=None):
        """
        Call the named function from the command queue. Block until it's done,
        return its result.

        :param func:
        :param args:
        :param kw_args:
        :return: Whatever the function returned
        """
        return self.do_command(Callback(func, args, kw_args)).get()

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

    def tune(self, transmitter):
        """
        Change the channel
        :param frequency: Transmitter call letters preferably, or MHz.   The call letters are used
           to validate SAME messages received, so it is helpful to have them.
        :return: a tuple of RSSI (dBµV), SNR (dB), and frequency
        """
        try:
            frequency = get_frequency(transmitter)
            self.transmitter = transmitter
        except KeyError:
            frequency = transmitter + 0  # Maybe it's a number?
            self.transmitter = None
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
        self._logger.info("Scanned " + str(rates))
        best = max(rates)
        self.tune(best[2])
        self.mute(mute)
        return best

    def getAGC(self):
        self.do_command(GetAGCStatus()).get()

    def setAGC(self, enabled):
        """
        Set automatic gain control according to the parameter.  AGC should only be used in
        situations where the input RSSI is too high.
        :param enabled: True to use AGC, False otherwise
        """
        self.do_command(SetAGCStatus(enabled)).get()


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


class Context(object):
    """
    A context gives instructions on how to reset the radio and send and receive bytes.
    It is also responsible for cleaning itself up as necessary.
    """

    def __init__(self):
        if type(self) is Context:
            raise NotImplemented()
        self._logger = logging.getLogger(type(self).__name__)

    def reset_radio(self):
        """
        At a minimum, this will happen first.  It may also happen later on.  If it is called a second time,
        it needs to be able to start over by doing whatever shutdown might be implied, then the startup again.
        """
        raise NotImplemented()

    def write_bytes(self, data):
        """
        Send bytes to the radio.
        :param data: an array of numbers to be interpreted as bytes, or bytes()
        """
        raise NotImplemented()

    def read_bytes(self, num_bytes):
        """
        Return bytes from the radio
        :param num_bytes: How many do you want? (Max ~32)
        :return: bytes()
        """
        raise NotImplemented()
