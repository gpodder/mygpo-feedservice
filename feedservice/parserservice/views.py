#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import urllib
import time
import email.utils
import logging
import cgi
from datetime import datetime


from django.http import HttpResponse
from django.shortcuts import render_to_response

from feedservice.parserservice.models import Feed
from feedservice import urlstore
import httputils
import youtube
import soundcloud
import fm4

try:
    import simplejson as json
except ImportError:
    import json


FEED_CLASSES = (
        youtube.YoutubeFeed,
        soundcloud.SoundcloudFeed,
        soundcloud.SoundcloudFavFeed,
        fm4.FM4OnDemandPlaylist,
        Feed,
    )


def parse(request):
    """ Parser Endpoint """

    urls = map(urllib.unquote, request.GET.getlist('url'))

    parse_args = dict(
        inline_logo = request.GET.get('inline_logo', default=0),
        scale_to    = request.GET.get('scale_logo',  default=0),
        logo_format = request.GET.get('logo_format', None),
        strip_html  = request.GET.get('strip_html',  default=0),
        use_cache   = request.GET.get('use_cache',   default=1),
    )

    mod_since_utc = request.META.get('HTTP_IF_MODIFIED_SINCE', None)
    accept = request.META.get('HTTP_ACCEPT', 'application/json')

    base_url = request.build_absolute_uri('/')

    if urls:
        podcasts = parse_feeds(urls, mod_since_utc, base_url, **parse_args)

        last_mod_utc = datetime.utcnow()
        response = send_response(podcasts, last_mod_utc, accept)

    else:
        response = HttpResponse()
        response.status_code = 400
        response.write('parameter url missing')

    return response


def send_response(podcasts, last_mod_utc, formats):

    format = httputils.select_matching_option(['text/html', 'application/json'], formats)

    if format in (None, 'application/json'): #serve json as default
        response = HttpResponse()
        content_type = 'application/json'
        response.write(json.dumps(podcasts, sort_keys=True, indent=None, separators=(',', ':')))
        response['Last-Modified'] = email.utils.formatdate(time.mktime(last_mod_utc.timetuple()))


    else:
        content_type = 'text/html'
        pretty_json = json.dumps(podcasts, sort_keys=True, indent=4)
        pretty_json = cgi.escape(pretty_json)
        response = render_to_response('pretty_response.html', {
                'response': pretty_json
                })

    response['Content-Type'] = content_type

    response['Vary'] = 'Accept, User-Agent, Accept-Encoding'
    return response


def parse_feeds(feed_urls, mod_since_utc, base_url, **kwargs):
    """
    Parses several feeds, specified by feed_urls and returns their JSON
    objects and the latest of their modification dates. RSS-Redirects are
    followed automatically by including both feeds in the result.
    """

    visited_urls = set()
    result = []

    for url in feed_urls:

        feed = parse_feed(url, mod_since_utc, base_url, **kwargs)

        if not feed:
            continue

        visited  = feed.get('urls', [])
        new_loc  = feed.get('new_location', None)

        # we follow RSS-redirects automatically
        if new_loc and new_loc not in (list(visited_urls) + feed_urls):
            feed_urls.append(new_loc)

        result.append(feed)

    return result


def parse_feed(feed_url, mod_since_utc, base_url, use_cache, **kwargs):
    """
    Parses a feed and returns its JSON object, a list of urls that refer to
    this feed, an outgoing redirect and the timestamp of the last modification
    of the feed
    """

    try:
        feed_url, feed_content, last_mod_up, last_mod_utc, etag, content_type, \
        length = urlstore.get_url(feed_url, use_cache)

    except Exception, e:
        raise
        # create a dummy feed to hold the error message and the feed URL
        feed = Feed()
        msg = 'could not fetch feed %(feed_url)s: %(msg)s' % \
            dict(feed_url=feed_url, msg=str(e))
        feed.add_error('fetch-feed', msg)
        logging.info(msg)
        feed.add_url(feed_url)
        raise
        return feed

    if last_mod_utc and mod_since_utc and last_mod_utc <= mod_since_utc:
        return None

    # chose the class to parse this feed
    for cls in FEED_CLASSES:
        if cls.handles_url(feed_url):
            feed_cls = cls
            break

    feed = feed_cls(feed_url, feed_content, last_mod_up, etag, **kwargs)
    feed.subscribe_at_hub(base_url)
    return feed
