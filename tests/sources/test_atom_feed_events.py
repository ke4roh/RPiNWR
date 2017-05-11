# -*- coding: utf-8 -*-
__author__ = 'ke4roh'
# Copyright © 2016 James E. Scarborough
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later 0version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# https://alerts.weather.gov/cap/pdf/CAP%20v12%20guide%20web%2006052013.pdf

import unittest
import os
from glob import glob
import time
import http.server
import socketserver
import threading
import shutil
import logging
import calendar
import RPiNWR.sources.atom_events as ae
from RPiNWR.messages.CAP import CAPMessage
import pickle


class OneFileAtATimeHandler(http.server.BaseHTTPRequestHandler):
    """
    This handler returns each file in turn on subsequent calls.
    """
    files = sorted(glob(os.path.join(os.path.dirname(os.path.realpath(__file__)), "atom", "atom*.xml")))
    index = 0

    def __init__(self, request, client_address, server):
        super().__init__(request, client_address, server)
        self.protocol_version = "HTTP/1.1"

    def do_GET(self):
        file = OneFileAtATimeHandler.files[OneFileAtATimeHandler.index]
        OneFileAtATimeHandler.index += 1
        if OneFileAtATimeHandler.index >= len(OneFileAtATimeHandler.files):
            self.send_error(410, message="GONE")
            return

        logging.error("Serving " + file)
        self.send_response(200)
        self.send_header("Content-type", "application/rss+xml")
        self.send_header("Content-Length", os.path.getsize(file))
        self.end_headers()

        with open(file, 'rb') as f:
            shutil.copyfileobj(f, self.wfile)

    def date_time_string(self, timestamp=None):
        # The Date header here is the time that the file was received, to tag the event with the appropriate time
        return OneFileAtATimeHandler.__http_date(OneFileAtATimeHandler.files[OneFileAtATimeHandler.index - 1][-28:-4])

    @staticmethod
    def __http_date(time_str):
        """
        :param time_str: a date of the form 2016-05-24T21:24:05-0400
        :return: the time in HTTP format
        """
        tz = time_str[-5:]
        tzo = 60 * (int(tz[-2:]) + 60 * int(tz[-4:-2]))
        if tz[-5] == '-':
            tzo = -tzo
        date = calendar.timegm(time.strptime(time_str[0:-5], '%Y-%m-%dT%H:%M:%S')) - tzo
        return time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime(date))


class TestAtomCAPFeed(unittest.TestCase):
    def __init__(self, methodName="runTest"):
        super().__init__(methodName)
        self.PORT = 1989
        self.httpd = None

    def setUp(self):
        self.original_cwd = os.getcwd()
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
        self.PORT = 1989
        self.httpd = socketserver.TCPServer(("", self.PORT), OneFileAtATimeHandler)
        t = threading.Thread(target=self.start_web_server, daemon=True)
        t.start()

    def start_web_server(self):
        print("serving at port", self.PORT)
        self.httpd.serve_forever()

    def tearDown(self):
        self.httpd.shutdown()
        os.chdir(self.original_cwd)

    def export_atom_events(self):
        """
        This is a utility to extract a more wieldy subset of data for testing purposes than an evening's
        storm reports captured every 30 seconds.  It is not meant to run as a test every time, but rather as a tool
        to construct test data for situations going forward.

        While this code's correct execution is indicative of a (reasonably correct) implementation of the
        atom feed, it is not an exhaustive test with respect to error handling, nor is it fast enough, nor
        does it perform necessary assertions.

        :return:
        """
        wfo = {"KDDC", "KGLD", "KWNS"}  # This is where the action was when I was capturing messages
        specific_wfo_events = []

        def atom_event_handler(event):
            if event.__class__ is ae.NewAtomEntry:
                cap = CAPMessage(event.message)
                print(str(cap))
                if len(wfo & set([x.office_id for x in filter(lambda x: x.raw, cap.vtec)])):
                    specific_wfo_events.append((event.time, cap))
            else:
                print(str(event))

        aeg = ae.AtomEventGenerator("http://localhost:1989/", atom_event_handler, polling_interval_sec=.01)
        timeout = time.time() + 600  # 600 to get them all
        while time.time() < timeout and 410 != aeg.status.msg:
            # TODO get this to die gracefully rather than wait for timeout when killed
            time.sleep(.1)
        aeg.stop = True

        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "_".join(sorted(wfo)).lower() + ".cap.p"),
                  "wb") as f:
            pickle.dump(specific_wfo_events, f)

        self.assertTrue(time.time() < timeout)

        # TODO write a simple test for atom events (not a loop over 2 hours of storms)
        # TODO test for web error handling
