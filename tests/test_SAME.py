# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
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
from RPiNWR.messages.SAME import *
import RPiNWR.messages.SAME as SAME
import logging
import json
from calendar import timegm
import os


class TestSAME(unittest.TestCase):
    @staticmethod
    def get_time(msg, year=2011):
        """

        :param msg: a SAME message
        :param year: the year of the message (2011 by default)
        :return: time in seconds since the epoch
        """
        plus = msg.find('+')
        return timegm(time.strptime("2011" + msg[plus + 6:plus + 13] + 'UTC', '%Y%j%H%M%Z'))

    @staticmethod
    def add_time(msg_tuple, msg_time=None, order=0):
        """
        :param msg_tuple: a tuple of message and confidence (confidence is just passed through), or 3 of these
        :param start: If provided, the start time of the message, otherwise it will be constructed from the message
        :param order: The number of headers that preceded this one after the given start time
        :return:
        """
        if len(msg_tuple) == 3:
            l = []
            for i in range(0, 3):
                l.append(TestSAME.add_time(msg_tuple[i], msg_time, i))
            return l

        if msg_time is None:
            msg_time = TestSAME.get_time(msg_tuple[0])
        message_duration = 1 + len(msg_tuple[0]) / 520.83 * 8
        return msg_tuple[0], msg_tuple[1], msg_time + message_duration * order

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
        self.fail(str(mess))

    @staticmethod
    def make_noisy_messages(noise):
        # mimic spotty reception this way.
        clear_message = '-WXR-RWT-020103-020209-020091-020121-029047-029165-029095-029037+0030-3031700-KEAX/NWS-'
        msg_time = TestSAME.get_time(clear_message)

        random.seed(0)  # ensure a repeatable test
        return clear_message, TestSAME.add_time([
            TestSAME.add_noise(clear_message, noise),
            TestSAME.add_noise(clear_message, noise),
            TestSAME.add_noise(clear_message, noise)
        ], msg_time)

    def testAverageMessage(self):
        clear_message, messages = self.make_noisy_messages(.03)
        (msg, confidence) = average_message(messages, "KID77")
        self.assertEqual(clear_message, msg)
        self.assertEqual(3, min(confidence))
        self.assertEqual(9, max(confidence))

    def testAverageMessageOfJunkHasLowConfidence(self):
        clear_message, messages = self.make_noisy_messages(.05)
        (msg, confidence) = average_message(messages, "KID77")
        for i in range(0, len(clear_message)):
            if clear_message[i] != msg[i]:
                self.assertTrue(confidence[i] < 3, "%s != %s (%d)" % (clear_message[i], msg[i], confidence[i]))

    def testDifferentLengths(self):
        # Sometimes messages come in partial, like in this bad reception example
        messages = TestSAME.add_time([('-E\x00S-RWT', [2, 1, 2, 3, 2, 2, 1, 2]),
                                      ('-E\x00S-RWT-0\x007183+', [3, 3, 3, 3, 3, 3, 3, 3, 2, 2, 3, 3, 2, 3, 2, 3]),
                                      ('-E\x00S-RWT-0\x007183+', [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 2, 3])],
                                     time.time())
        (msg, confidence) = average_message(messages, "WXL58")
        # The next assertion is not prescriptive as to how to handle the null FIPS character.  It might rightly be
        # substituted because every value from the possibilities is 3, and there is no confidence lost by substitution.
        self.assertEquals('-EAS-RWT-0⨀7183+', msg)  # ^^ read that
        self.assertEquals(8, confidence[2])  # It's been fixed and verified by the adjacent 2 characters
        self.assertTrue(confidence[10] < 3)

    def test_reconcile_word(self):
        w, c, d = SAME._reconcile_word("dug", "939", 0, ["dog", "cat", "fly", "pug"])
        self.assertEqual("dog", w)
        self.assertEqual([9, 7, 9], c)

        w, c, d = SAME._reconcile_word("030151", "992997", 0,
                                       '037037-037063-037069-037077-037085-037101-037105-037125-037135-037145-037151-037181-037183-037185'.split(
                                           '-'))
        self.assertEqual("037151", w)
        self.assertEqual(list([int(x) for x in "998997"]), c)

        w, c, d = SAME._reconcile_word("037001-030151", "9999999992997", 7,
                                       '037037-037063-037069-037077-037085-037101-037105-037125-037135-037145-037151-037181-037183-037185'.split(
                                           '-'))
        self.assertEqual("037151", w[7:])
        self.assertEqual(list([int(x) for x in "998997"]), c[7:])

    def test_dirty_messages(self):
        logging.basicConfig(level=logging.INFO)
        messages = self.load_dirty_messages()
        for msg in messages:
            msg["calculated"] = average_message(msg["headers"], msg["transmitter"])

            # Make the headers readable in output
            for i in range(0, len(msg["headers"])):
                if type(msg["headers"][i][1]) is list:
                    msg["headers"][i][1] = "".join([str(x) for x in msg["headers"][i][1]])
                msg["headers"][i][0] = unicodify(msg["headers"][i][0])

            if "clean" in msg:
                clean_message = msg["clean"]
                c_msg = msg["calculated"][0]
                confidence = msg["calculated"][1]

                # Now, because this message was so dirty, let's assert a certain level of accuracy, which can be tuned upward
                # as the average_message algorithm is improved.
                changed_bits = self.count_changed_bits(clean_message, c_msg)
                changed_bytes = self.count_changed_bytes(clean_message, c_msg)
                wrong_confidence = self.count_wrong_confidence(clean_message, c_msg, confidence)
                right_confidence = self.count_right_confidence(clean_message, c_msg, confidence)

                report = "\n".join([self.get_errstr(c_msg, clean_message),
                                    c_msg,
                                    "".join([str(x) for x in confidence]),
                                    clean_message,
                                    "wrong_bits=%d wrong_bytes=%d wrong_confidence=%d right_confidence=%d " %
                                    (changed_bits, changed_bytes, wrong_confidence, right_confidence)])

                self.assertTrue("".join([str(x) for x in confidence]).isnumeric(), "\n" + report)
                for f, v in [("changed_bits", changed_bits), ("changed_bytes", changed_bytes),
                             ("wrong_confidence", wrong_confidence), ("right_confidence", right_confidence)]:
                    if f in msg:
                        if f.startswith("right"):
                            self.assertTrue(v >= msg[f], "%s=%d, worse than %d\n%s" % (f, v, msg[f], report))
                        else:
                            self.assertTrue(v <= msg[f], "%s=%d, worse than %d\n%s" % (f, v, msg[f], report))
                    else:
                        msg[f] = v

            msg["calculated"] = (msg["calculated"][0], "".join([str(x) for x in msg["calculated"][1]]))

        # added encoding for Windows machines
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "dirty_messages_1.json"), "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=4, sort_keys=True, ensure_ascii=False)

    def load_dirty_messages(self):
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "dirty_messages.json"), "r", encoding="utf-8") as f:
            messages = json.load(f)
        return messages

    def __testRealRWT(self):
        logging.basicConfig(level=logging.INFO)
        # I figured the clean version out by hand based on received
        clean_message = '-WXR-RWT-037001-037037-037063-037069-037077-037085-037101-037105-037125-037135-037145-037151-037181-037183-037185+0600-1181503-KRAH/NWS-'
        msg_time = TestSAME.get_time(clean_message, 2016)

        # And here's an RWT with bad reception
        messages = TestSAME.add_time([
            (
                '-W⨀R-RWT-0⨀7001-03⨀037-037⨀63-0370⨀9-03707⨀-037085⨀037101-⨀37105-0⨀7125-03⨀135-037⨀45-0371⨀1-03718⨀-037183⨀037185+⨀600-118⨀503-KRA⨀/NWS-⨀⨀⨀ỶỂ␝Iỹ',
                '233232233333333233333323333333333333333333333233333333333333333333333333333333333333233333233333333233333323333323333333333233333233333333300000'
            ),
            (
                '-W⨀R-RWT-0⨀7001-03⨀037-037⨀63-0370⨀9-03707⨀-037085⨀037101-⨀37105-0⨀7125-03⨀135-037⨀45-0371⨀1-03718⨀-037183⨀037185+⨀600-118⨀503-KRA⨀/NWS-⨀⨀⨀Ẵ␂␑IX',
                '333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333300000'
            ),
            (
                '-W⨀R-RWT-0⨀7001-03⨀037-037⨀63-0370⨀9-03707⨀-037085⨀037101-⨀37105-0⨀7125-03⨀135-037⨀45-0371⨀1-03718⨀-037183⨀037185+⨀600-118⨀503-KRA⨀/NWS-⨀⨀⨀0⨀␑IP',
                '333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333333300000'
            )], msg_time)

        (msg, confidence) = average_message(messages)

        # Now, because this message was so dirty, let's assert a certain level of accuracy, which can be tuned upward
        # as the average_message algorithm is improved.
        changed_bits = self.count_changed_bits(clean_message, msg)
        changed_bytes = self.count_changed_bytes(clean_message, msg)
        wrong_confidence = self.count_wrong_confidence(clean_message, msg, confidence)
        right_confidence = self.count_right_confidence(clean_message, msg, confidence)
        logging.info("wrong_bits=%d wrong_bytes=%d wrong_confidence=%d right_confidence=%d " %
                     (changed_bits, changed_bytes, wrong_confidence, right_confidence))

        logging.info(self.get_errstr(msg, clean_message))
        logging.info(msg)
        logging.info("".join([str(x) for x in confidence]))
        logging.info(clean_message)
        self.assertTrue(changed_bits < 20, changed_bits)
        self.assertTrue(changed_bytes < 12, changed_bytes)
        self.assertTrue(wrong_confidence < 19, wrong_confidence)
        self.assertTrue(right_confidence > 1075,
                        "%d -- %.2f per byte" % (right_confidence, right_confidence / len(msg)))

    def _test_probabilities(self):
        """
        This is an information-gathering routine.  Its objective is to examine dirty messages and
        print out a matrix of how many times each combo of bit swaps happened at each confidence level.
        It's most useful with a huge sample of data (hundreds of messages).
        """
        messages = self.load_dirty_messages()

        # This will become a 2d array - score v. bits wrong in a byte (0-8)
        cbits_by_score = []
        for i in range(0, 4):
            cbits_by_score.append([0] * 9)

        # Keep count of how many nulls appear in each certainty
        sure_null = [0] * 4

        for msg in messages:
            if "clean" in msg:
                clean = msg["clean"]
                for header, scores, when in msg["headers"]:
                    for i in range(0, min(len(clean), len(header))):
                        if header[i] == "\u0000":
                            try:
                                sure_null[scores[i]] += 1
                            except TypeError:
                                sure_null[int(scores[i])] += 1
                        else:
                            cbits = self.count_changed_bits((clean[i]), (header[i]))
                            try:
                                cbits_by_score[scores[i]][cbits] += 1
                            except TypeError:
                                cbits_by_score[int(scores[i])][cbits] += 1

        # Normalize
        for i in range(0, 4):
            # Count exactly 1 for all the things that never happened in this trial to account for their possibility
            all = sum(cbits_by_score[i]) + len(list(filter(lambda x: x == 0, cbits_by_score[i])))
            cbits_by_score[i] = list([max(x, 1) / all for x in cbits_by_score[i]])
        logging.error(str(sure_null))
        self.fail("\n" + "\n".join([str(x) for x in cbits_by_score]))

    def count_changed_bits(self, a, b):
        bits = abs(len(a) - len(b)) * 8
        for i in range(0, min(len(a), len(b))):
            bits += bin(ord(a[i]) ^ ord(b[i])).count('1')

        return bits

    def count_right_confidence(self, clean_message, test_message, confidence):
        rc = 0
        for i in range(0, len(confidence)):
            if (not len(clean_message) < i) and clean_message[i] == test_message[i]:
                rc += confidence[i]
        return rc

    def count_wrong_confidence(self, clean_message, test_message, confidence):
        wc = 0
        for i in range(0, len(confidence)):
            if len(clean_message) < i or clean_message[i] != test_message[i]:
                wc += confidence[i]
        return wc

    def count_changed_bytes(self, a, b):
        bytes = abs(len(a) - len(b))
        for i in range(0, min(len(a), len(b))):
            bytes += (a[i] != b[i]) & 1
        return bytes

    def get_errstr(self, a, b):
        errstr = ''
        for i in range(0, min(len(a), len(b))):
            if a[i] == b[i]:
                errstr += ' '
            else:
                errstr += "_"
        return errstr

    def test_county_parse(self):
        c = SAMEMessage(
            '-WXR-RWT-020103-020209-020091-020121-029047-029165-029095-029037+0030-3031700-KEAX/NWS-').get_counties()
        self.assertEqual(['020103', '020209', '020091', '020121', '029047', '029165', '029095', '029037'], c)

    def test_parse_letters_in_fips(self):
        msg = "-PEP-TXP-WXL58!+0015-1180023-KRAH/NWS-"
        mm = average_message(TestSAME.add_time(
            [(msg, '2' * len(msg))] * 3
        ), "WXL58")

        self.assertEqual(msg, mm[0])

    def test_fips_p_code(self):
        # WXL29 serves 2 large counties
        # ('032013', '032027')
        msg = "-WXR-TOR-932013-832013+0015-1180023-KLKN/NWS-"
        mm = average_message(TestSAME.add_time(
            [(msg, '2' * len(msg))] * 3
        ), "WXL29")

        self.assertEqual(msg, mm[0])

    def test_p_code_with_nulls(self):
        # These counties differ in 2 digits, so several mutations should resolve correctly
        clean_msg = "-WXR-TOR-932013-832013+0015-1180023-KLKN/NWS-"
        msg = list(clean_msg)
        msg[12] = '\x00'
        msg[19] = '\x00'
        msg = "".join(msg)
        mm = average_message(TestSAME.add_time(
            [(msg, '2' * len(msg))] * 3
        ), "WXL29")

        self.assertEqual(clean_msg, mm[0])

    def test_applies_to_fips(self):
        msg = '-WXR-RWT-037001-037037-037063-037069-037077-037085-037101-037105-037125-037135-037145-037151-037181-037183-037185+0600-1181503-KRAH/NWS-'

        sm = SAMEMessage(msg)
        self.assertTrue(sm.applies_to_fips("037001"))
        self.assertTrue(sm.applies_to_fips("037037"))
        self.assertFalse(sm.applies_to_fips("047001"))
        self.assertTrue(sm.applies_to_fips("137001"))
        self.assertTrue(sm.applies_to_fips("037185"))

        msg = '-WXR-TOR-137001+0030-1181503-KRAH/NWS-'
        sm = SAMEMessage(msg)

        self.assertTrue(sm.applies_to_fips("137001"))
        self.assertTrue(sm.applies_to_fips("037001"))
        self.assertFalse(sm.applies_to_fips("937001"))

    def test_message_times(self):
        # This test checks that the time from the message (and duration) is correctly converted to seconds since
        # the epoch (1970-01-01 00:00:00 UTC).  To do this, we need an absolute time for the message to compare
        # against a known-good time since the epoch, so this makes a constructor with a header saying the message
        # came in at a specific time (shortly after it says it was created).  The transmitter is not necessary
        # because we know the whole code is valid.
        msg = "-WXR-SVR-037085-037101+0100-1250218-KRAH/NWS-"
        m = SAMEMessage(transmitter=None, headers=[(msg, '9' * len(msg), 1462328285)])
        self.assertEqual(1462328280.0, m.get_start_time_sec())
        self.assertEqual(60 * 60, m.get_duration_sec())
        self.assertEqual(1462328280 + 60 * 60, m.get_end_time_sec())

    def test_get_broadcaster(self):
        self.assertEqual("KRAH/NWS", SAMEMessage("-WXR-SVR-037085-037101+0100-1250218-KRAH/NWS-").get_broadcaster())

    def test_sort_messages(self):
        self.assertEqual(0, default_SAME_sort(SAMEMessage("-WXR-SVR-037085-037101+0100-1250218-KRAH/NWS-"),
                                              SAMEMessage("-WXR-SVR-037085-037101+0100-1250218-KRAH/NWS-")))
        self.assertTrue(default_SAME_sort(SAMEMessage("-WXR-SVR-037085-037101+0100-1250218-KRAH/NWS-"),
                                          SAMEMessage("-WXR-SVA-037085-037101+0100-1250218-KRAH/NWS-")) < 0)
        self.assertTrue(default_SAME_sort(SAMEMessage("-WXR-SVR-037085-037101+0100-1250219-KRAH/NWS-"),
                                          SAMEMessage("-WXR-SVR-037085-037101+0100-1250218-KRAH/NWS-")) < 0)
        self.assertTrue(default_SAME_sort(SAMEMessage("-WXR-FRW-037085-037101+0100-1250219-KRAH/NWS-"),
                                          SAMEMessage("-WXR-HMW-037085-037101+0100-1250218-KRAH/NWS-")) < 0)
        self.assertTrue(default_SAME_sort(SAMEMessage("-CIV-FRW-037085-037101+0100-1250219-KRAH/NWS-"),
                                          SAMEMessage("-CIV-HMW-037085-037101+0100-1250218-KRAH/NWS-")) < 0)
        self.assertTrue(default_SAME_sort(SAMEMessage("-CIV-FRW-037085-037101+0100-1250219-KRAH/NWS-"),
                                          SAMEMessage("-CIV-FRW-037085-037101+0130-1250218-KRAH/NWS-")) < 0)

    def test_reconcile_character(self):
        # D = 0100 0100
        # L = 0100 1100
        # M = 0100 1101
        # and reconciling these 3 with equal weights should yeild L
        # Easier to write with MSB first, then reverse
        bitstrue = [0, 3, 0, 0, 2, 3, 0, 1]
        bitsfalse = [3, 0, 3, 3, 1, 0, 3, 2]
        bitstrue.reverse()
        bitsfalse.reverse()
        self.assertEqual((2, 'L'), SAME._reconcile_character(bitstrue, bitsfalse,
                                                             'ABCDEFGHIJKLMNOPQRSTUVWXYZ'))


    def test_mutate_string(self):
        # setup
        test_string = 'string'
        expected_result = '$tring'

        # test
        test_mutate_string = SAME.mutate_string(test_string, 0, '$')

        # assert
        self.assertEqual(test_mutate_string, expected_result)
