#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import logging
import urllib.error
import http.client
import socket

from feedservice.parse.models import Feed, ParserException
from feedservice.utils import fetch_url, NotModified


logger = logging.getLogger(__name__)


class FetchFeedException(Exception):
    """ raised when there's an error while fetching the podcast feed """


def get_parser_classes():
    from feedservice.parse import feed, youtube, soundcloud, fm4, vimeo
    return (
        youtube.YoutubeParser,
        vimeo.VimeoParser,
        soundcloud.SoundcloudParser,
        soundcloud.SoundcloudFavParser,
        fm4.FM4OnDemandPlaylistParser,
        feed.Feedparser,  # fallback, has to be the last entry
    )


PARSER_CLASSES = get_parser_classes()


def parse_feeds(feed_urls, mod_since_utc=None, text_processor=None):
    """ Parses the specified feeds and returns their JSON representations

    RSS-Redirects are followed automatically by including both feeds in the
    result. """

    visited_urls = set()
    result = []

    for url in feed_urls:

        try:
            feed = parse_feed(url, text_processor, mod_since_utc)

        except FetchFeedException as ffe:
            feed = Feed()
            feed.urls = [url]
            feed.new_location = None
            feed.add_error('fetch-feed', str(ffe))

        if not feed:
            continue

        visited = feed.urls
        new_loc = feed.new_location

        # we follow RSS-redirects automatically
        if new_loc and new_loc not in (list(visited_urls) + visited):
            feed_urls.append(new_loc)

        visited_urls.add(url)

        result.append(feed)

    return result


def get_parser_cls(url):
    for cls in PARSER_CLASSES:
        if cls.handles_url(url):
            return cls

    raise ValueError('no feed can handle %s' % url)


def parse_feed(feed_url, text_processor, mod_since_utc=None):
    """ Parses a feed and returns its JSON object

    mod_since_utc: feeds that have not changed since this timestamp are ignored
    text_processor: class to pre-process text contents
    """

    parser_cls = get_parser_cls(feed_url)

    try:
        resp = fetch_url(feed_url, mod_since_utc)
        parser = parser_cls(feed_url, resp, text_processor=text_processor)
        return parser.get_feed()

    except NotModified:
        return None

    except (http.client.HTTPException, urllib.error.URLError, urllib.error.HTTPError,
            ValueError, socket.error, ParserException) as ex:
        raise FetchFeedException(ex) from ex
