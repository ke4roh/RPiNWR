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
from circuits import Component
import pygame
import os.path


class AudioPlayer(Component):
    def __init__(self, audio_path="RPiNWR/audio/"):
        self.channel = None
        self.audio_path = audio_path

    def __play_sound(self, sound_file):
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        if self.channel is None:
            self.channel = pygame.mixer.find_channel()
        self.channel.queue(pygame.mixer.Sound(sound_file))

    def begin_alert(self):
        self.__play_sound(os.path.join(self.audio_path, "begin_alert.ogg"))

    def continue_alert(self):
        self.__play_sound(os.path.join(self.audio_path, "continue_alert.ogg"))

    def all_clear(self):
        self.__play_sound(os.path.join(self.audio_path, "all_clear.ogg"))
