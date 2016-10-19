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
    long_description="""
    This library provides basic operations and demonstration of features for a Si4707-based weather radio
    running on a Raspberry Pi.
    """,
    author='Jim Scarborough',
    author_email='jimes@hiwaay.net',
    url='https://github.com/ke4roh/RPiNWR',
    license='GNU GPL v.3',
    packages=find_packages(exclude=('tests', 'docs')),
    # install_requires=['Adafruit_Python_GPIO'],
    # dependency_links=[
    #   'git+https://github.com/nioinnovation/Adafruit_Python_GPIO.git'
    # ],
    install_requires=['urllib3', 'shapely', 'iso8601', 'circuits', 'lxml', 'python-dateutil', 'watchdog', 'pygame'],
    setup_requires=['pytest-runner'],
    tests_require=['pytest'],
    test_suite="tests",
)
