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

try:
    import simplejson as json
except ImportError:
    import json

import os
import time

import re
import email
import email.Header

from django.conf import settings

from feedservice.parserservice.models import Feed, Episode
from feedservice.urlstore import get_url
from feedservice.parserservice.mimetype import get_mimetype



class SoundcloudUser(object):
    def __init__(self, username):
        self.username = username

    def get_coverart(self):
        key = ':'.join((self.username, 'avatar_url'))

        image = None
        try:
            json_url = 'http://api.soundcloud.com/users/%s.json?consumer_key=%s' % (self.username, settings.SOUNDCLOUD_CONSUMER_KEY)
            _url, content, _last_mod_up, _last_mod_utc, etag, _content_type, \
            _length = get_url(json_url)
            user_info = json.loads(content)
            return user_info.get('avatar_url', None)

        except:
            return None


    def get_tracks(self, feed):
        """Get a generator of tracks from a SC user

        The generator will give you a dictionary for every
        track it can find for its user."""

        json_url = 'http://api.soundcloud.com/users/%(user)s/%(feed)s.json?filter=downloadable&consumer_key=%(consumer_key)s' \
                % { "user":self.username, "feed":feed, "consumer_key": settings.SOUNDCLOUD_CONSUMER_KEY }
        _url, content, _last_mod_up, _last_mod_utc, etag, _content_type, \
        _length = get_url(json_url)
        tracks = (track for track in json.loads(content) \
                if track['downloadable'])

        for track in tracks:
            # Prefer stream URL (MP3), fallback to download URL
            url = track.get('stream_url', track['download_url']) + \
                '?consumer_key=%(consumer_key)s' \
                % { 'consumer_key': settings.SOUNDCLOUD_CONSUMER_KEY }

            filesize, filetype, filename = self.get_metadata(url)

            yield {
                'title': track.get('title', track.get('permalink', 'Unknown track')),
                'link': track.get('permalink_url', 'http://soundcloud.com/'+self.username),
                'description': track.get('description', 'No description available'),
                'url': url,
                'length': int(filesize),
                'mimetype': filetype,
                'guid': track.get('permalink', track.get('id')),
                'pubDate': self.soundcloud_parsedate(track.get('created_at', None)),
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

        feed_url, feed_content, last_mod_up, last_mod_utc, etag, content_type, \
        length = get_url(url)

        return length, content_type, os.path.basename(os.path.dirname(url))


    @staticmethod
    def soundcloud_parsedate(s):
        """Parse a string into a unix timestamp

        Only strings provided by Soundcloud's API are
        parsed with this function (2009/11/03 13:37:00).
        """
        m = re.match(r'(\d{4})/(\d{2})/(\d{2}) (\d{2}):(\d{2}):(\d{2})', s)
        return time.mktime([int(x) for x in m.groups()]+[0, 0, -1])


class SoundcloudFeed(Feed):
    URL_REGEX = re.compile('http://([a-z]+\.)?soundcloud\.com/([^/]+)$', re.I)

    @classmethod
    def handles_url(cls, url):
        return bool(cls.URL_REGEX.match(url))


    def __init__(self, feed_url, content):
        self.strip_html = kwargs.get('strip_html', False)
        m = self.__class__.URL_REGEX.match(feed_url)
        subdomain, self.username = m.groups()
        self.sc_user = SoundcloudUser(self.username)

        super(SoundcloudFeed, self).__init__(feed_url)


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

    def get_episode_objects(self):
        tracks = self.sc_user.get_tracks('tracks')
        make_episode = lambda t: SoundcloudEpisode(t, self.get_author())
        return map(make_episode, tracks)



class SoundcloudFavFeed(SoundcloudFeed):
    URL_REGEX = re.compile('http://([a-z]+\.)?soundcloud\.com/([^/]+)/favorites', re.I)


    def __init__(self, *args, **kwargs):
        super(SoundcloudFavFeed,self).__init__(*args, **kwargs)


    @classmethod
    def handles_url(cls, url):
        return bool(cls.URL_REGEX.match(url))


    def get_title(self):
        return '%s\'s favorites on Soundcloud' % self.username

    def get_link(self):
        return 'http://soundcloud.com/%s/favorites' % self.username

    def get_description(self):
        return 'Tracks favorited by %s on Soundcloud.' % self.username



class SoundcloudEpisode(Episode):


    def __init__(self, track, author):
        self.entry = track
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


    def list_files(self):
        url = self.entry.get('url', None)
        mimetype = get_mimetype(self.entry.get('mimetype', None), url)
        filesize = self.entry.get('length', None)

        yield (url, mimetype, filesize)


    def get_timestamp(self):
        try:
            return int(self.entry.get('pubDate', None))
        except:
            return None
