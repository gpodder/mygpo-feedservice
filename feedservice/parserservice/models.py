#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import re
import logging
import time

import feedparser
import Image
import StringIO

from feedservice import urlstore
from feedservice import httputils
from feedservice.utils import strip_html, parse_time, longest_substr
from feedservice.parserservice.mimetype import get_mimetype, check_mimetype



class Feed(dict):
    """ A parsed Feed """

    def __init__(self, feed_url, feed_content, last_mod_up, etag, inline_logo,
                       scale_to, logo_format, strip_html):

        self.feed_url = feed_url
        self.last_mod_up = last_mod_up
        self.etag = etag
        self.inline_logo = inline_logo
        self.scale_to = scale_to
        self.logo_format = logo_format
        self.strip_html = strip_html
        self.feed = feedparser.parse(feed_content)
        self.process_feed()


    @staticmethod
    def handles_url(url):
        """ Generic class that can handle every RSS/Atom feed """
        return True


    @property
    def episode_cls(self):
        return Episode


    def process_feed(self):
        """
        Parses a feed and returns its JSON object, a list of urls that refer to
        this feed, an outgoing redirect and the timestamp of the last modification
        of the feed
        """

        PROPERTIES = (
            ('title',              self.get_title),
            ('link',               self.get_link),
            ('description',        self.get_description),
            ('author',             self.get_author),
            ('language',           self.get_language),
            ('urls',               self.get_urls),
            ('new_location',       self.get_new_location),
            ('logo',               self.get_podcast_logo),
            ('logo_data',          self.get_podcast_logo_inline),
            ('tags',               self.get_feed_tags),
            ('hub',                self.get_hub_url),
            ('episodes',           self.get_episodes),
            ('content_types',      self.get_podcast_types),
            ('http_last_modified', self.get_last_modified),
            ('http_etag',          self.get_etag),
        )

        for name, func in PROPERTIES:
            val = func()
            if val is not None:
                self[name] = val


    def add_error(self, key, msg):
        """ Adds an error entry to the feed """

        if not 'errors' in self:
            self['errors'] = {}

        self['errors'][key] = msg


    def add_warning(self, key, msg):
        """ Adds a warning entry to the feed """

        if not 'warnings' in self:
            self['warnings'] = {}

        self['warnings'][key] = msg


    @strip_html
    def get_title(self):
        return self.feed.feed.get('title', None)


    def get_link(self):
        return self.feed.feed.get('link', None)

    @strip_html
    def get_description(self):
        return self.feed.feed.get('subtitle', None)


    @strip_html
    def get_author(self):
        return self.feed.feed.get('author',
                self.feed.feed.get('itunes_author', None))

    @strip_html
    def get_language(self):
        return self.feed.feed.get('language', None)


    def add_url(self, url):
        if not 'urls' in self:
            self['urls'] = []

        self['urls'].append(url)


    def get_urls(self):
        urls, self.new_loc = httputils.get_redirects(self.feed_url)
        return urls


    def get_new_location(self):
        # self.new_loc is set by get_urls()
        return getattr(self, 'new_loc', False) or \
               self.feed.feed.get('newlocation', None)


    def get_podcast_logo(self):
        cover_art = None
        image = self.feed.feed.get('image', None)
        if image is not None:
            for key in ('href', 'url'):
                cover_art = getattr(image, key, None)
                if cover_art:
                    break

        return cover_art


    def get_podcast_logo_inline(self):
        """ Fetches the feed's logo and returns its data URI """

        if not self.inline_logo:
            return None

        logo_url = self.get('logo', None)

        if not logo_url:
            return None

        try:
            url, content, last_mod_up, last_mod_utc, etag = urlstore.get_url(logo_url)

        except Exception, e:
            msg = 'could not fetch feed logo %(logo_url)s: %(msg)s' % \
                dict(logo_url=logo_url, msg=str(e))
            self.add_warning('fetch-logo', msg)
            logging.info(msg)
            return None

        # TODO: uncomment
        #if last_mod_up and mod_since_up and last_mod_up <= mod_since_up:
        #    return None

        mimetype = get_mimetype(None, url)

        transform_args = dict(size=self.scale_to, img_format=self.logo_format)

        if any(transform_args.values()):
            content, mimetype = self.transform_image(content, mimetype, **transform_args)

        return httputils.get_data_uri(content, mimetype)


    @staticmethod
    def transform_image(content, mimetype, size, img_format):
        """
        Transforms (resizes, converts) the image and returns
        the resulting bytes and mimetype
        """

        content_io = StringIO.StringIO(content)
        img = Image.open(content_io)

        try:
            size = int(size)
        except (ValueError, TypeError):
            size = None

        if img.mode not in ('RGB', 'RGBA'):
            img = im.convert('RGB')

        if img_format:
            mimetype = 'image/%s' % img_format
        else:
            img_format = mimetype[mimetype.find('/')+1:]

        if size:
            img = img.resize((size, size), Image.ANTIALIAS)


        # If it's a RGBA image, composite it onto a white background for JPEG
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size)
            draw = ImageDraw.Draw(background)
            draw.rectangle((-1, -1, img.size[0]+1, img.size[1]+1), \
                    fill=(255, 255, 255))
            del draw
            img = Image.composite(img, background, img)

        io = StringIO.StringIO()
        img.save(io, img_format.upper())
        content = io.getvalue()

        return content, mimetype


    def get_feed_tags(self):
        tags = []

        for tag in self.feed.feed.get('tags', []):
            if tag['term']:
                tags.extend(filter(None, tag['term'].split(',')))

            if tag['label']:
                tags.append(tag['label'])

        return list(set(tags))


    def get_hub_url(self):
        """
        Returns the Hub URL as specified by
        http://pubsubhubbub.googlecode.com/svn/trunk/pubsubhubbub-core-0.3.html#discovery
        """

        for l in self.feed.feed.get('links', []):
            if l.rel == 'hub' and l.get('href', None):
                return l.href
        return None


    def get_episodes(self):
        get_episode = lambda e: self.episode_cls(e, self.strip_html)
        episodes = filter(None, map(get_episode, self.feed.entries))

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
        from feedservice.parserservice.mimetype import get_podcast_types
        return get_podcast_types(self)


    def get_last_modified(self):
        try:
            return int(time.mktime(self.last_mod_up.timetuple()))
        except:
            return None


    def get_etag(self):
        return self.etag


    def subscribe_at_hub(self, base_url):
        """ Tries to subscribe to the feed if it contains a hub URL """

        if not self.get('hub', False):
            return

        from feedservice.pubsubhubbub import subscribe
        from feedservice.pubsubhubbub.models import SubscriptionError

        # use the last URL in the redirect chain
        feed_url = self['urls'][-1]

        hub_url = self.get('hub')

        try:
            subscribe(feed_url, hub_url, base_url)
        except SubscriptionError, e:
            self.add_warning('hub-subscription', repr(e))


