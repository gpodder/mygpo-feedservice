#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# This file is part of my.gpodder.org.
#
# my.gpodder.org is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# my.gpodder.org is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public
# License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with my.gpodder.org. If not, see <http://www.gnu.org/licenses/>.
#

import re
import urllib

from feedservice.parse.feed import FeedparserFeed, FeedparserEpisode
from feedservice.urlstore import get_url

# See http://en.wikipedia.org/wiki/YouTube#Quality_and_codecs
# Currently missing: the WebM 480p and 720 formats; 3GP profile
supported_formats = [
    (37, '37/1920x1080/9/0/115', '1920x1080 (HD)'),
    (22, '22/1280x720/9/0/115', '1280x720 (HD)'),
    (35, '35/854x480/9/0/115', '854x480'),
    (34, '34/640x360/9/0/115', '640x360'),
    (18, '18/640x360/9/0/115', '640x360 (iPod)'),
    (18, '18/480x360/9/0/115', '480x360 (iPod)'),
    (5, '5/320x240/7/0/0', '320x240 (FLV)'),
]


class YouTubeError(Exception):
    pass


class YoutubeFeed(FeedparserFeed):


    re_youtube_feeds = [
        re.compile(r'^https?://gdata.youtube.com/feeds/base/users/(?P<username>[^/]+)/uploads'),
        re.compile(r'^https?://(www\.)?youtube\.com/rss/user/(?P<username>[^/]+)/videos\.rss'),
        ]

    re_cover = re.compile('http://www\.youtube\.com/rss/user/([^/]+)/videos\.rss', \
                re.IGNORECASE)


    @classmethod
    def handles_url(cls, url):
        return any(regex.match(url) for regex in cls.re_youtube_feeds)



    def __init__(self, url, url_obj):
        super(YoutubeFeed, self).__init__(url, url_obj)
        for reg in self.re_youtube_feeds:
            m = reg.match(url)
            if m:
                self.username = m.group('username')
                return


    def get_description(self):
        return 'Youtube uploads by %s' % self.username


    def get_podcast_logo(self):
        url = self.feed.feed.get('link', False)
        m = self.re_cover.match(url)

        if m is None:
            return None

        username = m.group(1)
        api_url = 'http://gdata.youtube.com/feeds/api/users/%s?v=2' % username
        data = get_url(api_url)[1]
        match = re.search('<media:thumbnail url=[\'"]([^\'"]+)[\'"]/>', data)
        if match is not None:
            log('YouTube userpic for %s is: %s', url, match.group(1))
            return match.group(1)


    def get_real_channel_url(self):
        r = re.compile('http://(?:[a-z]+\.)?youtube\.com/user/([a-z0-9]+)', re.IGNORECASE)
        m = r.match(self.url)

        if m is not None:
            next = 'http://www.youtube.com/rss/user/'+ m.group(1) +'/videos.rss'
            log('YouTube link resolved: %s => %s', self.url, next)
            return next

        r = re.compile('http://(?:[a-z]+\.)?youtube\.com/profile?user=([a-z0-9]+)', re.IGNORECASE)
        m = r.match(self.url)

        if m is not None:
            next = 'http://www.youtube.com/rss/user/'+ m.group(1) +'/videos.rss'
            log('YouTube link resolved: %s => %s', self.url, next)
            return next

        return self.url


    def get_podcast_types(self):
        return ["video"]


class YoutubeEpisode(FeedparserEpisode):

    def list_files(self):
        for link in getattr(self.entry, 'links', []):
            if not hasattr(link, 'href'):
                continue

            url = link['href']
            dl_url = self.get_real_download_url(url)

            if self.is_video_link(url):
                yield ([dl_url], 'application/x-youtube', None)


    def is_video_link(self, url):
        return (self.get_youtube_id(url) is not None)


    def get_youtube_id(self, url):
        r = re.compile('http://(?:[a-z]+\.)?youtube\.com/v/(.*)\.swf', re.IGNORECASE).match(url)
        if r is not None:
            return r.group(1)

        r = re.compile('http://(?:[a-z]+\.)?youtube\.com/watch\?v=([^&]*)', re.IGNORECASE).match(url)
        if r is not None:
            return r.group(1)

        return None


    def get_real_download_url(self, url, preferred_fmt_id=18):
        vid = self.get_youtube_id(url)
        if vid is not None:
            url = 'http://www.youtube.com/watch?v=' + vid

            page = get_url(url)[1]

            # Try to find the best video format available for this video
            # (http://forum.videohelp.com/topic336882-1800.html#1912972)
            def find_urls(page):
                r4 = re.search('.*"url_encoded_fmt_stream_map"\:\s+"([^"]+)".*', page)
                if r4 is not None:
                    fmt_url_map = r4.group(1)
                    for fmt_url_encoded in fmt_url_map.split(','):
                        video_info = dict(map(urllib.unquote, x.split('=', 1))
                                for x in fmt_url_encoded.split('\\u0026'))
                        yield int(video_info['itag']), video_info['url']

            fmt_id_url_map = sorted(find_urls(page), reverse=True)
            # Default to the highest fmt_id if we don't find a match below
            if fmt_id_url_map:
                default_fmt_id, default_url = fmt_id_url_map[0]
            else:
                raise YouTubeError('fmt_url_map not found for video ID "%s"' % vid)

            formats_available = set(fmt_id for fmt_id, url in fmt_id_url_map)
            fmt_id_url_map = dict(fmt_id_url_map)

            # use fmt_id 18 (seems to be always available)
            fmt_id = 18

            # This will be set to True if the search below has already "seen"
            # our preferred format, but has not yet found a suitable available
            # format for the given video.
            seen_preferred = False

            for id, wanted, description in supported_formats:
                # If we see our preferred format, accept formats below
                if id == preferred_fmt_id:
                    seen_preferred = True

                # If the format is available and preferred (or lower),
                # use the given format for our fmt_id
                if id in formats_available and seen_preferred:
                    fmt_id = id
                    break

            url = fmt_id_url_map.get(fmt_id, None)
            if url is None:
                url = default_url

        return urllib.unquote(url)
