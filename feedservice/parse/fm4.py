#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# gPodder - A media aggregator and podcast client
# Copyright (c) 2005-2011 Thomas Perl and the gPodder Team
#
# gPodder is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# gPodder is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# XSPF playlist parser module for gPodder
# Thomas Perl <thp@gpodder.org>; 2010-08-07


# Currently, this is restricted to FM4 On Demand content, as the XSPF parser
# here isn't generic enough to parse all other feeds reliably. Please get in
# touch if you want support for other feeds - you can use the existing parser
# as a template for your own! :)
#
# See http://fm4.orf.at/radio/stories/audio for available feeds


import os
import time

import re
import feedparser

from xml.dom import minidom

from feedservice.urlstore import get_url
from feedservice.parse.models import Feed, Episode
from feedservice.parse.feed import Feedparser, FeedparserEpisodeParser
from feedservice.parse.mimetype import get_mimetype


class FM4OnDemandPlaylistParser(Feedparser):

    URL_REGEX = re.compile('http://onapp1\.orf\.at/webcam/fm4/fod/([^/]+)\.xspf$')

    CONTENT = {
            'spezialmusik': (
                'FM4 Sendungen',
                'http://onapp1.orf.at/webcam/fm4/fod/SOD_Bild_Spezialmusik.jpg',
                'http://fm4.orf.at/',
                'Sendungen jeweils sieben Tage zum Nachhören.',
            ),
            'unlimited': (
                'FM4 Unlimited',
                'http://onapp1.orf.at/webcam/fm4/fod/SOD_Bild_Unlimited.jpg',
                'http://fm4.orf.at/unlimited',
                'Montag bis Freitag (14-15 Uhr)',
            ),
            'soundpark': (
                'FM4 Soundpark',
                'http://onapp1.orf.at/webcam/fm4/fod/SOD_Bild_Soundpark.jpg',
                'http://fm4.orf.at/soundpark',
                'Nacht von Sonntag auf Montag (1-6 Uhr)',
            ),
    }


    @classmethod
    def handles_url(cls, url):
        return bool(cls.URL_REGEX.match(url))


    def get_text_contents(self, node):
        if hasattr(node, '__iter__'):
            return u''.join(self.get_text_contents(x) for x in node)
        elif node.nodeType == node.TEXT_NODE:
            return node.data
        else:
            return u''.join(self.get_text_contents(c) for c in node.childNodes)


    def __init__(self, feed_url, resp, text_processor=None):

        self.category = self.get_category(feed_url)
        # TODO: Use proper caching of contents with support for
        #       conditional GETs (If-Modified-Since, ETag, ...)
        self.data = minidom.parseString(resp.read())
        self.playlist = self.data.getElementsByTagName('playlist')[0]

        super(FM4OnDemandPlaylistParser, self).__init__(feed_url, resp,
                text_processor=text_processor)


    def get_category(cls, url):
        m = cls.URL_REGEX.match(url)
        if m is not None:
            return m.group(1)


    def get_title(self):
        title = self.playlist.getElementsByTagName('title')[0]
        default = self.get_text_contents(title)
        return self.CONTENT.get(self.category, \
                (default, None, None, None))[0]


    def get_logo_url(self):
        return self.CONTENT.get(self.category, \
                (None, None, None, None))[1]


    def get_link(self):
        return self.CONTENT.get(self.category, \
                (None, None, 'http://fm4.orf.at/', None))[2]


    def get_description(self):
        return self.CONTENT.get(self.category, \
                (None, None, None, 'XSPF playlist'))[3]


    def get_episodes(self):
        tracks = self.playlist.getElementsByTagName('track')
        parsers = [FM4EpisodeParser(t, text_processor=self.text_processor) for t in tracks]
        episodes = [p.get_episode() for p in parsers]
        return episodes



class FM4EpisodeParser(FeedparserEpisodeParser):

    def __init__(self, track, text_processor=None):
        self.title = self.get_text_contents(track.getElementsByTagName('title'))
        self.url = self.get_text_contents(track.getElementsByTagName('location'))
        super(FM4EpisodeParser, self).__init__({},
                text_processor=text_processor)


    def get_text_contents(self, node):
        if hasattr(node, '__iter__'):
            return u''.join(self.get_text_contents(x) for x in node)
        elif node.nodeType == node.TEXT_NODE:
            return node.data
        else:
            return u''.join(self.get_text_contents(c) for c in node.childNodes)


    def get_guid(self):
        return self.url


    def get_title(self):
        return self.title


    def list_files(self):
        if not self.url:
            return

        mimetype = get_mimetype(None, self.url)
        yield ([self.url], mimetype, None)


    def get_timestamp(self):
        return 0
