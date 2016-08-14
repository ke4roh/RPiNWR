# -*- coding: utf-8 -*-
__author__ = 'ke4roh'

from RPiNWR.sources import TextPull
from threading import Timer, Condition
import unittest
import os
from circuits import Debugger
import io
import time
from circuits.web import Server, Controller, expose
from circuits import Component, handler


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
        with self.__cv:
            while time.time() < toolate and len(list(filter(filter_function, self.events))) < n:
                self.__cv.wait()
        if time.time() >= toolate:
            raise TimeoutError("n = %d" % len(list(filter(filter_function, self.events))))


class TestTextPull(unittest.TestCase):
    def setUp(self):
        self.manager = []

    def tearDown(self):
        for mgr in self.manager:
            mgr.stop()

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
