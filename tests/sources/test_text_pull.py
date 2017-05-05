# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# test the text_pull code
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
from .test_sources import ManagerTest, Watcher
from RPiNWR.sources import TextPull
from circuits import Debugger
from circuits.web import Server, Controller, expose
import io
import os
import time


class _data(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class TestTextPull(ManagerTest):
    def testCallback(self):
        self.manager.append(
            TextPull({'warnzone': "ILZ001", 'warncounty': "ILC085",
                      'firewxzone': "ILZ001", 'local_place1': "6 Miles W Stockton IL",
                      'lat': 42.36, 'lon': -90.12}, url=None)
        )
        tp = self.manager[-1]

        sb = io.StringIO()
        sw = Watcher()
        (tp + Debugger(file=sb) + sw).start()
        sw.wait_for_start()

        body = []
        for fn in ["", "2"]:
            with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "svr-detail%s.html" % fn), "rb") as f:
                body.append(f.read())

        tp._receive_response(_data(status=200, read=lambda: body[0]))
        sw.wait_for_n_events(4, lambda x: x[0].name == "new_message", 1)
        # There are 5 messages in this first file, but the first is duplicated, so it contains 4 distinct messages.
        self.assertEqual(4, sb.getvalue().count("new_message"))
        tp._receive_response(_data(status=200, read=lambda: body[1]))
        sw.wait_for_n_events(5, lambda x: x[0].name == "new_message", 1)
        self.assertEqual(5, sb.getvalue().count("new_message"))

    def testFetcher(self):
        # mock server
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "svr-detail2.html"), "rb") as f:
            body = f.read()

        class Root(Controller):
            def __init__(self):
                self.received_headers = []
                super().__init__()

            @expose("showsigwx.php")
            def index(self, *args, **kwargs):
                self.received_headers.append(self.request.headers)
                return body

        mockmonitor = Watcher()
        mockroot = Root()
        self.manager.append((Server(("0.0.0.0", 9000)) + mockroot + mockmonitor))
        self.manager[-1].start()
        mockmonitor.wait_for_n_events(1, lambda x: x[0].name == "ready", .5)
        # End mock server


        # TextPull is under test here
        tp = TextPull({'warnzone': "ILZ001", 'warncounty': "ILC085",
                       'firewxzone': "ILZ001", 'local_place1': "6 Miles W Stockton IL",
                       'lat': 42.36, 'lon': -90.12}, url="http://localhost:9000/")

        self.manager.append(tp)
        tp.timer.reset(interval=.5)
        sw = Watcher()
        (tp + sw).start()

        sw.wait_for_n_events(5, lambda x: x[0].name == "new_message", 2)
        sw.wait_for_n_events(2, lambda x: x[0].name == "request", 1)
        time.sleep(.5)

        self.assertEqual(5, len(list(filter(lambda x: x[0].name == "new_message", sw.events))))
        for h in mockroot.received_headers:
            self.assertEquals('*/*', h['Accept'])
            self.assertEquals('RPiNWR/0.0.1', h['User-Agent'])
