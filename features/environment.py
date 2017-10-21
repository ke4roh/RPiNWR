# -*- coding: utf-8 -*-
from behave import use_step_matcher
__author__ = 'jscarbor'

use_step_matcher("re")

def before_scenario(context, scenario):
    context.after_scenario_cleanup = []


def after_scenario(context, scenario):
    for f in context.after_scenario_cleanup:
        f(context, scenario)
