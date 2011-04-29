#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import urllib
import time
import simplejson as json
import email.utils
import logging
import cgi

from google.appengine.ext import webapp

from feed import Feed
import urlstore
import httputils


class Parser(webapp.RequestHandler):
    """ Parser Endpoint """

    def post(self):
        return self.get()

    def get(self):
        urls = map(urllib.unquote, self.request.get_all('url'))

        parse_args = dict(
            inline_logo = self.request.get_range('inline_logo', 0, 1, default=0),
            scale_to    = self.request.get_range('scale_logo',  0, 1, default=0),
            logo_format = self.request.get('logo_format'),
            strip_html  = self.request.get_range('strip_html',  0, 1, default=0),
            use_cache   = self.request.get_range('use_cache',   0, 1, default=1),
        )

        modified = self.request.headers.get('If-Modified-Since', None)
        accept   = self.request.headers.get('Accept', 'application/json')

        if urls:
            podcasts = parse_feeds(urls, modified, **parse_args)

            last_modified = None #TODO: set to server timestamp
            self.send_response(podcasts, last_modified, accept)

        else:
            self.response.set_status(400)
            self.response.out.write('parameter url missing')


    def send_response(self, podcasts, last_modified, formats):
        self.response.headers.add_header('Vary', 'Accept, User-Agent, Accept-Encoding')

        format = httputils.select_matching_option(['text/html', 'application/json'], formats)

        if format in (None, 'application/json'): #serve json as default
            content_type = 'application/json'
            content = json.dumps(podcasts, sort_keys=True, indent=None, separators=(',', ':'))
            self.response.headers.add_header('Last-Modified', email.utils.formatdate(time.mktime(last_modified.timetuple())))


        else:
            content_type = 'text/html'
            pretty_json = json.dumps(podcasts, sort_keys=True, indent=4)
            pretty_json = cgi.escape(pretty_json)
            content = """<html><head>
<link href="static/screen.css" type="text/css" rel="stylesheet" />
<link href="static/prettify.css" type="text/css" rel="stylesheet" />
<script type="text/javascript" src="static/prettify.js"></script>
</head><body onload="prettyPrint()"><h1>HTML Response</h1><p>This response is HTML formatted. To get just the JSON data for processing in your client, <a href="/#accept">send the HTTP Header <em>Accept: application/json</em></a>. <a href="/">Back to the Documentation</a></p><pre class="prettyprint">%s</pre></body></html>""" % pretty_json

        self.response.headers['Content-Type'] = content_type
        self.response.out.write(content)


def parse_feeds(feed_urls, modified_since, **kwargs):
    """
    Parses several feeds, specified by feed_urls and returns their JSON
    objects and the latest of their modification dates. RSS-Redirects are
    followed automatically by including both feeds in the result.
    """

    visited_urls = set()
    result = []

    for url in feed_urls:

        feed = parse_feed(url, modified_since, **kwargs)

        if not feed:
            continue

        visited  = feed.get('urls', [])
        new_loc  = feed.get('new_location', None)

        # we follow RSS-redirects automatically
        if new_loc and new_loc not in (list(visited_urls) + feed_urls):
            feed_urls.append(new_loc)

        result.append(feed)

    return result


def parse_feed(feed_url, modified_since, use_cache, **kwargs):
    """
    Parses a feed and returns its JSON object, a list of urls that refer to
    this feed, an outgoing redirect and the timestamp of the last modification
    of the feed
    """

    try:
        feed_url, feed_content, last_modified, etag = urlstore.get_url(feed_url, use_cache)

    except Exception, e:
        # create a dummy feed to hold the error message and the feed URL
        feed = Feed()
        msg = 'could not fetch feed %(feed_url)s: %(msg)s' % \
            dict(feed_url=feed_url, msg=str(e))
        feed.add_error('fetch-feed', msg)
        logging.info(msg)
        feed.add_url(feed_url)
        raise
        return feed

    if last_modified and modified_since and last_modified <= modified_since:
        return None

    # we can select between special-case classes later
    feed_cls = Feed

    feed = feed_cls.from_blob(feed_url, feed_content, last_modified, etag, **kwargs)
    return feed
