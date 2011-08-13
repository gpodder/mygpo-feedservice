# -*- coding: utf-8 -*-
#

import re
import logging

import Image
import StringIO

from feedservice import urlstore
from feedservice import httputils
from feedservice.utils import strip_html, flatten, longest_substr
from feedservice.parserservice.mimetype import get_mimetype, check_mimetype



class Feed(object):
    """ A parsed Feed """

    def __init__(self, url):
        self.url = url
        self.errors = {}
        self.warnings = {}


    @classmethod
    def handles_url(cls, url):
        """ Returns True if the class can handle the feed with the given URL """
        return False


    def parse(self):
        if last_mod_utc and mod_since_utc and last_mod_utc <= mod_since_utc:
            pass


    def to_dict(self, strip_html, inline_logo, scale_to, logo_format):
        """
        Parses a feed and returns its JSON object, a list of urls that refer to
        this feed, an outgoing redirect and the timestamp of the last modification
        of the feed
        """

        self.strip_html  = strip_html
        self.inline_logo = inline_logo
        self.logo_format = logo_format
        self.scale_to    = scale_to

        feed_dict = {}

        PROPERTIES = (
            ('title',              self.get_title),
            ('link',               self.get_link),
            ('description',        self.get_description),
            ('author',             self.get_author),
            ('language',           self.get_language),
            ('urls',               self.get_urls),
            ('new_location',       self.get_new_location),
            ('logo',               self.get_logo_url),
            ('logo_data',          self.get_logo_inline),
            ('tags',               self.get_feed_tags),
            ('hub',                self.get_hub_url),
            ('content_types',      self.get_podcast_types),
            ('http_last_modified', self.get_last_modified),
            ('episodes',           self.get_episodes),
#            ('http_etag',          self.get_etag),
        )

        for name, func in PROPERTIES:
            val = func()
            if val is not None:
                feed_dict[name] = val

        return feed_dict

    def add_error(self, key, msg):
        """ Adds an error entry to the feed """
        self.errors[key] = msg


    def add_warning(self, key, msg):
        """ Adds a warning entry to the feed """
        self.warnings[key] = msg


    @strip_html
    def get_title(self):
        return None


    def get_link(self):
        return None


    @strip_html
    def get_description(self):
        return None


    @strip_html
    def get_author(self):
        return None


    @strip_html
    def get_language(self):
        return None


    def get_urls(self):
        urls, self.new_loc = httputils.get_redirects(self.url)
        return urls


    def get_new_location(self):
        return None


    def get_logo_url(self):
        return None


    def get_logo_inline(self):
        """ Fetches the feed's logo and returns its data URI """

        if not self.inline_logo:
            return None

        logo_url = self.get_logo_url()

        if not logo_url:
            return None

        try:
            url, content, last_mod_up, last_mod_utc, etag, content_type, \
                length = urlstore.get_url(logo_url)

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
        return None


    def get_hub_url(self):
        return None


    def get_episodes(self):
        episodes = self.get_episode_objects()
        common_title = self.get_common_title(episodes)

        return [episode.to_dict(common_title) for episode in episodes]


    def get_common_title(self, episodes):
        # We take all non-empty titles
        titles = filter(None, (e.get_title() for e in episodes))

        # get the longest common substring
        common_title = longest_substr(titles)

        # but consider only the part up to the first number. Otherwise we risk
        # removing part of the number (eg if a feed contains episodes 100 - 199)
        common_title = re.search(r'^\D*', common_title).group(0)

        if len(common_title.strip()) < 2:
            return None

        return common_title



    def get_episode_objects(self):
        return []


    def get_podcast_types(self):
        from feedservice.parserservice.mimetype import get_podcast_types

        files = (episode.get_files() for episode in self.get_episode_objects())
        files = list(flatten(files))
        return get_podcast_types(f.get('mimetype', None) for f in files)


    def get_last_modified(self):
        return None


    def subscribe_at_hub(self, base_url):
        """ Tries to subscribe to the feed if it contains a hub URL """

        hub_url = self.get_hub_url()
        if not hub_url:
            return

        from feedservice.pubsubhubbub import subscribe
        from feedservice.pubsubhubbub.models import SubscriptionError

        # use the last URL in the redirect chain
        feed_url = self.get_urls()[-1]

        try:
            subscribe(feed_url, hub_url, base_url)
        except SubscriptionError, e:
            self.add_warning('hub-subscription', repr(e))



class Episode(object):
    """ A parsed Episode """


    def to_dict(self, common_title):

        self.common_title = common_title

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
            ('number',      self.get_episode_number),
            ('short_title', self.get_short_title),
        )

        episode_dict = {}

        for name, func in PROPERTIES:
            val = func()
            if val is not None:
                episode_dict[name] = val

        return episode_dict


    def get_guid(self):
        return None


    @strip_html
    def get_title(self):
        return None


    def get_link(self):
        return None


    @strip_html
    def get_author(self):
        return None

    @strip_html
    def get_description(self):
        return None


    def get_duration(self):
        return None


    def get_language(self):
        return None


    def get_timestamp(self):
        return None


    def get_files(self):
        """Get the download / episode URL of a feedparser entry"""

        files = []

        for url, mimetype, filesize in self.list_files():

            if not check_mimetype(mimetype):
                continue

            f = dict(url=url)
            if mimetype:
                f['mimetype'] = mimetype
            if filesize:
                f['filesize'] = filesize

            files.append(f)

        return files


    def get_episode_number(self):
        """
        Returns the first number in the non-repeating part of the episode's title
        """

        title = self.get_title()

        if None in (title, self.common_title):
            return None

        title = title.replace(self.common_title, '').strip()
        match = re.search(r'^\W*(\d+)', title)
        if not match:
            return None

        return int(match.group(1))


    def get_short_title(self):
        """
        Returns the non-repeating part of the episode's title
        If an episode number is found, it is removed
        """

        title = self.get_title()

        if None in (title, self.common_title):
            return None

        title = title.replace(self.common_title, '').strip()
        title = re.sub(r'^[\W\d]+', '', title)
        return title
