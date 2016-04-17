#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# look here: http://python-packaging-user-guide.readthedocs.org/en/latest/current/

from setuptools import setup, find_packages

with open('README.md') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='RPiNWR',
    version='0.0.1',
    description='Operate the Raspberry Pi NOAA Weather Radio Receiver and Decoder',
    long_description='This library provides basic operations and demonstration of features for the board',
    author='Jim Scarborough',
    author_email='jimes@hiwaay.net',
    url='https://github.com/ke4roh/RPiNWR',
    license='GNU GPL v.3',
    packages=find_packages(exclude=('tests', 'docs')),
    test_suite="tests",
)
