#!/usr/bin/python
# -*- coding: utf-8 -*-
#


import urlstore
import youtube
from mimetype import get_mimetype, check_mimetype, get_podcast_types


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
        ('episodes',      False, lambda: get_episodes(feed, strip_html, podcast.get('title', None))),
        ('content_types', False, lambda: get_podcast_types(podcast)),
    )

    for name, is_text, func in PROPERTIES:
        set_val(podcast, name, func, strip_html and is_text)

    return podcast, podcast.get('urls', None), podcast.get('new_location', None), last_modified


def set_val(obj, name, func, remove_tags):
    from utils import remove_html_tags

    val = func()
    if remove_tags: val = remove_html_tags(val)
    if val is not None:
        obj[name] = val


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

    if None in (inline_logo, url):
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


def get_episodes(feed, strip_html, podcast_title):
    get_episode = lambda e: get_episode_metadata(e, strip_html, podcast_title)
    return filter(None, map(get_episode, feed.entries))


def get_episode_metadata(entry, strip_html, podcast_title=None):

    files = get_episode_files(entry)
    if not files:
        return None

    PROPERTIES = (
        ('guid',        None,  lambda: entry.get('id', None)),
        ('title',       True,  lambda: entry.get('title', None)),
        ('number',      False, lambda: get_episode_number(entry.get('title', None), podcast_title)),
        ('short_title', True,  lambda: get_short_title(entry.get('title', None), podcast_title)),
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


def get_episode_number(title, podcast_title):
    import re

    if title is None:
        return None

    title = title.replace(podcast_title, '').strip()
    match = re.search(r'^\W*(\d+)', title)
    if not match:
        return None

    return int(match.group(1))


def get_short_title(title, podcast_title):
    import re

    if title is None:
        return None

    title = title.replace(podcast_title, '').strip()
    title = re.sub(r'^[\W\d]+', '', title)
    title = re.sub(r'\W+$', '', title)
    return title


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
