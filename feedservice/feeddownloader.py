#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import re, urllib
import simplejson as json

from google.appengine.ext import webapp

import urlstore, httputils, youtube, utils
from mimetype import get_mimetype, check_mimetype, get_podcast_types


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
        res, visited, new, last_mod = parse_feed(url, *args, **kwargs)

        if not res:
            continue

        visited_urls.update(visited)

        # we follow RSS-redirects automatically
        if new and new not in (list(visited_urls) + feed_urls):
            feed_urls.append(new)

        if not last_modified or (last_mod and last_mod > last_modified):
            last_modified = last_mod

        result.append(res)

    return result, last_modified


def parse_feed(feed_url, inline_logo, scale_to, logo_format, strip_html, modified, use_cache):
    """
    Parses a feed and returns its JSON object, a list of urls that refer to
    this feed, an outgoing redirect and the timestamp of the last modification
    of the feed
    """

    import feedparser
    from httputils import get_redirects

    feed_url, feed_content, last_modified = urlstore.get_url(feed_url, use_cache)

    if last_modified and modified and last_modified <= modified:
        return None, None, None, None

    feed = feedparser.parse(feed_content)

    podcast = dict()

    PROPERTIES = (
        ('title',         True,  lambda: feed.feed.get('title', None)),
        ('link',          False, lambda: feed.feed.get('link', None)),
        ('description',   True,  lambda: feed.feed.get('subtitle', None)),
        ('author',        True,  lambda: feed.feed.get('author', feed.feed.get('itunes_author', None))),
        ('language',      False, lambda: feed.feed.get('language', None)),
        ('urls',          False, lambda: get_redirects(feed_url)),
        ('new_location',  False, lambda: feed.feed.get('newlocation', None)),
        ('logo',          False, lambda: get_podcast_logo(feed)),
        ('logo_data',     False, lambda: get_data_uri(inline_logo, podcast.get('logo', None), modified, size=scale_to, img_format=logo_format)),
        ('tags',          False, lambda: get_feed_tags(feed.feed)),
        ('hub',           False, lambda: get_hub_url(feed.feed)),
        ('episodes',      False, lambda: get_episodes(feed, strip_html)),
        ('content_types', False, lambda: get_podcast_types(podcast)),
    )

    for name, is_text, func in PROPERTIES:
        set_val(podcast, name, func, strip_html and is_text)

    subscribe_at_hub(podcast)

    return podcast, podcast.get('urls', None), podcast.get('new_location', None), last_modified


def set_val(obj, name, func, remove_tags=False):
    from utils import remove_html_tags

    val = func()
    if remove_tags: val = remove_html_tags(val)
    if val is not None:
        obj[name] = val


def add_error(feed, key, msg):
    """ Adds an error entry to the feed """

    if not 'errors' in feed:
        feed['errors'] = {}

    feed['errors'][key] = msg


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


def get_data_uri(inline_logo, url, modified_since, **transform_args):
    """
    Fetches the logo, applies the specified transformations and
    returns the Data URI for the resulting image
    """

    import base64

    if not inline_logo or not url:
        return None

    url, content, last_modified = urlstore.get_url(url)

    if last_modified and modified_since and last_modified <= modified:
        return None

    mimetype = get_mimetype(None, url)

    if any(transform_args.values()):
        content, mimetype = transform_image(content, mimetype, **transform_args)

    encoded = base64.b64encode(content)
    return 'data:%s;base64,%s' % (mimetype, encoded)


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


def get_feed_tags(feed):
    tags = []

    for tag in feed.get('tags', []):
        if tag['term']:
            tags.extend(filter(None, tag['term'].split(',')))

        if tag['label']:
            tags.append(tag['label'])

    return list(set(tags))


def get_hub_url(feed):
    """
    Returns the Hub URL as specified by
    http://pubsubhubbub.googlecode.com/svn/trunk/pubsubhubbub-core-0.3.html#discovery
    """

    for l in feed.get('links', []):
        if l.rel == 'hub' and l.get('href', None):
            return l.href
    return None


def get_episodes(feed, strip_html):
    get_episode = lambda e: get_episode_metadata(e, strip_html)
    episodes = filter(None, map(get_episode, feed.entries))

    # We take all non-empty titles
    titles = filter(None, [e.get('title', None) for e in episodes])

    # get the longest common substring
    common_title = utils.longest_substr(titles)

    # but consider only the part up to the first number. Otherwise we risk
    # removing part of the number (eg if a feed contains episodes 100 - 199)
    common_title = re.search(r'^\D*', common_title).group(0)

    for e in episodes:
        e.update(get_additional_episode_data(e, common_title))

    return episodes



def get_episode_metadata(entry, strip_html):

    files = get_episode_files(entry)
    if not files:
        return None

    PROPERTIES = (
        ('guid',        None,  lambda: entry.get('id', None)),
        ('title',       True,  lambda: entry.get('title', None)),
        ('description', True,  lambda: get_episode_summary(entry)),
        ('link',        False, lambda: entry.get('link', None)),
        ('author',      True,  lambda: entry.get('author', entry.get('itunes_author', None))),
        ('duration',    False, lambda: get_duration(entry)),
        ('language',    False, lambda: entry.get('language', None)),
        ('files',       False, lambda: get_files(files)),
        ('released',    False, lambda: get_timestamp(entry)),
    )

    episode = {}
    for name, is_text, func in PROPERTIES:
        set_val(episode, name, func, strip_html and is_text)

    return episode


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

    return None


def get_duration(entry):
    from utils import parse_time

    str = entry.get('itunes_duration', '')
    try:
        return parse_time(str)
    except ValueError:
        return None


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


def get_timestamp(entry):
    from datetime import datetime
    try:
        return datetime(*(entry.updated_parsed)[:6]).strftime('%Y-%m-%dT%H:%M:%S')
    except:
        return None


def get_additional_episode_data(episode, common_title):
    """
    Returns additional data about an episode that is calculated after
    the first pass over all episodes
    """

    PROPERTIES = (
        ('number',      lambda: get_episode_number(episode.get('title', None), common_title)),
        ('short_title', lambda: get_short_title(episode.get('title', None), common_title)),
    )

    data = {}
    for name, func in PROPERTIES:
        set_val(data, name, func)

    return data


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


def subscribe_at_hub(feed):
    """ Tries to subscribe to the feed if it contains a hub URL """

    if not feed.get('hub', False):
        return

    import pubsubhubbub

    # use the last URL in the redirect chain
    feed_url = feed['urls'][-1]

    hub_url = feed.get('hub')

    try:
        pubsubhubbub.Subscriber.subscribe(feed_url, hub_url)
    except pubsubhubbub.SubscriptionError, e:
        add_error(feed, 'hub-subscription', repr(e))
