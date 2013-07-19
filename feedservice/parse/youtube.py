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

from urlparse import parse_qs

from feedservice.parse.feed import Feedparser, FeedparserEpisodeParser
from feedservice.parse.models import ParserException
from feedservice.urlstore import fetch_url
from feedservice.utils import remove_html_tags

import logging
logger = logging.getLogger(__name__)


# http://en.wikipedia.org/wiki/YouTube#Quality_and_codecs
# format id, (preferred ids, path(?), description) # video bitrate, audio bitrate
formats = [
    # WebM VP8 video, Vorbis audio
    # Fallback to an MP4 version of same quality.
    # Try 34 (FLV 360p H.264 AAC) if 18 (MP4 360p) fails.
    # Fallback to 6 or 5 (FLV Sorenson H.263 MP3) if all fails.
    (46, ([46, 37, 45, 22, 44, 35, 43, 18, 6, 34, 5], '45/1280x720/99/0/0', 'WebM 1080p (1920x1080)')), # N/A, 192 kbps
    (45, ([45, 22, 44, 35, 43, 18, 6, 34, 5], '45/1280x720/99/0/0', 'WebM 720p (1280x720)')), # 2.0 Mbps, 192 kbps
    (44, ([44, 35, 43, 18, 6, 34, 5], '44/854x480/99/0/0', 'WebM 480p (854x480)')), # 1.0 Mbps, 128 kbps
    (43, ([43, 18, 6, 34, 5], '43/640x360/99/0/0', 'WebM 360p (640x360)')), # 0.5 Mbps, 128 kbps

    # MP4 H.264 video, AAC audio
    # Try 35 (FLV 480p H.264 AAC) between 720p and 360p because there's no MP4 480p.
    # Try 34 (FLV 360p H.264 AAC) if 18 (MP4 360p) fails.
    # Fallback to 6 or 5 (FLV Sorenson H.263 MP3) if all fails.
    (38, ([38, 37, 22, 35, 18, 34, 6, 5], '38/1920x1080/9/0/115', 'MP4 4K 3072p (4096x3072)')), # 5.0 - 3.5 Mbps, 192 kbps
    (37, ([37, 22, 35, 18, 34, 6, 5], '37/1920x1080/9/0/115', 'MP4 HD 1080p (1920x1080)')), # 4.3 - 3.0 Mbps, 192 kbps
    (22, ([22, 35, 18, 34, 6, 5], '22/1280x720/9/0/115', 'MP4 HD 720p (1280x720)')), # 2.9 - 2.0 Mbps, 192 kbps
    (18, ([18, 34, 6, 5], '18/640x360/9/0/115', 'MP4 360p (640x360)')), # 0.5 Mbps, 96 kbps

    # FLV H.264 video, AAC audio
    # Does not check for 360p MP4.
    # Fallback to 6 or 5 (FLV Sorenson H.263 MP3) if all fails.
    (35, ([35, 34, 6, 5], '35/854x480/9/0/115', 'FLV 480p (854x480)')), # 1 - 0.80 Mbps, 128 kbps
    (34, ([34, 6, 5], '34/640x360/9/0/115', 'FLV 360p (640x360)')), # 0.50 Mbps, 128 kbps

    # FLV Sorenson H.263 video, MP3 audio
    (6, ([6, 5], '5/480x270/7/0/0', 'FLV 270p (480x270)')), # 0.80 Mbps, 64 kbps
    (5, ([5], '5/320x240/7/0/0', 'FLV 240p (320x240)')), # 0.25 Mbps, 64 kbps
]
formats_dict = dict(formats)


class YouTubeError(ParserException):
    pass


class YoutubeParser(Feedparser):


    re_youtube_feeds = [
        re.compile(r'^https?://gdata.youtube.com/feeds/base/users/(?P<username>[^/]+)/uploads'),
        re.compile(r'^https?://(www\.)?youtube\.com/rss/user/(?P<username>[^/]+)/videos\.rss'),
        ]

    re_cover = re.compile('https?://www\.youtube\.com/rss/user/([^/]+)/videos\.rss', \
                re.IGNORECASE)


    @classmethod
    def handles_url(cls, url):
        return any(regex.match(url) for regex in cls.re_youtube_feeds)



    def __init__(self, url, resp, text_processor=None):
        super(YoutubeParser, self).__init__(url, resp,
                text_processor=text_processor)

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
        data = fetch_url(api_url).read()
        match = re.search('<media:thumbnail url=[\'"]([^\'"]+)[\'"]/>', data)
        if match is not None:
            return match.group(1)


    def get_real_channel_url(self):
        r = re.compile('http://(?:[a-z]+\.)?youtube\.com/user/([a-z0-9]+)', re.IGNORECASE)
        m = r.match(self.url)

        if m is not None:
            next = 'http://www.youtube.com/rss/user/'+ m.group(1) +'/videos.rss'
            logger.debug('YouTube link resolved: %s => %s', self.url, next)
            return next

        r = re.compile('http://(?:[a-z]+\.)?youtube\.com/profile?user=([a-z0-9]+)', re.IGNORECASE)
        m = r.match(self.url)

        if m is not None:
            next = 'http://www.youtube.com/rss/user/'+ m.group(1) +'/videos.rss'
            logger.debug('YouTube link resolved: %s => %s', self.url, next)
            return next

        return self.url


    def get_podcast_types(self):
        return ["video"]


    def get_episodes(self):
        parser = [YoutubeEpisodeParser(e, text_processor=self.text_processor)
            for e in self.feed.entries]
        return [p.get_episode() for p in parser]


