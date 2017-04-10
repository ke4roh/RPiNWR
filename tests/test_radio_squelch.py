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

import unittest
from RPiNWR.sources.radio.radio_squelch import Radio_Squelch, radio_message_escrow, EscrowAction
from RPiNWR.sources import new_message, net_status
from circuits.core.events import generate_events
from threading import Lock
from RPiNWR.messages.SAME import SAMEMessage


class _RS(Radio_Squelch):
    def __init__(self, clock):
        super().__init__(clock=clock)
        self.events = []

    def fireEvent(self, event, *channels, **kwargs):
        self.events.append((event, channels, kwargs))

    fire = fireEvent


class TestRadioSquelch(unittest.TestCase):
    def assertEventEqual(self, event, e1):
        self.assertEqual(event.name, e1[0].name)
        self.assertEqual(event.args, e1[0].args)

    def test_radio_squelch_good_net(self):
        # Test operation with continuously up network
        t = [0]

        rs = _RS(lambda: t[0])
        events = rs.events
        ge = generate_events(Lock(), 300)
        rs._generate_events(ge)
        self.assertEqual(0, len(events))
        self.assertEqual(5, ge.time_left)
        rs._monitor_net(net_status.ok)
        t[0] += 1
        msg = SAMEMessage('-WXR-TOR-137001+0030-1181503-KRAH/NWS-')
        nme = new_message(msg)
        self.assertFalse(nme.stopped)
        rs.new_message(nme, msg)
        self.assertEqual(1, len(events))
        self.assertTrue(nme.stopped)

        self.assertEventEqual(radio_message_escrow(EscrowAction.escrowed, msg), events[0])
        t[0] += 1
        rs._generate_events(ge)
        self.assertEqual(1, len(events))
        t[0] += 90
        rs._generate_events(ge)
        self.assertEqual(2, len(events))
        self.assertEventEqual(radio_message_escrow(EscrowAction.suppressed, msg), events[1])

    def test_radio_squelch_bad_net(self):
        # Test operation with consistently down network
        t = [0]

        rs = _RS(lambda: t[0])
        events = rs.events
        ge = generate_events(Lock(), 300)
        msg = SAMEMessage('-WXR-TOR-137001+0030-1181503-KRAH/NWS-')
        nme = new_message(msg)
        rs._monitor_net(net_status.down)
        self.assertFalse(nme.stopped)
        rs.new_message(nme, msg)
        self.assertFalse(nme.stopped)  # this event is allowed to continue, nothing stops
        self.assertEqual(0, len(events))  # no changes to events
        rs._generate_events(ge)
        self.assertEqual(0, len(events))  # no changes to events
        t[0] += 90
        rs._generate_events(ge)
        self.assertEqual(0, len(events))  # no changes to events

    def test_radio_squelch_net_fails_in_the_middle(self):
        # Test operation with network that goes down in the middle
        t = [0]

        rs = _RS(lambda: t[0])
        events = rs.events
        ge = generate_events(Lock(), 300)
        msg = SAMEMessage('-WXR-TOR-137001+0030-1181503-KRAH/NWS-')
        nme = new_message(msg)

        rs._monitor_net(net_status.ok)
        rs.new_message(nme, msg)
        self.assertEqual(1, len(events))
        self.assertEventEqual(radio_message_escrow(EscrowAction.escrowed, msg), events[0])
        t[0] += 10
        rs._generate_events(ge)
        self.assertEqual(1, len(events))
        t[0] += 5
        rs._generate_events(ge)
        self.assertEqual(1, len(events))
        t[0] += 5
        # Net goes down
        rs._monitor_net(net_status.down)
        self.assertEqual(2, len(events))  # It fires an event
        self.assertEventEqual(new_message(msg), events[1])  # namely re-fires the escrowed event
        self.assertFalse(events[1][0].stopped)  # which is not stopped
        rs.new_message(events[1][0], events[1][0].args[0])  # in the live system, that triggers this call...
        self.assertFalse(events[1][0].stopped)  # and the event is still not stopped afterward
        self.assertEqual(3, len(events))  # but we have another event
        self.assertEventEqual(radio_message_escrow(EscrowAction.released, msg), events[2])  # escrow released

        rs._generate_events(ge)
        self.assertEqual(3, len(events))  # Nothing more happened

    def test_radio_squelch_good_net_non_tor(self):
        # Test operation with network that goes down in the middle
        t = [0]

        rs = _RS(lambda: t[0])
        events = rs.events
        ge = generate_events(Lock(), 300)
        msg = SAMEMessage('-WXR-SVR-137001+0030-1181503-KRAH/NWS-')
        nme = new_message(msg)
        rs.new_message(nme,msg)
        self.assertFalse(nme.stopped)