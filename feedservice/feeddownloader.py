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

USER_AGENT = 'mygpo crawler (+http://my.gpodder.org)'


import os
import sys
import datetime
import hashlib
import urllib2
import base64
#import socket

from google.appengine.api import images


import feedcore
from utils import parse_time
import youtube
from mimetype import get_mimetype, check_mimetype, get_podcast_types

#socket.setdefaulttimeout(10)
fetcher = feedcore.Fetcher(USER_AGENT)


def get_episode_files(entry):
    """Get the download / episode URL of a feedparser entry"""

    urls = {}
    enclosures = getattr(entry, 'enclosures', [])
    for enclosure in enclosures:
        if 'href' in enclosure:
            mimetype = get_mimetype(enclosure.get('type', ''), enclosure['href'])
            if check_mimetype(mimetype):
                try:
                    filesize = int(enclosure['length'])
                except ValueError:
                    filesize = None
                urls[enclosure['href']] = (mimetype, filesize)

    media_content = getattr(entry, 'media_content', [])
    for media in media_content:
        if 'url' in media:
            mimetype = get_mimetype(media.get('type', ''), media['url'])
            if check_mimetype(mimetype):
                urls[media['url']] = (mimetype, None)

    links = getattr(entry, 'links', [])
    for link in links:
        if not hasattr(link, 'href'):
            continue

        if youtube.is_video_link(link['href']):
            urls[link['href']] = ('application/x-youtube', None)

        # XXX: Implement link detection as in gPodder

    return urls

def get_episode_summary(entry):
    for key in ('summary', 'subtitle', 'link'):
        value = entry.get(key, None)
        if value:
            return value

    return ''

def get_duration(entry):
    str = entry.get('itunes_duration', '')

    try:
        return parse_time(str)
    except ValueError:
        return 0

def get_feed_tags(feed):
    tags = []

    for tag in feed.get('tags', []):
        if tag['term']:
            tags.extend([t for t in tag['term'].split(',') if t])

        if tag['label']:
            tags.append(tag['label'])

    return set(tags)


def update_feed_tags(podcast, tags):
    src = 'feed'

    #delete all tags not found in the feed anymore
    #PodcastTag.objects.filter(podcast=podcast, source=src).exclude(tag__in=tags).delete()

    #create new found tags
    #for tag in tags:
    #    if not PodcastTag.objects.filter(podcast=podcast, source=src, tag=tag).exists():
    #        PodcastTag.objects.get_or_create(podcast=podcast, source=src, tag=tag)


def get_episode_metadata(entry, files):
    d = {
        'title': entry.get('title', entry.get('link', '')),
        'description': get_episode_summary(entry),
        'link': entry.get('link', ''),
        'timestamp': None,
        'author': entry.get('author', entry.get('itunes_author', '')),
        'duration': get_duration(entry),
        'language': entry.get('language', ''),
        'files': [ dict(url=k, mimetype=v[0], filesize=v[1]) for (k, v) in files.items()],
        'url': files.keys()[0],
        'filesize': files.values()[0][1],
        'mimetype': files.values()[0][0],
    }
    try:
        d['timestamp'] = datetime.datetime(*(entry.updated_parsed)[:6]).strftime('%Y-%m-%dT%H:%M:%S')
    except:
        d['timestamp'] = None

    return d


def parse_feed(feed_url, inline_logo, scale_to):
    try:
        fetcher.fetch(feed_url)

    except (feedcore.Offline, feedcore.InvalidFeed, feedcore.WifiLogin, feedcore.AuthenticationRequired):
        pass

    except feedcore.NewLocation, location:
        return parse_feed(location.data)

    except feedcore.UpdatedFeed, updated:
        feed = updated.data
        podcast = dict()
        podcast['title'] = feed.feed.get('title', '')
        podcast['link']  = feed.feed.get('link', '')
        podcast['description'] = feed.feed.get('subtitle', '')
        podcast['author'] = feed.feed.get('author', feed.feed.get('itunes_author', ''))
        podcast['language'] = feed.feed.get('language', '')

        logo_url = get_podcast_logo(feed)
        podcast['logo'] = logo_url
        if inline_logo and logo_url:
            podcast['logo_data'] = get_data_uri(logo_url, scale_to)

        #update_feed_tags(podcast, get_feed_tags(feed.feed))

        podcast['episodes'] = []
        for entry in feed.entries:
            urls = get_episode_files(entry)
            if not urls:
                continue

            e = get_episode_metadata(entry, urls)
            podcast['episodes'].append(e)

        podcast['content_types'] = get_podcast_types(podcast)

    except Exception, e:
        print >>sys.stderr, 'Exception:', e

    return podcast


def get_podcast_logo(feed):
    cover_art = None
    image = feed.feed.get('image', None)
    if image is not None:
        for key in ('href', 'url'):
            cover_art = getattr(image, key, None)
            if cover_art:
                break

    yturl = youtube.get_real_cover(feed.feed.link)
    if yturl:
        cover_art = yturl

    return cover_art


def get_data_uri(url, size=None):
    content = urllib2.urlopen(url).read()

    if size:
        content = images.resize(content, size, size)

    mimetype = get_mimetype(None, url)
    encoded = base64.b64encode(content)
    return 'data:%s;base64,%s' % (mimetype, encoded)
