# -*- coding: utf-8 -*-
__author__ = 'jscarbor'
# Exceptions that can crop up dealing with the radio
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
#


class FutureException(RuntimeError):
    """Something bad went down instead of your future getting fulfilled.  See the nested exception. """
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
    The status received from Si4707 indicates an error in the command it received.  The command that preceded
    this exception is suspected of having done something bad.
    """

    def __init__(self, status):
        self.status = status