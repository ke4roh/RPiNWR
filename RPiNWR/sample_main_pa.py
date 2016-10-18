# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# Main program for running connected to a PA system
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
from .radio_component import Radio_Component
from .radio_squelch import Radio_Squelch
from .sources import TextPull, FolderMonitor
from .cache import MessageCache
from circuits import Debugger
from .alerting import AlertTimer
from .audio import AudioPlayer

location = {
    'lat': 35.77,
    'lon': -78.64,
    'fips6': '037183',
    'warnzone': 'NCZ183',
    'firewxzone': 'NCZ183'
}

box = Radio_Component("--transmitter WXL58") + Radio_Squelch() + TextPull(location) + \
      FolderMonitor(location, "drpozone") + AlertTimer() + MessageCache(location) + Debugger() + AudioPlayer()
# TODO add test facility
# TODO add web server to display status
# TODO add health check & alerting for radio
box.run()
