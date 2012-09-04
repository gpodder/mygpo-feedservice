"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TestCase

from feedservice.parse.feed import Feedparser
from feedservice.parse import parse_feed


class SimpleTest(TestCase):

    def test_basic_parse(self):
        """
        Tests that 1 + 1 always equals 2.
        """

        URL = 'http://feeds.feedburner.com/linuxoutlaws'

        parse_feed(URL)
