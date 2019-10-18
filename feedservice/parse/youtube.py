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
import json

from urllib.parse import parse_qs, unquote, urlparse
import urllib.error

from django.conf import settings

from feedservice.parse.feed import Feedparser, FeedparserEpisodeParser
from feedservice.parse.models import ParserException
from feedservice.utils import remove_html_tags, fetch_url, requests

import feedservice.utils as util  # for gpodder.youtube compat

import logging
logger = logging.getLogger(__name__)


# todo: actually parse the feed and look for the <link rel=canonical"> tag
RE_CANONICAL = 'rel="canonical" href="([^"]+)'

RE_CHANNEL = re.compile('channel/([_a-zA-Z0-9-]+)')
RE_PLAYLIST = re.compile(r'playlist\?list=([_a-zA-Z0-9-]+)')

CHANNEL_FEED = 'https://www.youtube.com/feeds/videos.xml?channel_id={fid}'
PLAYLIST_FEED = 'https://www.youtube.com/feeds/videos.xml?playlist_id={fid}'

FEED_TYPES = {
    RE_CHANNEL: CHANNEL_FEED,
    RE_PLAYLIST: PLAYLIST_FEED,
}

# old URLs that don't work anymore
OLD_USER_URLS = [
    r'http[s]?://(?:[a-z]+\.)?youtube.com/rss/user/([A-Za-z0-9-]+)/videos\.rss',
    r'http[s]?://(?:[a-z]+\.)?youtube\.com/profile?user=([A-Za-z0-9-]+)',
    r'http[s]?://gdata.youtube.com/feeds/users/([^/]+)/uploads',
    r'http[s]?://gdata.youtube.com/feeds/base/users/([^/]+)/uploads',
]

NEW_USER_URLS = 'https://www.youtube.com/user/{username}'

OLD_ID_URLS = [
    r'http[s]?://gdata.youtube.com/feeds/api/users/([_a-zA-Z0-9-]+)/uploads',
]


class YouTubeError(ParserException):
    pass


class YoutubeParser(Feedparser):

    @classmethod
    def handles_url(cls, url):
        result = urlparse(url)
        if result.netloc == 'youtube.com':
            return True

        if result.netloc.endswith('.youtube.com'):
            return True

        return False

    def __init__(self, url, resp, text_processor=None):
        self._orig_url = url
        self._current_url = self.get_current_url(self._orig_url)
        self._new_url = self.parse_video_page(self._current_url)
        super().__init__(self._new_url, resp, text_processor=text_processor)

    def get_current_url(self, url):
        # try to match for old URLs that already contain the video ID
        for oldurl in OLD_ID_URLS:
            m = re.match(oldurl, url)
            if m:
                url = CHANNEL_FEED.format(fid=m.group(1))
                break

        # try to match for old URLs that contain a username
        for oldurl in OLD_USER_URLS:
            m = re.match(oldurl, url)
            if m:
                url = NEW_USER_URLS.format(username=m.group(1))
                break

        return url

    def parse_video_page(self, url):
        # by now we should have a new (working) URL, let's fetch it
        r = requests.get(url)
        m = re.search(RE_CANONICAL, r.text)
        if not m:
            # URL didn't contain a canonical link, so we can't work with it
            return url
        canonical_url = m.group(1)

        # see what kind of canonical link we found
        for regex, feed in FEED_TYPES.items():
            m = regex.search(canonical_url)
            if m:
                feed_url = feed.format(fid=m.group(1))
                return feed_url

    def get_urls(self):
        return [self._orig_url, self._current_url, self._new_url]

    def get_logo_url(self):
        return None

    def get_podcast_types(self):
        return ["video"]

    def get_episodes(self):
        parser = [YoutubeEpisodeParser(e, text_processor=self.text_processor)
                  for e in self.feed.entries]
        return [p.get_episode() for p in parser]


class YoutubeEpisodeParser(FeedparserEpisodeParser):

    def list_files(self):
        for link in getattr(self.entry, 'links', []):
            if not hasattr(link, 'href'):
                continue

            url = link['href']
            try:
                dl_url = get_real_download_url(url)
            except YouTubeError:
                dl_url = None

            if is_video_link(url):
                if dl_url is not None:
                  yield ([dl_url], 'application/x-youtube', None)
                yield ([url], 'application/x-youtube', None)


