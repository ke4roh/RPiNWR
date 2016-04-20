# -*- coding: utf-8 -*-
__author__ = 'jscarbor'
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



from math import ceil
import random
import unittest
from RPiNWR.SAME import *


class TestSAME(unittest.TestCase):
    @staticmethod
    def add_noise(msg, rate, sd=.02):
        """

        :param msg: A message to mess up
        :param rate: 0-1, a number indicating how much of the message to perturb.  Small is good.  1 would swap
            every bit and 0 would swap none, so .04 with sd .02 is quite a lot of error for a digital system.
        :param sd: standard deviation of error rate
        :return: A tuple containing a bytearray of the noisy message and the confidence hints for its noise
        """
        if rate < 0 or rate > 1:
            raise ValueError("0<=rate<=1")

        def confidence0(r):
            return int(min(3, max(0, ceil(3 - 50 * r))))

        new_message = ''
        confidence = []
        for c in msg:
            byte_noise_rate = random.gauss(rate, sd)
            bits_to_flip_n = int(8 * byte_noise_rate + .5)
            bits_l = list('1' * bits_to_flip_n + '0' * (8 - bits_to_flip_n))
            random.shuffle(bits_l)
            noise_mask = int("".join(bits_l), 2)
            new_message += chr(ord(c) ^ noise_mask)
            confidence.append(confidence0(byte_noise_rate))

        return new_message, confidence

    def _test_add_noise(self):
        random.seed(0)
        clear_message = 'ZCZC-WXR-TOR-039173-039051-139069+0030-1591829-KCLE/NWS-'
        mess, conf = self.add_noise(clear_message, 0.06, .03)
        changed = [[0, 0], [0, 0], [0, 0], [0, 0]]
        for i in range(0, len(clear_message)):
            changed[conf[i]][0] += 1
            changed[conf[i]][1] += (clear_message[i] == mess[i]) & 1
        for i in range(0, 4):
            print("c(%d)=%.0f%%  n=%d\n" % (i, changed[i][1] * 100.0 / changed[i][0], conf.count(i)))
        self.fail(str(msg))

    @staticmethod
    def make_noisy_messages(noise):
        # mimic spotty reception this way.
        clear_message = '-WXR-RWT-020103-020209-020091-020121-029047-029165-029095-029037+0030-3031700-KEAX/NWS'

        random.seed(0)  # ensure a repeatable test
        return clear_message, [
            (TestSAME.add_noise(clear_message, noise)),
            (TestSAME.add_noise(clear_message, noise)),
            (TestSAME.add_noise(clear_message, noise)),
        ]

    def testAverageMessage(self):
        clear_message, messages = self.make_noisy_messages(.03)
        (msg, confidence) = average_message(messages)
        self.assertEqual(clear_message, msg)
        self.assertEqual(1, min(confidence))
        self.assertEqual(8, max(confidence))

    def testAverageMessageOfJunkHasLowConfidence(self):
        clear_message, messages = self.make_noisy_messages(.05)
        (msg, confidence) = average_message(messages)
        for i in range(0, len(clear_message)):
            if clear_message[i] != msg[i]:
                self.assertTrue(confidence[i] < 3, "%s != %s (%d)" % (clear_message[i], msg[i], confidence[i]))
