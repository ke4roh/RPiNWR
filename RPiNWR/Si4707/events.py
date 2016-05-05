# -*- coding: utf-8 -*-
__author__ = 'jscarbor'
import time

###############################################################################
# EVENTS
#
# Events occur after significant activity having to do with the radio.
###############################################################################
class Si4707Event(object):
    """
    Some radio-level thing happened.
    """

    def __init__(self):
        self.time = time.time()

    def __str__(self):
        return type(self).__name__ + " [" + ', '.join("%s: %s" % item for item in vars(self).items()) + "]"


class CommandExceptionEvent(Si4707Event):
    """
    There was a problem executing commands
    """

    def __init__(self, exception, passed_back):
        """
        :param exception - what went wrong
        :param passed_back - true if the exception has been passed back to the caller (in which case
        it's mostly useful for diagnostics).
        """

        super(CommandExceptionEvent, self).__init__()
        self.exception = exception
        self.passed_back = passed_back


class SAMEEvent(Si4707Event):
    pass


class SAMEMessageReceivedEvent(SAMEEvent):
    def __init__(self, same_message):
        super(SAMEMessageReceivedEvent, self).__init__()
        self.message = same_message


class SAMEHeaderReceived(SAMEEvent):
    def __init__(self, message):
        super(SAMEHeaderReceived, self).__init__()
        self.message = message
        self.header = message.headers[-1]

    def __str__(self):
        return "SAMEHeaderReceived: %s" % str(self.header)


class EndOfMessage(SAMEEvent):
    pass


class NotClearToSend(Exception):
    """
    Clear To Send did not happen before the timeout
    """
    pass


class RadioPowerEvent(Si4707Event):
    """
    Sent when the radio is turned on or off.
    """

    def __init__(self, power_on):
        super(RadioPowerEvent, self).__init__()
        self.power_on = power_on


class ReadyToTuneEvent(Si4707Event):
    """
    Sent after power-up when the oscillator has had time to stabilize
    """
    pass
