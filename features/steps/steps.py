# -*- coding: utf-8 -*-
from enum import Enum

__author__ = 'jscarbor'

from behave import *
from tests.mock_clock import MockClock
from tests.messages.message_mocker import mocker as msg_mocker, TZ
import time
from math import ceil
from RPiNWR.messages.cache import MessageCache
from circuits import Debugger, Component
from RPiNWR.alerting import AlertTimer
from RPiNWR.sources.radio.radio_component import Radio_Component
from RPiNWR.sources.radio.radio_squelch import Radio_Squelch
import threading
import re
from tests.test_integration import DummyLogger, ScriptInjector
from tests.sources.test_sources import Watcher
from RPiNWR.sources import TextPull
from circuits.web import Server, Controller, expose
import datetime


class HotMessageMonitor(Component):
    def __init__(self, clock):
        super().__init__()
        self.score = None
        self.message = None
        self.score_log = []
        self.clock = clock
        self.listeners = []
        self.netstat = None

    def net_status(self, status):
        self.netstat = status

    def new_score(self, score, message):
        self.score = score
        self.message = message
        self.score_log.append((self.clock.time(), score))
        for l in self.listeners:
            l(score, message)

    def add_listener(self, callable):
        self.listeners.append(callable)

    def remove_listener(self, callable):
        self.listeners.remove(callable)


@given(
    'a radio at 35.77N, 78.64E in 037183 monitoring text alerts from the web')
def initialize_radio(context):
    context.after_all = lambda: context.clock.stop()

    context.location = location = {
        'lat': 35.77,
        'lon': -78.64,
        'fips6': '037183',
        'warnzone': 'NCZ183',
        'firewxzone': 'NCZ183'
    }
    logger = context.radio_logger = DummyLogger(clock=context.clock.time)

    si4707args = "--hardware-context RPiNWR.sources.radio.Si4707.mock.MockContext --mute-after 0  --transmitter WXL58".split()
    context.radio_injector = ScriptInjector()
    context.hot_message_monitor = HotMessageMonitor(context.clock)
    context.radio = box = Radio_Component(si4707args,
                                          clock=context.clock.time) + Radio_Squelch() + \
                          TextPull(location=location,
                                   url='http://localhost:8012/') + \
                          AlertTimer(continuation_reminder_interval_sec=.05,
                                     clock=context.clock.time) + \
                          MessageCache(location, clock=context.clock.time) + \
                          context.hot_message_monitor + \
                          Debugger() + \
                          Debugger(
                              logger=context.radio_logger) + context.radio_injector

    box.start()
    context.after_scenario_cleanup.append(lambda ctx, y: ctx.radio.stop())

    logger.wait_for_n_events(1, re.compile('<started.*'), 5)

    logger.wait_for_n_events(1, re.compile('<radio_status.*'), 5)

    assert len(logger.debug_history) < 20, str(logger.debug_history)


class MessageType(Enum):
    toa_new = "toa-new"
    toa_con = "toa-con"
    tow_new = "tow-new"
    tow_con = "tow-con"


_SAME_TYPE = {
    MessageType.toa_new: "TOA",
    MessageType.toa_con: "TOA",
    MessageType.tow_new: "TOR",
    MessageType.tow_con: "TOR"
}

_SAME_WORDS = {
    "TOA": "Tornado Watch",
    "TOR": "Tornado Warning"
}


class MockMessageInNWS(object):
    """
    A representation of a NWS message (watch, warning, statement) as it is being disseminated
    """

    def __init__(self, message_type, issue_time, duration_min, counties, polygon=None):
        self.message_type = message_type
        self.issue_time = issue_time
        self.duration_min = duration_min
        self.counties = counties
        self.polygon = polygon


