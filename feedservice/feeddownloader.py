#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import re
import urllib
import urllib2
import logging
import time
import simplejson as json

from google.appengine.ext import webapp

import urlstore
import httputils
import youtube
import utils
from mimetype import get_mimetype, check_mimetype


def strip_html(f):
    """ Decorator to strip HTML tags from the results of bound methods

    Checks if self has the attribute 'strip_html' set """

    def _tmp(self, *args, **kwargs):

        strip_html = getattr(self, 'strip_html', False)

        val = f(self, *args, **kwargs)
        if strip_html:
            from utils import remove_html_tags
            val = remove_html_tags(val)

        return val

    return _tmp



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
            from email import utils
            import time
            self.response.headers.add_header('Last-Modified', utils.formatdate(time.mktime(last_modified.timetuple())))


        else:
            import cgi
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

        res, visited, new, last_mod = Feed.parse(url, *args, **kwargs)

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



class Feed(dict):
    """ A parsed Feed """


    def __init__(self, strip_html):
        self.strip_html = strip_html


    @classmethod
    def parse(cls, feed_url, inline_logo, scale_to, logo_format, strip_html, modified, use_cache):
        """
        Parses a feed and returns its JSON object, a list of urls that refer to
        this feed, an outgoing redirect and the timestamp of the last modification
        of the feed
        """

        import feedparser

        feed_obj = Feed(strip_html)

        try:
            feed_url, feed_content, last_modified = urlstore.get_url(feed_url, use_cache)
            feed_obj.last_modified = last_modified

        except Exception, e:
            msg = 'could not fetch feed %(feed_url)s: %(msg)s' % \
                dict(feed_url=feed_url, msg=str(e))
            feed_obj.add_error('fetch-feed', msg)
            logging.info(msg)
            feed_obj.add_url(feed_url)
            return feed_obj, None, None, None


        if last_modified and modified and last_modified <= modified:
            return None, None, None, None

        feed = feedparser.parse(feed_content)

        PROPERTIES = (
            ('title',         lambda: feed_obj.get_title(feed)),
            ('link',          lambda: feed_obj.get_link(feed)),
            ('description',   lambda: feed_obj.get_description(feed)),
            ('author',        lambda: feed_obj.get_author(feed)),
            ('language',      lambda: feed_obj.get_language(feed)),
            ('urls',          lambda: feed_obj.get_urls(feed_url)),
            ('new_location',  lambda: feed_obj.get_new_location(feed)),
            ('logo',          lambda: feed_obj.get_podcast_logo(feed)),
            ('logo_data',     lambda: feed_obj.get_podcast_logo_inline(inline_logo, modified, size=scale_to, img_format=logo_format)),
            ('tags',          lambda: feed_obj.get_feed_tags(feed.feed)),
            ('hub',           lambda: feed_obj.get_hub_url(feed.feed)),
            ('episodes',      lambda: feed_obj.get_episodes(feed, strip_html)),
            ('content_types', lambda: feed_obj.get_podcast_types()),
        )

        for name, func in PROPERTIES:
            val = func()
            if val is not None:
                feed_obj[name] = val

        feed_obj.subscribe_at_hub()

        return feed_obj, feed_obj.get('urls', None), feed_obj.get('new_location', None), last_modified


    def add_error(self, key, msg):
        """ Adds an error entry to the feed """

        if not 'errors' in self:
            self['errors'] = {}

        self['errors'][key] = msg


    @strip_html
    def get_title(self, feed):
        return feed.feed.get('title', None)


    @staticmethod
    def get_link(feed):
        return feed.feed.get('link', None)

    @strip_html
    def get_description(self, feed):
        return feed.feed.get('subtitle', None)


    @strip_html
    def get_author(self, feed):
        return feed.feed.get('author', feed.feed.get('itunes_author', None))

    @strip_html
    def get_language(self, feed):
        return feed.feed.get('language', None)


    def add_url(self, url):
        if not 'urls' in self:
            self['urls'] = []

        self['urls'].append(url)


    @staticmethod
    def get_urls(feed_url):
        from httputils import get_redirects
        return get_redirects(feed_url)


    @staticmethod
    def get_new_location(feed):
        return feed.feed.get('newlocation', None)


    @staticmethod
    def get_podcast_logo(feed):
        cover_art = None
        image = feed.feed.get('image', None)
        if image is not None:
            for key in ('href', 'url'):
                cover_art = getattr(image, key, None)
                if cover_art:
                    break

        cover_art = youtube.get_real_cover(feed.feed.get('link', None)) or cover_art

        return cover_art


    def get_podcast_logo_inline(self, inline_logo, modified_since, **transform_args):
        """ Fetches the feed's logo and returns its data URI """

        if not inline_logo:
            return None

        logo_url = self.get('logo', None)

        if not logo_url:
            return None

        try:
            url, content, last_modified = urlstore.get_url(logo_url)

        except Exception, e:
            msg = 'could not fetch feed logo %(logo_url)s: %(msg)s' % \
                dict(logo_url=logo_url, msg=str(e))
            self.add_error('fetch-logo', msg)
            logging.info(msg)
            return None

        if last_modified and modified_since and last_modified <= modified_since:
            return None

        mimetype = get_mimetype(None, url)

        if any(transform_args.values()):
            content, mimetype = self.transform_image(content, mimetype, **transform_args)

        return httputils.get_data_uri(content, mimetype)


    @staticmethod
    def transform_image(content, mimetype, size, img_format):
        """
        Transforms (resizes, converts) the image and returns
        the resulting bytes and mimetype
        """

        from google.appengine.api import images

        img_formats = dict(png=images.PNG, jpeg=images.JPEG)

        img = images.Image(content)

        if img_format:
            mimetype = 'image/%s' % img_format
        else:
            img_format = mimetype[mimetype.find('/')+1:]

        if size:
            img.resize(min(size, img.width), min(size, img.height))

        content = img.execute_transforms(output_encoding=img_formats[img_format])
        return content, mimetype


    @staticmethod
    def get_feed_tags(feed):
        tags = []

        for tag in feed.get('tags', []):
            if tag['term']:
                tags.extend(filter(None, tag['term'].split(',')))

            if tag['label']:
                tags.append(tag['label'])

        return list(set(tags))


    @staticmethod
    def get_hub_url(feed):
        """
        Returns the Hub URL as specified by
        http://pubsubhubbub.googlecode.com/svn/trunk/pubsubhubbub-core-0.3.html#discovery
        """

        for l in feed.get('links', []):
            if l.rel == 'hub' and l.get('href', None):
                return l.href
        return None


    @staticmethod
    def get_episodes(feed, strip_html):
        get_episode = lambda e: Episode.parse(e, strip_html)
        episodes = filter(None, map(get_episode, feed.entries))

        # We take all non-empty titles
        titles = filter(None, [e.get('title', None) for e in episodes])

        # get the longest common substring
        common_title = utils.longest_substr(titles)

        # but consider only the part up to the first number. Otherwise we risk
        # removing part of the number (eg if a feed contains episodes 100 - 199)
        common_title = re.search(r'^\D*', common_title).group(0)

        for e in episodes:
            e.update(e.get_additional_episode_data(common_title))

        return episodes


    def get_podcast_types(self):
        from mimetype import get_podcast_types
        return get_podcast_types(self)


    def subscribe_at_hub(self):
        """ Tries to subscribe to the feed if it contains a hub URL """

        if not self.get('hub', False):
            return

        import pubsubhubbub

        # use the last URL in the redirect chain
        feed_url = self['urls'][-1]

        hub_url = self.get('hub')

        try:
            pubsubhubbub.Subscriber.subscribe(feed_url, hub_url)
        except pubsubhubbub.SubscriptionError, e:
            self.add_error('hub-subscription', repr(e))