class YoutubeEpisodeParser(FeedparserEpisodeParser):

    def __init__(self, *args, **kwargs):
        super(YoutubeEpisodeParser, self).__init__(*args, **kwargs)


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

    def is_youtube_guid(guid):
        return guid.startswith('tag:youtube.com,2008:video:')


    def get_youtube_id(self, url):
        r = re.compile('http[s]?://(?:[a-z]+\.)?youtube\.com/v/(.*)\.swf', re.IGNORECASE).match(url)
        if r is not None:
            return r.group(1)

        r = re.compile('http[s]?://(?:[a-z]+\.)?youtube\.com/watch\?v=([^&]*)', re.IGNORECASE).match(url)
        if r is not None:
            return r.group(1)

        r = re.compile('http[s]?://(?:[a-z]+\.)?youtube\.com/v/(.*)[?]', re.IGNORECASE).match(url)
        if r is not None:
            return r.group(1)

        return None


    def get_fmt_ids(self, youtube_config):
        fmt_ids = youtube_config.preferred_fmt_ids
        if not fmt_ids:
            format = formats_dict.get(youtube_config.preferred_fmt_id)
            if format is None:
                fmt_ids = []
            else:
                fmt_ids, path, description = format

        return fmt_ids


    def get_real_download_url(self, url, preferred_fmt_ids=None):
        if not preferred_fmt_ids:
            preferred_fmt_ids, _, _ = formats_dict[22] # MP4 720p

        vid = self.get_youtube_id(url)
        if vid is not None:
            page = None
            url = 'http://www.youtube.com/get_video_info?&el=detailpage&video_id=' + vid

            while page is None:
                req = fetch_url(url)
                if 'location' in req.msg:
                    url = req.msg['location']
                else:
                    page = req.read()

            # Try to find the best video format available for this video
            # (http://forum.videohelp.com/topic336882-1800.html#1912972)
            def find_urls(page):
                r4 = re.search('.*&url_encoded_fmt_stream_map=([^&]+)&.*', page)
                if r4 is not None:
                    fmt_url_map = urllib.unquote(r4.group(1))
                    for fmt_url_encoded in fmt_url_map.split(','):
                        video_info = parse_qs(fmt_url_encoded)
                        yield int(video_info['itag'][0]), video_info['url'][0] + "&signature=" + video_info['sig'][0]
                else:
                    error_info = parse_qs(page)
                    error_message = remove_html_tags(error_info['reason'][0])
                    raise YouTubeError('Cannot download video: %s' % error_message)

            fmt_id_url_map = sorted(find_urls(page), reverse=True)

            if not fmt_id_url_map:
                raise YouTubeError('fmt_url_map not found for video ID "%s"' % vid)

            # Default to the highest fmt_id if we don't find a match below
            _, url = fmt_id_url_map[0]

            formats_available = set(fmt_id for fmt_id, url in fmt_id_url_map)
            fmt_id_url_map = dict(fmt_id_url_map)

            for id in preferred_fmt_ids:
                id = int(id)
                if id in formats_available:
                    format = formats_dict.get(id)
                    if format is not None:
                        _, _, description = format
                    else:
                        description = 'Unknown'

                    logger.info('Found YouTube format: %s (fmt_id=%d)',
                            description, id)
                    url = fmt_id_url_map[id]
                    break

        return url



    def get_real_cover(self):
        r = re.compile('http://www\.youtube\.com/rss/user/([^/]+)/videos\.rss', \
                re.IGNORECASE)
        m = r.match(self.url)

        if m is not None:
            username = m.group(1)
            api_url = 'http://gdata.youtube.com/feeds/api/users/%s?v=2' % username
            data = fetch_url(api_url)
            match = re.search('<media:thumbnail url=[\'"]([^\'"]+)[\'"]/>', data)
            if match is not None:
                logger.debug('YouTube userpic for %s is: %s', self.url, match.group(1))
                return match.group(1)

        return None