class MockNWS(object):
    """
    Pretend to be the NWS.  Issue alerts of different kinds with the appropriate time differentials.
    """
    def __init__(self, context, net_delay):
        """
        :param context: The context in which this MockNWS is installed
        :param net_delay: The duration in seconds net is behind the radio (negative means net is ahead)
        """
        self.messages = []

        class Root(Controller):
            def __init__(self):
                self.received_headers = []
                super().__init__()

            @expose("showsigwx.php")
            def index(self, *args, **kwargs):
                self.received_headers.append(self.request.headers)
                return msg_mocker.get_template("web_status.html").render(self.messages)

        self.nws_watcher = Watcher()
        self.nws_server = nws_server = (Server(("0.0.0.0", 8012)) + Root() + self.nws_watcher)
        nws_server.start()
        context.after_scenario_cleanup.append(lambda ctx, y: self.shutdown(ctx, y))
        self.nws_watcher.wait_for_n_events(1, lambda x: x[0].name == "ready", .5)
        self.context = context
        self.clock = context.clock
        self.net_delay = net_delay
        # End mock server

    # Put the message on the web site
    def _add_nws_message(self, msg):
        mtype = msg.message_type
        mt = {
            "start": datetime.datetime.fromtimestamp(msg.issue_time, tz=TZ['Z']).astimezone(TZ['EDT']),
            "polygon": msg.polygon
        }
        mt["end"] = mt["start"] + datetime.timedelta(minutes=msg.duration_min)
        self.messages.append(
            {"title": _SAME_WORDS[_SAME_TYPE[mtype]], "body": msg_mocker.get_template(mtype.value + ".txt").render(mt)})

    def _send_same_message(self, msg):
        self.context.radio_injector.inject("send -WXR-%s-0%s+%04d-%s-KRAH/NWS-" %
                                   (_SAME_TYPE[msg.message_type],
                                    "-0".join(msg.counties),
                                    ceil(msg.duration_min / 15) * 15,
                                    time.strftime('%j%H%M', time.gmtime(msg.issue_time))))

    def send_alert(self, nws_message):
        if self.net_delay > 0:
            self.clock.after(self.net_delay, lambda: self._add_nws_message(nws_message))
            self._send_same_message(nws_message)
        else:
            self.clock.after(-self.net_delay, lambda: self._send_same_message(nws_message))
            self._add_nws_message(nws_message)

    def shutdown(self, ctx, y):
        self.nws_server.stop()


@given(
    "the National Weather Service publishes alerts to the web (?P<web_delay_secs_str>\d+) seconds after the radio")
def init_nws_text_server(context, web_delay_secs_str):
    # Start this test at the top of the hour, at least an hour before the current time
    # Top of the hour gives some repeatability.
    # It's based on the current time because otherwise the radio will infer the wrong year on message timestamps.
    t = int((time.time() - 60 * 60) / (60 * 60)) * 60 * 60
    context.clock = MockClock(epoch=t)
    context.nws = MockNWS(context, int(web_delay_secs_str))
    # mock server


@when("the NWS issues a Tornado Watch for my area")
def issue_tornado_watch(context):
    context.nws.send_alert(
        MockMessageInNWS(MessageType.toa_new, context.clock.time(), 120, ("37183",))
    )


@then("the alert level on the radio goes up to (?P<score>\d+) within (?P<secs>\d+) seconds")
def then_alert_goes_up(context, score, secs):
    timeout = context.clock.time() + int(secs)
    while True:
        if context.hot_message_monitor.score is not None and \
                        context.hot_message_monitor.score >= int(score):
            break
        if context.clock.time() > timeout:
            raise TimeoutError(str(context.hot_message_monitor.score_log))
        context.clock.sleep(min(1, timeout - context.clock.time()))


@then("the alert level on the radio stays at (?P<score_str>\d+) for (?P<secs_str>\d+) seconds")
def score_stays_same(context, score_str, secs_str):
    score = int(score_str)
    secs = int(secs_str)
    end_time = context.clock.time() + secs
    score_box = [threading.Condition(), context.hot_message_monitor.score]

    def listener(sc, message):
        with score_box[0]:
            score_box[1] = sc
            score_box[0].notify_all()

    context.hot_message_monitor.add_listener(listener)
    while context.clock.time() < end_time:
        if context.hot_message_monitor.score != score:
            raise AssertionError("%s != %s" % (context.hot_message_monitor.score, score))
        with score_box[0]:
            score_box[0].wait(secs / context.clock.speedup)


@then("the most urgent message on the radio is a TOA")
def the_most_urgent_message_is(context):
    assert context.hot_message_monitor.message.get_event_type() == "TOA"


@when("the NWS issues a TOW for elsewhere")
def the_nws_issues_a_tow(context):
    lat = context.location['lat']
    lon = context.location['lon']
    polygon = [lat + .03, lon - .05, lat - .05, lon - .05, lat, lon - .07]

    context.nws.send_alert(
        MockMessageInNWS(MessageType.tow_new, context.clock.time(), 30, ("37183",), polygon)
    )


@when("the NWS updates the TOW to include my location")
def the_nws_updates_tow_for_here(context):
    lat = context.location['lat']
    lon = context.location['lon']
    polygon = [lat + .03, lon - .05, lat - .05, lon - .05, lat, lon + .07]

    context.nws.send_alert(
        MockMessageInNWS(MessageType.tow_new, context.clock.time(), 30, ("37183",), polygon)
    )