class Episode(dict):
    """ A parsed Episode """


    def __init__(self, strip_html):
        self.strip_html = strip_html


    @classmethod
    def parse(cls, entry, strip_html):

        episode = Episode(strip_html)
        files = episode.get_episode_files(entry)

        if not files:
            return None

        PROPERTIES = (
            ('guid',        lambda: episode.get_guid(entry)),
            ('title',       lambda: episode.get_title(entry)),
            ('description', lambda: episode.get_description(entry)),
            ('link',        lambda: episode.get_link(entry)),
            ('author',      lambda: episode.get_author(entry)),
            ('duration',    lambda: episode.get_duration(entry)),
            ('language',    lambda: episode.get_language(entry)),
            ('files',       lambda: episode.get_files(files)),
            ('released',    lambda: episode.get_timestamp(entry)),
        )

        for name, func in PROPERTIES:
            val = func()
            if val is not None:
                episode[name] = val

        return episode



    @staticmethod
    def get_guid(entry):
        return entry.get('id', None)

    @strip_html
    def get_title(self, entry):
        return entry.get('title', None)

    @staticmethod
    def get_link(entry):
        return entry.get('link', None)

    @strip_html
    def get_author(self, entry):
        return entry.get('author', entry.get('itunes_author', None))


    @staticmethod
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


    @strip_html
    def get_description(self, entry):
        for key in ('summary', 'subtitle', 'link'):
            value = entry.get(key, None)
            if value:
                return value

        return None


    @staticmethod
    def get_duration(entry):
        from utils import parse_time

        str = entry.get('itunes_duration', '')
        try:
            return parse_time(str)
        except ValueError:
            return None


    @staticmethod
    def get_language(entry):
        return entry.get('language', None)


    @staticmethod
    def get_files(files):
        f = []
        for k, v in files.items():
            file = dict(url=k)
            if v[0]:
                file['mimetype'] = v[0]
            if v[1]:
                file['filesize'] = v[1]
            f.append(file)
        return f


    @staticmethod
    def get_timestamp(entry):
        from datetime import datetime
        try:
            return int(time.mktime(entry.updated_parsed))
        except:
            return None


    def get_additional_episode_data(self, common_title):
        """
        Returns additional data about an episode that is calculated after
        the first pass over all episodes
        """

        title = self.get('title', None)

        PROPERTIES = (
            ('number',      lambda: self.get_episode_number(title, common_title)),
            ('short_title', lambda: self.get_short_title(title, common_title)),
        )

        data = {}
        for name, func in PROPERTIES:
            val = func()
            if val is not None:
                data[name] = val

        return data

    @staticmethod
    def get_episode_number(title, common_title):
        """
        Returns the first number in the non-repeating part of the episode's title
        """

        if title is None:
            return None

        title = title.replace(common_title, '').strip()
        match = re.search(r'^\W*(\d+)', title)
        if not match:
            return None

        return int(match.group(1))


    @staticmethod
    def get_short_title(title, common_title):
        """
        Returns the non-repeating part of the episode's title
        If an episode number is found, it is removed
        """

        if title is None:
            return None

        title = title.replace(common_title, '').strip()
        title = re.sub(r'^[\W\d]+', '', title)
        return title
