#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import re
import logging
import time

import feedparser

import urlstore
import httputils
import youtube
from utils import strip_html, parse_time, longest_substr
from mimetype import get_mimetype, check_mimetype



class Feed(dict):
    """ A parsed Feed """


    def __init__(self, strip_html=False, last_modified=None, etag=None):
        self.strip_html = strip_html
        self.last_modified = last_modified
        self.etag = etag


    @classmethod
    def from_blob(cls, feed_url, feed_content, last_modified, etag, inline_logo, scale_to, logo_format, strip_html):
        """
        Parses a feed and returns its JSON object, a list of urls that refer to
        this feed, an outgoing redirect and the timestamp of the last modification
        of the feed
        """

        feed_res = feedparser.parse(feed_content)

        feed = Feed(strip_html, last_modified, etag)

        PROPERTIES = (
            ('title',              lambda: feed.get_title(feed_res)),
            ('link',               lambda: feed.get_link(feed_res)),
            ('description',        lambda: feed.get_description(feed_res)),
            ('author',             lambda: feed.get_author(feed_res)),
            ('language',           lambda: feed.get_language(feed_res)),
            ('urls',               lambda: feed.get_urls(feed_url)),
            ('new_location',       lambda: feed.get_new_location(feed_res)),
            ('logo',               lambda: feed.get_podcast_logo(feed_res)),
            ('logo_data',          lambda: feed.get_podcast_logo_inline(inline_logo, last_modified, size=scale_to, img_format=logo_format)),
            ('tags',               lambda: feed.get_feed_tags(feed_res.feed)),
            ('hub',                lambda: feed.get_hub_url(feed_res.feed)),
            ('episodes',           lambda: feed.get_episodes(feed_res, strip_html)),
            ('content_types',      lambda: feed.get_podcast_types()),
            ('http_last_modified', lambda: feed.get_last_modified()),
            ('http_etag',          lambda: feed.get_etag()),
        )

        for name, func in PROPERTIES:
            val = func()
            if val is not None:
                feed[name] = val

        feed.subscribe_at_hub()

        return feed


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
            url, content, last_modified, etag = urlstore.get_url(logo_url)

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
        common_title = longest_substr(titles)

        # but consider only the part up to the first number. Otherwise we risk
        # removing part of the number (eg if a feed contains episodes 100 - 199)
        common_title = re.search(r'^\D*', common_title).group(0)

        for e in episodes:
            e.update(e.get_additional_episode_data(common_title))

        return episodes


    def get_podcast_types(self):
        from mimetype import get_podcast_types
        return get_podcast_types(self)


    def get_last_modified(self):
        try:
            return int(time.mktime(self.last_modified.timetuple()))
        except:
            return None


    def get_etag(self):
        return self.etag


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
