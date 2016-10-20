# -*- coding: utf-8 -*-
__author__ = 'ke4roh'

from RPiNWR.sources import TextPull, FolderMonitor
from threading import Condition
import unittest
import os
from circuits import Debugger
import io
import time
from circuits.web import Server, Controller, expose
from circuits import Component, handler
from shutil import rmtree


class _data(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Watcher(Component):
    def __init__(self):
        super().__init__()
        self.__cv = Condition()
        self.started = False
        self.events = []

    def started(self, component):
        with self.__cv:
            self.started = True
            self.__cv.notify_all()

    def wait_for_start(self):
        with self.__cv:
            while not self.started:
                self.__cv.wait()

    @handler(priority=-100)
    def _on_event(self, event, *args, **kwargs):
        with self.__cv:
            self.events.append((event, args, kwargs))
            self.waitEvent(event)
            self.__cv.notify_all()

    def wait_for_n_events(self, n, filter_function, timeout=float("inf")):
        toolate = time.time() + timeout
        lll = []

        def ll():
            lll.clear()
            lll.extend(filter(filter_function, self.events))
            return lll

        with self.__cv:
            while time.time() < toolate and len(ll()) < n:
                self.__cv.wait()
        if time.time() >= toolate:
            raise TimeoutError("n = %d\n" % len(lll) + "\n".join([str(e) for e in self.events]))
        return lll


class ManagerTest(unittest.TestCase):
    def setUp(self):
        self.manager = []

    def tearDown(self):
        for mgr in self.manager:
            mgr.stop()


class TestPollFolder(ManagerTest):
    def tearDown(self):
        super().tearDown()
        rmtree("dropzone")

    def testFileDrop(self):
        location = {'warnzone': "ILZ001", 'warncounty': "ILC085",
                    'firewxzone': "ILZ001", 'local_place1': "6 Miles W Stockton IL",
                    'lat': 42.36, 'lon': -90.12}
        if not os.path.exists("dropzone"):
            os.makedirs("dropzone")
        fm = FolderMonitor(location, "dropzone", .25)
        mockmonitor = Watcher()
        system = fm + mockmonitor
        self.manager.append(system)
        system.start()
        mockmonitor.wait_for_start()
        time.sleep(1)

        with open("dropzone/wxreport", "w") as f:
            f.write("""
SEVERE THUNDERSTORM WARNING
MEC001-005-015-023-232100-
/O.NEW.KGYX.SV.W.0082.160723T2016Z-160723T2100Z/

BULLETIN - IMMEDIATE BROADCAST REQUESTED
SEVERE THUNDERSTORM WARNING
NATIONAL WEATHER SERVICE GRAY ME
416 PM EDT SAT JUL 23 2016

THE NATIONAL WEATHER SERVICE IN GRAY MAINE HAS ISSUED A

* SEVERE THUNDERSTORM WARNING FOR...
  SOUTHEASTERN SAGADAHOC COUNTY IN SOUTH CENTRAL MAINE...
  SOUTHWESTERN LINCOLN COUNTY IN SOUTH CENTRAL MAINE...
  SOUTHEASTERN ANDROSCOGGIN COUNTY IN SOUTHWESTERN MAINE...
  EAST CENTRAL CUMBERLAND COUNTY IN SOUTHWESTERN MAINE...

* UNTIL 500 PM EDT

* AT 415 PM EDT...A SEVERE THUNDERSTORM WAS LOCATED NEAR
  FREEPORT...OR NEAR BRUNSWICK...MOVING SOUTHEAST AT 30 MPH.

  HAZARD...60 MPH WIND GUSTS AND QUARTER SIZE HAIL.

  SOURCE...RADAR INDICATED.

  IMPACT...HAIL DAMAGE TO VEHICLES IS EXPECTED. EXPECT WIND DAMAGE
           TO ROOFS...SIDING...AND TREES.

* LOCATIONS IMPACTED INCLUDE...
  BRUNSWICK...BATH...FREEPORT...GEORGETOWN...YARMOUTH...HARPSWELL...
  AROWSIC...PHIPPSBURG AND WEST BATH.

PRECAUTIONARY/PREPAREDNESS ACTIONS...

FOR YOUR PROTECTION MOVE TO AN INTERIOR ROOM ON THE LOWEST FLOOR OF A
BUILDING.

LARGE HAIL AND DAMAGING WINDS AND CONTINUOUS CLOUD TO GROUND
LIGHTNING IS OCCURRING WITH THIS STORM. MOVE INDOORS IMMEDIATELY.
LIGHTNING IS ONE OF NATURE`S LEADING KILLERS. REMEMBER...IF YOU CAN
HEAR THUNDER...YOU ARE CLOSE ENOUGH TO BE STRUCK BY LIGHTNING.

TORRENTIAL RAINFALL IS OCCURRING WITH THIS STORM...AND MAY LEAD TO
FLASH FLOODING. DO NOT DRIVE YOUR VEHICLE THROUGH FLOODED ROADWAYS.

&&

LAT...LON 4374 6970 4363 6981 4378 7015 4393 7010
      4385 6970
TIME...MOT...LOC 2015Z 299DEG 24KT 4384 7004

HAIL...1.00IN
WIND...60MPH

$$
EKSTER

            """)
        nm = mockmonitor.wait_for_n_events(1, lambda x: x[0].name == "new_message", 2)
        self.assertEqual(1, len(nm))
        self.assertEqual("/O.NEW.KGYX.SV.W.0082.160723T2016Z-160723T2100Z/", nm[0][1][0].raw)


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
            @expose("showsigwx.php")
            def index(self, *args, **kwargs):
                return body

        mockmonitor = Watcher()
        self.manager.append((Server(("0.0.0.0", 9000)) + Root() + mockmonitor))
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
