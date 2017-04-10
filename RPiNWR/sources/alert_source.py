# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# The core component (and events) pertaining to alert sources
#
# Copyright © 2017 James E. Scarborough
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

from circuits import BaseComponent, Event

class AlertSource(BaseComponent):
    def __init__(self, location):
        self.location = location
        super().__init__()

    def get_delay_sec(self):
        raise NotImplementedError()

    def has_polygons(self):
        raise NotImplementedError()

    def is_operational(self):
        raise NotImplementedError()

class new_message(Event):
    """This fires when a new message comes in."""

