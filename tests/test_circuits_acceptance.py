# -*- coding: utf-8 -*-
__author__ = 'ke4roh'

import unittest
from circuits import Component, Event, Timer, BaseComponent, handler
import time


class TestCircuits(unittest.TestCase):
    """This is to make sure Circuits will do what we expect it to do.  It's not meant to be a replacement
    for circuits tests, but more of an assurance that it generally works in ways that are especially critical
    to the success of this project.
    """

    def test_multiple_send(self):
        runs = 10000

        times = [0, 0, 0, 0]

        class hello(Event):
            """hello Event"""

        class terminate(Event):
            """terminate Event"""

        class App(Component):
            def hello(self):
                """Hello Event Handler"""
                times[0] = time.time()
                times[1] += 1

            def started(self, *args):
                """Started Event Handler

                This is fired internally when your application starts up
                and can be used to trigger events that only occur once
                during startup.
                """
                times[2] = time.time()
                for i in range(0, runs):
                    self.fire(hello())  # Fire hello Event
                self.fire(terminate())

            def terminate(self):
                self.stop()

        class Bpp(Component):
            def hello(self):
                times[3] += 1

        app = App()
        Bpp().register(app)
        app.run()
        self.assertEqual(runs, times[1])
        self.assertEqual(runs, times[3])

        # It has to be fast - understandably the test environment is probably not identical to the
        # runtime environment, but an approximation of fast will suffice.
        self.assertTrue((times[0] - times[2]) / times[1] < 0.001)
        # self.fail(str((times[0] - times[2]) / times[1])) # 1.16e-5 with 1 listener, 1.20e-5 with 2

    def test_cross_tree(self):
        times = []

        class hello(Event):
            """hello Event"""

        class terminate(Event):
            """terminate Event"""

        class App(Component):
            def hello(self, origin):
                """Hello Event Handler"""
                times.append(origin + " from A")

            def started(self, *args):
                """Started Event Handler

                This is fired internally when your application starts up
                and can be used to trigger events that only occur once
                during startup.
                """
                self.fire(hello('A'))
                self.fire(terminate())

            def terminate(self):
                self.stop()

        class Bpp(Component):
            def hello(self, origin):
                times.append(origin + " from B")
                if origin == 'A':
                    self.fire(hello('B'))

        class Cpp(Component):
            def hello(self, origin):
                times.append(origin + " from C")
                if origin == 'A':
                    self.fire(hello('C'))

        class Dpp(Component):
            def hello(self, origin):
                times.append(origin + " from D")
                if origin == 'A':
                    self.fire(hello('D'))

        app = App()
        Bpp().register(app)
        cpp = Cpp()
        cpp.register(app)
        Dpp().register(cpp)
        app.run()

        # Everything in the tree of components sees everything else
        self.assertEquals(16, len(times))

        times.clear()
        cpp.unregister()
        # And here we run it twice - that's an interesting use case (but not necessary)
        app.run()

        # Removal of one component removes those beneath it
        self.assertEquals(4, len(times))

    def test_poller(self):
        times = []

        class doit(Event):
            """doit Event"""

        class App(BaseComponent):
            timer = Timer(.1, doit('A'), persist=True)

            def __init__(self):
                super().__init__()
                self.count = 0

            @handler("doit")
            def _doit(self, origin):
                times.append("%s from A at %.03f" % (origin, time.time()))
                self.count += 1
                if self.count > 4:
                    self.stop()

        App().run()
        self.assertEquals(5, len(times))
