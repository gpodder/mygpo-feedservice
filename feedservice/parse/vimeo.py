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

from feedservice.parse import FetchFeedException
from feedservice.parse.feed import Feedparser, FeedparserEpisodeParser
from feedservice.utils import fetch_url

VIMEO_RE = re.compile(r'http://vimeo\.com/user(\d+)/videos/rss')
VIMEOCOM_RE = re.compile(r'http://vimeo\.com/(\d+)$', re.IGNORECASE)
MOOGALOOP_RE = re.compile(r'http://vimeo\.com/moogaloop\.swf\?clip_id=(\d+)$', re.IGNORECASE)
SIGNATURE_RE = re.compile(r'"timestamp":(\d+),"signature":"([^"]+)"')


class VimeoError(FetchFeedException): pass


class VimeoParser(Feedparser):

    @classmethod
    def handles_url(cls, url):
        return bool(VIMEO_RE.match(url))


    def __init__(self, url, resp, text_processor=None):
        super(VimeoParser, self).__init__(url, resp,
                text_processor=text_processor)


    def get_description(self):
        return self.url


    def get_podcast_logo(self):
        return None


    def get_real_channel_url(self):
        result = VIMEOCOM_RE.match(url)
        if result is not None:
            return 'http://vimeo.com/%s/videos/rss' % result.group(1)

        return url


    def get_podcast_types(self):
        return ["video"]


    def get_episodes(self):
        parser = [VimeoEpisodeParser(e, text_processor=self.text_processor)
            for e in self.feed.entries]
        return [p.get_episode() for p in parser]



class VimeoEpisodeParser(FeedparserEpisodeParser):

    def __init__(self, *args, **kwargs):
        super(VimeoEpisodeParser, self).__init__(*args, **kwargs)


    def list_files(self):
        for link in getattr(self.entry, 'links', []):
            if not hasattr(link, 'href'):
                continue

            url = link['href']
            dl_url = self.get_real_download_url(url)

            if is_video_link(url):
                yield ([dl_url], 'application/x-vimeo', None)



    def get_real_download_url(self, url, preferred_fmt_id=None):
        quality = 'sd'
        codecs = 'H264,VP8,VP6'

        video_id = get_vimeo_id(url)

        if video_id is None:
            return url

        web_url = 'http://vimeo.com/%s' % video_id
        web_data = fetch_url(web_url).read()
        sig_pair = SIGNATURE_RE.search(web_data)

        if sig_pair is None:
            raise VimeoError('Cannot get signature pair from Vimeo')

        timestamp, signature = sig_pair.groups()
        params = '&'.join('%s=%s' % i for i in [
            ('clip_id', video_id),
            ('sig', signature),
            ('time', timestamp),
            ('quality', quality),
            ('codecs', codecs),
            ('type', 'moogaloop_local'),
            ('embed_location', ''),
        ])
        player_url = 'http://player.vimeo.com/play_redirect?%s' % params
        return player_url


def is_video_link(url):
    return (get_vimeo_id(url) is not None)


def get_vimeo_id(url):
    result = MOOGALOOP_RE.match(url)
    if result is not None:
        return result.group(1)

    result = VIMEOCOM_RE.match(url)
    if result is not None:
        return result.group(1)

    return None
