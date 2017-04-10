# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# Suppress radio tornado warning messages when the net is fine
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

from circuits import BaseComponent, handler, Event
from ...sources.net_events import net_status
from ...messages.CommonMessage import new_message
from time import time
from threading import Lock
from enum import Enum

class Radio_Squelch(BaseComponent):
    """
    Suppress TOR messages from the radio if the net is working.
    """

    def __init__(self, clock=time):
        super().__init__()
        self.__pending = []
        self.__pending_lock = Lock()
        self.max_time = 90
        self.net_ok = False
        self.last_net_ok_time = 0
        self.__clock = clock

    @handler("new_message", priority=1000)
    def new_message(self, event, message):
        if message.get_event_type() == "TOR":
            pending = None
            # Look through pending messages and see if this is one of them, or if it is novel
            for t, m in self.__pending:
                if m == message:
                    pending = (t, m)
                    break
            if pending:  # it wasn't novel
                # Since it was already known, it must have been re-fired, so allow it to continue
                with self.__pending_lock:
                    self.__pending.remove(pending)
                self.fire(radio_message_escrow(EscrowAction.released, message))
            elif self.net_ok:
                # this is a new message and the net is working now, so store it for a while to ensure net stays up
                with self.__pending_lock:
                    self.__pending.append((self.__clock(), message))
                event.stop()
                self.fire(radio_message_escrow(EscrowAction.escrowed, message))

    @handler("generate_events")
    def _generate_events(self, event):
        event.reduce_time_left(5)
        self._update_pending()

    def _update_pending(self):
        to_fire = []
        to_remove = []
        with self.__pending_lock:
            for t, m in self.__pending:
                if self.net_ok:
                    if self.__clock() >= t + self.max_time:
                        # net is ok at the timeout, so assume it came in via net if necessary
                        to_remove.append((t, m))  # defer modification
                        to_fire.append(radio_message_escrow(EscrowAction.suppressed, m))
                else:
                    # net goes down while we're waiting - could be weather-related
                    to_fire.append(new_message(m))
            for r in to_remove:
                self.__pending.remove(r)
        for e in to_fire:
            self.fire(e)

    @handler("net_status")
    def _monitor_net(self, status):
        if status == net_status.ok:
            self.net_ok = True
            self.last_net_ok_time = self.__clock()
        else:
            self.net_ok = False
            self._update_pending()


class radio_message_escrow(Event):
    pass


class EscrowAction(Enum):
    escrowed = "A radio message has been waylaid pending net validation."
    released = "A radio message has been re-fired from escrow (probably because net failed)."
    suppressed = "A radio message is discarded because no net problem was observed for the entire escrow time."