class Episode(dict):
    """ A parsed Episode """


    def __init__(self, entry, strip_html):
        self.strip_html = strip_html
        self.entry = entry
        self.process_episode()


    def process_episode(self):

        self.files = self.get_episode_files()

        if not self.files:
            return None

        PROPERTIES = (
            ('guid',        self.get_guid),
            ('title',       self.get_title),
            ('description', self.get_description),
            ('link',        self.get_link),
            ('author',      self.get_author),
            ('duration',    self.get_duration),
            ('language',    self.get_language),
            ('files',       self.get_files),
            ('released',    self.get_timestamp),
        )

        for name, func in PROPERTIES:
            val = func()
            if val is not None:
                self[name] = val


    def get_guid(self):
        return self.entry.get('id', None)

    @strip_html
    def get_title(self):
        return self.entry.get('title', None)

    def get_link(self):
        return self.entry.get('link', None)

    @strip_html
    def get_author(self):
        return self.entry.get('author', self.entry.get('itunes_author', None))


    def get_episode_files(self):
        """Get the download / episode URL of a feedparser entry"""

        urls = {}
        enclosures = getattr(self.entry, 'enclosures', [])
        for enclosure in enclosures:
            if 'href' in enclosure:
                mimetype = get_mimetype(enclosure.get('type', ''), enclosure['href'])
                if check_mimetype(mimetype):
                    try:
                        filesize = int(enclosure.get('length', None))
                    except (TypeError, ValueError):
                        filesize = None
                    urls[enclosure['href']] = (mimetype, filesize)

        media_content = getattr(self.entry, 'media_content', [])
        for media in media_content:
            if 'url' in media:
                mimetype = get_mimetype(media.get('type', ''), media['url'])
                if check_mimetype(mimetype):
                    urls[media['url']] = (mimetype, None)

        return urls


    @strip_html
    def get_description(self):
        for key in ('summary', 'subtitle', 'link'):
            value = self.entry.get(key, None)
            if value:
                return value

        return None


    def get_duration(self):
        str = self.entry.get('itunes_duration', '')
        try:
            return parse_time(str)
        except ValueError:
            return None


    def get_language(self):
        return self.entry.get('language', None)


    def get_files(self):
        f = []
        for k, v in self.files.items():
            file = dict(url=k)
            if v[0]:
                file['mimetype'] = v[0]
            if v[1]:
                file['filesize'] = v[1]
            f.append(file)
        return f


    def get_timestamp(self):
        try:
            return int(time.mktime(self.entry.updated_parsed))
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
