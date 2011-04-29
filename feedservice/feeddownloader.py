#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import urllib
import time
import simplejson as json
import email.utils
import cgi

from google.appengine.ext import webapp

import httputils
import feed


class Parser(webapp.RequestHandler):
    """ Parser Endpoint """

    def post(self):
        return self.get()

    def get(self):
        urls = map(urllib.unquote, self.request.get_all('url'))

        inline_logo = self.request.get_range('inline_logo', 0, 1, default=0)
        scale_to = self.request.get_range('scale_logo', 0, 1, default=0)
        logo_format = self.request.get('logo_format')
        strip_html = self.request.get_range('strip_html', 0, 1, default=0)
        use_cache = self.request.get_range('use_cache', 0, 1, default=1)
        modified = self.request.headers.get('If-Modified-Since', None)
        accept = self.request.headers.get('Accept', 'application/json')

        if urls:
            podcasts, last_modified = parse_feeds(urls, inline_logo, scale_to, logo_format, strip_html, modified, use_cache)
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


def parse_feeds(feed_urls, *args, **kwargs):
    """
    Parses several feeds, specified by feed_urls and returns their JSON
    objects and the latest of their modification dates. RSS-Redirects are
    followed automatically by including both feeds in the result.
    """

    visited_urls = set()
    result = []
    last_modified = None

    for url in feed_urls:

        res, visited, new, last_mod = feed.Feed.parse(url, *args, **kwargs)

        if not res:
            continue

        visited = visited or []

        # we follow RSS-redirects automatically
        if new and new not in (list(visited_urls) + feed_urls):
            feed_urls.append(new)

        if not last_modified or (last_mod and last_mod > last_modified):
            last_modified = last_mod

        result.append(res)

    return result, last_modified
