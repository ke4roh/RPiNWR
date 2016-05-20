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
import RPiNWR.SAME as SAME
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
                msg["headers"][i][0] = SAME._unicodify(msg["headers"][i][0])

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

        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "dirty_messages_1.json"), "w") as f:
            json.dump(messages, f, indent=4, sort_keys=True, ensure_ascii=False)

    def load_dirty_messages(self):
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "dirty_messages.json"), "r") as f:
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

    def test_buffer_against_storm_system(self):
        # Test to see that the correct events are reported in priority order as a storm progresses
        # This test is a little long in this file, but it's somewhat readable.
        alerts = [SAMEMessage(x) for x in [
            "-WXR-SVR-037183+0045-1232003-KRAH/NWS-",
            "-WXR-SVR-037151+0030-1232003-KRAH/NWS-",
            "-WXR-SVR-037037+0045-1232023-KRAH/NWS-",
            "-WXR-SVR-037001-037151+0100-1232028-KRAH/NWS-",
            "-WXR-SVR-037069-037077-037183+0045-1232045-KRAH/NWS-",
            "-WXR-SVR-037001+0045-1232110-KRAH/NWS-",
            "-WXR-SVR-037069-037181-037185+0045-1232116-KRAH/NWS-",
            "-WXR-FFW-037125+0300-1232209-KRAH/NWS-",
            "-WXR-SVA-037001-037037-037063-037069-037077-037085-037101-037105-037125-037135-037145-037151-037181-037183-037185+0600-1241854-KRAH/NWS-",
            "-WXR-SVR-037001-037037-037151+0045-1242011-KRAH/NWS-",
            "-WXR-SVR-037001-037037-037135+0100-1242044-KRAH/NWS-",
            "-WXR-SVR-037037-037063-037135-037183+0045-1242120-KRAH/NWS-",
            "-WXR-SVR-037183+0100-1242156-KRAH/NWS-",
            "-WXR-TOR-037183+0015-1242204-KRAH/NWS-",
            "-WXR-SVR-037101-037183+0100-1242235-KRAH/NWS-",
            "-WXR-SVR-037151+0100-1242339-KRAH/NWS-",
            "-WXR-SVR-037101+0100-1250011-KRAH/NWS-",
            "-WXR-SVR-037125-037151+0100-1250029-KRAH/NWS-",
            "-WXR-SVR-037085-037105-037183+0100-1250153-KRAH/NWS-",
            "-WXR-SVR-037085-037101+0100-1250218-KRAH/NWS-"
        ]]

        expected = """123 20:03  SVR --- SVR
123 20:08  SVR --- SVR
123 20:13  SVR --- SVR
123 20:18  SVR --- SVR
123 20:23  SVR --- SVR,SVR
123 20:28  SVR --- SVR,SVR,SVR
123 20:33  SVR --- SVR,SVR,SVR
123 20:38  SVR --- SVR,SVR
123 20:43  SVR --- SVR,SVR
123 20:48  SVR,SVR --- SVR,SVR
123 20:53  SVR --- SVR,SVR
123 20:58  SVR --- SVR,SVR
123 21:03  SVR --- SVR,SVR
123 21:08  SVR --- SVR,SVR
123 21:13  SVR --- SVR,SVR
123 21:18  SVR --- SVR,SVR,SVR
123 21:23  SVR --- SVR,SVR,SVR
123 21:28  SVR --- SVR,SVR,SVR
123 21:33   --- SVR,SVR
123 21:38   --- SVR,SVR
123 21:43   --- SVR,SVR
123 21:48   --- SVR,SVR
123 21:53   --- SVR,SVR
123 21:58   --- SVR
123 22:03   ---
123 22:08   ---
123 22:13   --- FFW
123 22:18   --- FFW
123 22:23   --- FFW
123 22:28   --- FFW
123 22:33   --- FFW
123 22:38   --- FFW
123 22:43   --- FFW
123 22:48   --- FFW
123 22:53   --- FFW
123 22:58   --- FFW
123 23:03   --- FFW
123 23:08   --- FFW
123 23:13   --- FFW
123 23:18   --- FFW
123 23:23   --- FFW
123 23:28   --- FFW
123 23:33   --- FFW
123 23:38   --- FFW
123 23:43   --- FFW
123 23:48   --- FFW
123 23:53   --- FFW
123 23:58   --- FFW
124 00:03   --- FFW
124 00:08   --- FFW
124 00:13   --- FFW
124 00:18   --- FFW
124 00:23   --- FFW
124 00:28   --- FFW
124 00:33   --- FFW
124 00:38   --- FFW
124 00:43   --- FFW
124 00:48   --- FFW
124 00:53   --- FFW
124 00:58   --- FFW
124 01:03   --- FFW
124 01:08   --- FFW
124 01:13   ---
124 01:18   ---
124 01:23   ---
124 01:28   ---
124 01:33   ---
124 01:38   ---
124 01:43   ---
124 01:48   ---
124 01:53   ---
124 01:58   ---
124 02:03   ---
124 02:08   ---
124 02:13   ---
124 02:18   ---
124 02:23   ---
124 02:28   ---
124 02:33   ---
124 02:38   ---
124 02:43   ---
124 02:48   ---
124 02:53   ---
124 02:58   ---
124 03:03   ---
124 03:08   ---
124 03:13   ---
124 03:18   ---
124 03:23   ---
124 03:28   ---
124 03:33   ---
124 03:38   ---
124 03:43   ---
124 03:48   ---
124 03:53   ---
124 03:58   ---
124 04:03   ---
124 04:08   ---
124 04:13   ---
124 04:18   ---
124 04:23   ---
124 04:28   ---
124 04:33   ---
124 04:38   ---
124 04:43   ---
124 04:48   ---
124 04:53   ---
124 04:58   ---
124 05:03   ---
124 05:08   ---
124 05:13   ---
124 05:18   ---
124 05:23   ---
124 05:28   ---
124 05:33   ---
124 05:38   ---
124 05:43   ---
124 05:48   ---
124 05:53   ---
124 05:58   ---
124 06:03   ---
124 06:08   ---
124 06:13   ---
124 06:18   ---
124 06:23   ---
124 06:28   ---
124 06:33   ---
124 06:38   ---
124 06:43   ---
124 06:48   ---
124 06:53   ---
124 06:58   ---
124 07:03   ---
124 07:08   ---
124 07:13   ---
124 07:18   ---
124 07:23   ---
124 07:28   ---
124 07:33   ---
124 07:38   ---
124 07:43   ---
124 07:48   ---
124 07:53   ---
124 07:58   ---
124 08:03   ---
124 08:08   ---
124 08:13   ---
124 08:18   ---
124 08:23   ---
124 08:28   ---
124 08:33   ---
124 08:38   ---
124 08:43   ---
124 08:48   ---
124 08:53   ---
124 08:58   ---
124 09:03   ---
124 09:08   ---
124 09:13   ---
124 09:18   ---
124 09:23   ---
124 09:28   ---
124 09:33   ---
124 09:38   ---
124 09:43   ---
124 09:48   ---
124 09:53   ---
124 09:58   ---
124 10:03   ---
124 10:08   ---
124 10:13   ---
124 10:18   ---
124 10:23   ---
124 10:28   ---
124 10:33   ---
124 10:38   ---
124 10:43   ---
124 10:48   ---
124 10:53   ---
124 10:58   ---
124 11:03   ---
124 11:08   ---
124 11:13   ---
124 11:18   ---
124 11:23   ---
124 11:28   ---
124 11:33   ---
124 11:38   ---
124 11:43   ---
124 11:48   ---
124 11:53   ---
124 11:58   ---
124 12:03   ---
124 12:08   ---
124 12:13   ---
124 12:18   ---
124 12:23   ---
124 12:28   ---
124 12:33   ---
124 12:38   ---
124 12:43   ---
124 12:48   ---
124 12:53   ---
124 12:58   ---
124 13:03   ---
124 13:08   ---
124 13:13   ---
124 13:18   ---
124 13:23   ---
124 13:28   ---
124 13:33   ---
124 13:38   ---
124 13:43   ---
124 13:48   ---
124 13:53   ---
124 13:58   ---
124 14:03   ---
124 14:08   ---
124 14:13   ---
124 14:18   ---
124 14:23   ---
124 14:28   ---
124 14:33   ---
124 14:38   ---
124 14:43   ---
124 14:48   ---
124 14:53   ---
124 14:58   ---
124 15:03   ---
124 15:08   ---
124 15:13   ---
124 15:18   ---
124 15:23   ---
124 15:28   ---
124 15:33   ---
124 15:38   ---
124 15:43   ---
124 15:48   ---
124 15:53   ---
124 15:58   ---
124 16:03   ---
124 16:08   ---
124 16:13   ---
124 16:18   ---
124 16:23   ---
124 16:28   ---
124 16:33   ---
124 16:38   ---
124 16:43   ---
124 16:48   ---
124 16:53   ---
124 16:58   ---
124 17:03   ---
124 17:08   ---
124 17:13   ---
124 17:18   ---
124 17:23   ---
124 17:28   ---
124 17:33   ---
124 17:38   ---
124 17:43   ---
124 17:48   ---
124 17:53   ---
124 17:58   ---
124 18:03   ---
124 18:08   ---
124 18:13   ---
124 18:18   ---
124 18:23   ---
124 18:28   ---
124 18:33   ---
124 18:38   ---
124 18:43   ---
124 18:48   ---
124 18:53   ---
124 18:58  SVA ---
124 19:03  SVA ---
124 19:08  SVA ---
124 19:13  SVA ---
124 19:18  SVA ---
124 19:23  SVA ---
124 19:28  SVA ---
124 19:33  SVA ---
124 19:38  SVA ---
124 19:43  SVA ---
124 19:48  SVA ---
124 19:53  SVA ---
124 19:58  SVA ---
124 20:03  SVA ---
124 20:08  SVA ---
124 20:13  SVA --- SVR
124 20:18  SVA --- SVR
124 20:23  SVA --- SVR
124 20:28  SVA --- SVR
124 20:33  SVA --- SVR
124 20:38  SVA --- SVR
124 20:43  SVA --- SVR
124 20:48  SVA --- SVR,SVR
124 20:53  SVA --- SVR,SVR
124 20:58  SVA --- SVR
124 21:03  SVA --- SVR
124 21:08  SVA --- SVR
124 21:13  SVA --- SVR
124 21:18  SVA --- SVR
124 21:23  SVR,SVA --- SVR
124 21:28  SVR,SVA --- SVR
124 21:33  SVR,SVA --- SVR
124 21:38  SVR,SVA --- SVR
124 21:43  SVR,SVA --- SVR
124 21:48  SVR,SVA ---
124 21:53  SVR,SVA ---
124 21:58  SVR,SVR,SVA ---
124 22:03  SVR,SVR,SVA ---
124 22:08  TOR,SVR,SVA ---
124 22:13  TOR,SVR,SVA ---
124 22:18  TOR,SVR,SVA ---
124 22:23  SVR,SVA ---
124 22:28  SVR,SVA ---
124 22:33  SVR,SVA ---
124 22:38  SVR,SVR,SVA ---
124 22:43  SVR,SVR,SVA ---
124 22:48  SVR,SVR,SVA ---
124 22:53  SVR,SVR,SVA ---
124 22:58  SVR,SVA ---
124 23:03  SVR,SVA ---
124 23:08  SVR,SVA ---
124 23:13  SVR,SVA ---
124 23:18  SVR,SVA ---
124 23:23  SVR,SVA ---
124 23:28  SVR,SVA ---
124 23:33  SVR,SVA ---
124 23:38  SVA ---
124 23:43  SVA --- SVR
124 23:48  SVA --- SVR
124 23:53  SVA --- SVR
124 23:58  SVA --- SVR
125 00:03  SVA --- SVR
125 00:08  SVA --- SVR
125 00:13  SVA --- SVR,SVR
125 00:18  SVA --- SVR,SVR
125 00:23  SVA --- SVR,SVR
125 00:28  SVA --- SVR,SVR
125 00:33  SVA --- SVR,SVR,SVR
125 00:38  SVA --- SVR,SVR,SVR
125 00:43  SVA --- SVR,SVR
125 00:48  SVA --- SVR,SVR
125 00:53  SVA --- SVR,SVR
125 00:58   --- SVR,SVR
125 01:03   --- SVR,SVR
125 01:08   --- SVR,SVR
125 01:13   --- SVR
125 01:18   --- SVR
125 01:23   --- SVR
125 01:28   --- SVR
125 01:33   ---
125 01:38   ---
125 01:43   ---
125 01:48   ---
125 01:53  SVR ---
125 01:58  SVR ---
125 02:03  SVR ---
125 02:08  SVR ---
125 02:13  SVR ---
125 02:18  SVR --- SVR
125 02:23  SVR --- SVR
125 02:28  SVR --- SVR
125 02:33  SVR --- SVR
125 02:38  SVR --- SVR
125 02:43  SVR --- SVR
125 02:48  SVR --- SVR
125 02:53  SVR --- SVR
125 02:58   --- SVR
125 03:03   --- SVR
125 03:08   --- SVR
125 03:13   --- SVR
125 03:18   --- SVR
125 03:23   ---
125 03:28   ---
125 03:33   ---
""".split("\n")

        buf = SAMECache("037183")
        # Iterate through this storm system 5 minutes at a time
        aix = 0
        eix = 0
        for t in range(int(alerts[0].get_start_time_sec()),
                       int(alerts[-1].get_start_time_sec() + alerts[-1].get_duration_sec() + 1000),
                       300):
            while aix < len(alerts) and alerts[aix].get_start_time_sec() <= t:
                buf.add_message(alerts[aix])
                aix += 1

            here = buf.get_active_messages(when=t)
            elsewhere = buf.get_active_messages(when=t, here=False)
            stat = time.strftime("%j %H:%M  ", time.gmtime(t)) + ",".join([x.get_event_type() for x in here]) \
                   + " --- " + ",".join([x.get_event_type() for x in elsewhere])
            self.assertEqual(expected[eix].strip(), stat.strip())
            eix += 1
