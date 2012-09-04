#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import logging

from feedservice.parse.models import Feed
from feedservice import urlstore
from feedservice.parse import feed, youtube, soundcloud, fm4


logger = logging.getLogger(__name__)

class UnchangedException(Exception):
    pass


PARSER_CLASSES = (
        youtube.YoutubeParser,
        soundcloud.SoundcloudParser,
        soundcloud.SoundcloudFavParser,
        fm4.FM4OnDemandPlaylistParser,
        feed.Feedparser, # fallback, has to be the last entry
    )


def parse_feeds(feed_urls, mod_since_utc=None,
        process_text=lambda _: _, cache=None, **kwargs):
    """ Parses the specified feeds and returns their JSON representations

    RSS-Redirects are followed automatically by including both feeds in the
    result. """

    visited_urls = set()
    result = []

    for url in feed_urls:

        feed = parse_feed(url)#, mod_since_utc, base_url, process_text, **kwargs)

        if not feed:
            continue

        visited  = feed.urls#['urls']
        new_loc  = feed.new_location

        # we follow RSS-redirects automatically
        if new_loc and new_loc not in (list(visited_urls) + feed_urls):
            feed_urls.append(new_loc)

        visited_urls.add(url)

        result.append(feed)

    return result


def get_parser_cls(url):
    feed_cls = None

    for cls in PARSER_CLASSES:
        if cls.handles_url(url):
            return cls

    raise ValueError('no feed can handle %s' % url)


def parse_feed(feed_url, mod_since_utc=None, base_url=None,
        process_text=lambda _: _, cache=None, **kwargs):
    """ Parses a feed and returns its JSON object

    mod_since_utc: feeds that have not changed since this timestamp are ignored
    base_url: base url of the service -- used for pubsub subscriptions
    process_text: function to process text (eg remove HTML tags)
    cache: cache or None to disable caching
    """

    parser_cls = get_parser_cls(feed_url)

    try:
        resp = urlstore.fetch_url(feed_url)

        #if not res.changed_since(mod_since_utc):
        #    raise UnchangedException

    except Exception as e:

        raise

        # create a dummy feed to hold the error message and the feed URL
        feed = Feed(feed_url, None)
        msg = 'could not fetch feed %(feed_url)s: %(msg)s' % \
            dict(feed_url=feed_url, msg=str(e))
        feed.add_error('fetch-feed', msg)
        logger.warning(msg)
        return feed.to_dict(process_text, **kwargs)

    except UnchangedException as e:
        return None

    parser = parser_cls(feed_url, resp)

    return parser.get_feed()