# http://en.wikipedia.org/wiki/YouTube#Quality_and_codecs
# format id, (preferred ids, path(?), description) # video bitrate, audio bitrate
formats = [
    # WebM VP8 video, Vorbis audio
    # Fallback to an MP4 version of same quality.
    # Try 34 (FLV 360p H.264 AAC) if 18 (MP4 360p) fails.
    # Fallback to 6 or 5 (FLV Sorenson H.263 MP3) if all fails.
    (46, ([46, 37, 45, 22, 44, 35, 43, 18, 6, 34, 5], '45/1280x720/99/0/0', 'WebM 1080p (1920x1080)')), # N/A,      192 kbps
    (45, ([45, 22, 44, 35, 43, 18, 6, 34, 5],         '45/1280x720/99/0/0', 'WebM 720p (1280x720)')),   # 2.0 Mbps, 192 kbps
    (44, ([44, 35, 43, 18, 6, 34, 5],                 '44/854x480/99/0/0',  'WebM 480p (854x480)')),    # 1.0 Mbps, 128 kbps
    (43, ([43, 18, 6, 34, 5],                         '43/640x360/99/0/0',  'WebM 360p (640x360)')),    # 0.5 Mbps, 128 kbps

    # MP4 H.264 video, AAC audio
    # Try 35 (FLV 480p H.264 AAC) between 720p and 360p because there's no MP4 480p.
    # Try 34 (FLV 360p H.264 AAC) if 18 (MP4 360p) fails.
    # Fallback to 6 or 5 (FLV Sorenson H.263 MP3) if all fails.
    (38, ([38, 37, 22, 35, 18, 34, 6, 5], '38/1920x1080/9/0/115', 'MP4 4K 3072p (4096x3072)')), # 5.0 - 3.5 Mbps, 192 kbps
    (37, ([37, 22, 35, 18, 34, 6, 5],     '37/1920x1080/9/0/115', 'MP4 HD 1080p (1920x1080)')), # 4.3 - 3.0 Mbps, 192 kbps
    (22, ([22, 35, 18, 34, 6, 5],         '22/1280x720/9/0/115',  'MP4 HD 720p (1280x720)')),   # 2.9 - 2.0 Mbps, 192 kbps
    (18, ([18, 34, 6, 5],                 '18/640x360/9/0/115',   'MP4 360p (640x360)')),       #       0.5 Mbps,  96 kbps

    # FLV H.264 video, AAC audio
    # Does not check for 360p MP4.
    # Fallback to 6 or 5 (FLV Sorenson H.263 MP3) if all fails.
    (35, ([35, 34, 6, 5], '35/854x480/9/0/115',   'FLV 480p (854x480)')), # 1 - 0.80 Mbps, 128 kbps
    (34, ([34, 6, 5],     '34/640x360/9/0/115',   'FLV 360p (640x360)')), #     0.50 Mbps, 128 kbps

    # FLV Sorenson H.263 video, MP3 audio
    (6, ([6, 5],         '5/480x270/7/0/0',      'FLV 270p (480x270)')), #     0.80 Mbps,  64 kbps
    (5, ([5],            '5/320x240/7/0/0',      'FLV 240p (320x240)')), #     0.25 Mbps,  64 kbps
]
formats_dict = dict(formats)

V3_API_ENDPOINT = 'https://www.googleapis.com/youtube/v3'
CHANNEL_VIDEOS_XML = 'https://www.youtube.com/feeds/videos.xml'


def get_fmt_ids(youtube_config):
    fmt_ids = youtube_config.preferred_fmt_ids
    if not fmt_ids:
        format = formats_dict.get(youtube_config.preferred_fmt_id)
        if format is None:
            fmt_ids = []
        else:
            fmt_ids, path, description = format

    return fmt_ids


# TODO: currently not working, needs investigation
def get_real_download_url(url, preferred_fmt_ids=None):
    if not preferred_fmt_ids:
        preferred_fmt_ids, _, _ = formats_dict[22]  # MP4 720p

    vid = get_youtube_id(url)
    if vid is not None:
        page = None
        url = 'https://www.youtube.com/get_video_info?&el=detailpage&video_id=' + vid

        while page is None:
            req = util.http_request(url, method='GET')
            if 'location' in req.msg:
                url = req.msg['location']
            else:
                page = req.read()

        page = page.decode()
        # Try to find the best video format available for this video
        # (http://forum.videohelp.com/topic336882-1800.html#1912972)

        def find_urls(page):
            r4 = re.search('url_encoded_fmt_stream_map=([^&]+)', page)
            if r4 is not None:
                fmt_url_map = urllib.parse.unquote(r4.group(1))
                for fmt_url_encoded in fmt_url_map.split(','):
                    video_info = parse_qs(fmt_url_encoded)
                    yield int(video_info['itag'][0]), video_info['url'][0]
            else:
                error_info = parse_qs(page)
                if 'reason' in error_info:
                    error_message = util.remove_html_tags(error_info['reason'][0])
                elif 'player_response' in error_info:
                    player_response = json.loads(error_info['player_response'][0])
                    if 'reason' in player_response['playabilityStatus']:
                        error_message = util.remove_html_tags(player_response['playabilityStatus']['reason'])
                    elif 'live_playback' in error_info:
                        error_message = 'live stream'
                    elif 'post_live_playback' in error_info:
                        error_message = 'post live stream'
                    else:
                        error_message = ''
                else:
                    error_message = ''
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


def get_youtube_id(url):
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

def is_video_link(url):
    return (get_youtube_id(url) is not None)

def is_youtube_guid(guid):
    return guid.startswith('tag:youtube.com,2008:video:')
