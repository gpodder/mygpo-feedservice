# -*- coding: utf-8 -*-
#

import re
import logging
import time

import feedparser
import Image
import StringIO

from feedservice.parserservice.models import Feed, Episode

from feedservice import urlstore
from feedservice import httputils
from feedservice.utils import parse_time, longest_substr
from feedservice.parserservice.mimetype import get_mimetype, check_mimetype



class FeedparserFeed(Feed):
    """ A parsed Feed """

    def __init__(self, url, content, inline_logo, scale_to, logo_format):

        super(FeedparserFeed, self).__init__(url, content, inline_logo,
                scale_to, logo_format)

        self.episodes = None
        self.feed = feedparser.parse(content)


    @classmethod
    def handles_url(cls, url):
        """ Generic class that can handle every RSS/Atom feed """
        return True


    def get_title(self):
        return self.feed.feed.get('title', None)


    def get_link(self):
        return self.feed.feed.get('link', None)

    def get_description(self):
        return self.feed.feed.get('subtitle', None)


    def get_author(self):
        return self.feed.feed.get('author',
                self.feed.feed.get('itunes_author', None))

    def get_language(self):
        return self.feed.feed.get('language', None)


    def get_urls(self):
        urls, self.new_loc = httputils.get_redirects(self.url)
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


    @property
    def episode_cls(self):
       return FeedparserEpisode


    def get_episode_objects(self):
        if self.episodes is None:
            self.episodes = map(self.episode_cls, self.feed.entries)
            self.episodes = filter(None, self.episodes)

        return self.episodes


    def get_last_modified(self):
        try:
            return int(time.mktime(self.last_mod_up.timetuple()))
        except:
            return None


class FeedparserEpisode(Episode):
    """ A parsed Episode """


    def __init__(self, entry):
        self.entry = entry


    def get_guid(self):
        return self.entry.get('id', None)


    def get_title(self):
        return self.entry.get('title', None)


    def get_link(self):
        return self.entry.get('link', None)


    def get_author(self):
        return self.entry.get('author', self.entry.get('itunes_author', None))


    def list_files(self):
        for enclosure in getattr(self.entry, 'enclosures', []):
            if not 'href' in enclosure:
                continue

            mimetype = get_mimetype(enclosure.get('type', ''),
                    enclosure['href'])

            try:
                filesize = int(enclosure.get('length', None))
            except (TypeError, ValueError):
                filesize = None

            yield (enclosure['href'], mimetype, filesize)


        media_content = getattr(self.entry, 'media_content', [])
        for media in media_content:
            if not 'url' in media:
                continue

            mimetype = get_mimetype(media.get('type', ''), media['url'])

            yield media['url'], mimetype, None


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


    def get_timestamp(self):
        try:
            return int(time.mktime(self.entry.updated_parsed))
        except:
            return None
