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

# Soundcloud.com API client module for gPodder
# Thomas Perl <thp@gpodder.org>; 2009-11-03

import os
import time

import re
import email
import email.Header

from django.conf import settings

from feedservice.parse.models import Feed, Episode, File
from feedservice.parse.feed import Feedparser, FeedparserEpisodeParser
from feedservice.urlstore import fetch_url
from feedservice.parse.mimetype import get_mimetype
from feedservice.utils import json



class SoundcloudUser(object):
    def __init__(self, username):
        self.username = username

    def get_coverart(self):
        key = ':'.join((self.username, 'avatar_url'))

        image = None
        json_url = 'http://api.soundcloud.com/users/%s.json?consumer_key=%s' % (self.username, settings.SOUNDCLOUD_CONSUMER_KEY)

        resp = fetch_url(json_url)
        user_info = json.loads(resp.read())
        return user_info.get('avatar_url', None)


    def get_tracks(self, feed):
        """Get a generator of tracks from a SC user

        The generator will give you a dictionary for every
        track it can find for its user."""

        json_url = 'http://api.soundcloud.com/users/%(user)s/%(feed)s.json?filter=downloadable&consumer_key=%(consumer_key)s' \
                % { "user":self.username, "feed":feed, "consumer_key": settings.SOUNDCLOUD_CONSUMER_KEY }

        res = fetch_url(json_url)
        tracks = (track for track in json.loads(res.read()) \
                if track['downloadable'])

        for track in tracks:
            # Prefer stream URL (MP3), fallback to download URL
            url = track.get('stream_url', track['download_url']) + \
                '?consumer_key=%(consumer_key)s' \
                % { 'consumer_key': settings.SOUNDCLOUD_CONSUMER_KEY }

            yield {
                'title': track.get('title', track.get('permalink', 'Unknown track')),
                'link': track.get('permalink_url', 'http://soundcloud.com/'+self.username),
                'description': track.get('description', 'No description available'),
                'url': url,
                'guid': track.get('permalink', track.get('id')),
                'pubDate': self.parsedate(track.get('created_at', None)),
            }


    @staticmethod
    def get_param(s, param='filename', header='content-disposition'):
        """Get a parameter from a string of headers

        By default, this gets the "filename" parameter of
        the content-disposition header. This works fine
        for downloads from Soundcloud.
        """
        msg = email.message_from_string(s)
        if header in msg:
            value = msg.get_param(param, header=header)
            decoded_list = email.Header.decode_header(value)
            value = []
            for part, encoding in decoded_list:
                if encoding:
                    value.append(part.decode(encoding))
                else:
                    value.append(unicode(part))
            return u''.join(value)

        return None


    def get_metadata(self, url):
        """Get file download metadata

        Returns a (size, type, name) from the given download
        URL. Will use the network connection to determine the
        metadata via the HTTP header fields.
        """

        res = fetch_url(url, headers_only=True)

        return res.length, res.content_type, os.path.basename(os.path.dirname(res.url))


    @staticmethod
    def parsedate(s):
        """Parse a string into a unix timestamp

        Only strings provided by Soundcloud's API are
        parsed with this function (2009/11/03 13:37:00).
        """
        m = re.match(r'(\d{4})/(\d{2})/(\d{2}) (\d{2}):(\d{2}):(\d{2})', s)
        return time.mktime([int(x) for x in m.groups()]+[0, 0, -1])


class SoundcloudParser(Feedparser):
    URL_REGEX = re.compile('http://([a-z]+\.)?soundcloud\.com/([^/]+)$', re.I)

    @classmethod
    def handles_url(cls, url):
        return bool(cls.URL_REGEX.match(url))


    def __init__(self, feed_url, resp, text_processor=None):
        m = self.__class__.URL_REGEX.match(feed_url)
        subdomain, self.username = m.groups()
        self.sc_user = SoundcloudUser(self.username)

        super(SoundcloudParser, self).__init__(feed_url, resp,
                text_processor=text_processor)


    def get_title(self):
        return '%s on Soundcloud' % self.username

    def get_logo_url(self):
        return self.sc_user.get_coverart()

    def get_link(self):
        return 'http://soundcloud.com/%s' % self.username

    def get_description(self):
        return 'Tracks published by %s on Soundcloud.' % self.username

    def get_author(self):
        return self.username

    def get_episodes(self):
        tracks = self.sc_user.get_tracks('tracks')
        parsers = [SoundcloudEpisodeParser(t, self.get_author(),
                text_processor=self.text_processor) for t in tracks]
        return [p.get_episode() for p in parsers]




class SoundcloudFavParser(SoundcloudParser):
    URL_REGEX = re.compile('http://([a-z]+\.)?soundcloud\.com/([^/]+)/favorites', re.I)


    def __init__(self, *args, **kwargs):
        super(SoundcloudFavParser,self).__init__(*args, **kwargs)


    @classmethod
    def handles_url(cls, url):
        return bool(cls.URL_REGEX.match(url))


    def get_title(self):
        return '%s\'s favorites on Soundcloud' % self.username

    def get_link(self):
        return 'http://soundcloud.com/%s/favorites' % self.username

    def get_description(self):
        return 'Tracks favorited by %s on Soundcloud.' % self.username



class SoundcloudEpisodeParser(FeedparserEpisodeParser):


    def __init__(self, track, author, text_processor=None):
        super(SoundcloudEpisodeParser, self).__init__(track,
                text_processor=text_processor)
        self.author = author


    def get_guid(self):
        return self.entry.get('guid', None)


    def get_title(self):
        return self.entry.get('title', None)


    def get_link(self):
        return self.entry.get('link', None)


    def get_author(self):
        return self.author


    def get_description(self):
        return self.entry.get('description', None)


    def get_duration(self):
        return None


    def get_language(self):
        return None


    def get_files(self):
        url = self.entry.get('url', None)
        mimetype = get_mimetype(self.entry.get('mimetype', None), url)
        filesize = self.entry.get('length', None)

        yield File([url], mimetype, filesize)


    def get_timestamp(self):
        return int(self.entry.get('pubDate', None))
