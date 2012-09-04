# -*- coding: utf-8 -*-
#

import time

import feedparser

from feedservice.parse.models import Feed, Episode, File

from feedservice.utils import parse_time
from feedservice.parse.mimetype import get_mimetype
from feedservice.parse import mimetype
from feedservice.parse.core import Parser



class Feedparser(Parser):
    """ A parsed Feed """

    def __init__(self, url, resp):
        super(Feedparser, self).__init__(url, resp)
        self.url = url
        self.feed = feedparser.parse(url)


    @classmethod
    def handles_url(cls, url):
        """ Generic class that can handle every RSS/Atom feed """
        return True


    def get_feed(self):
        feed = Feed()
        feed.title = self.get_title()
        feed.link = self.get_link()
        feed.description = self.get_description()
        feed.author = self.get_author()
        feed.language = self.get_language()
        feed.urls = self.get_urls()
        feed.new_location = self.get_new_location()
        feed.logo = self.get_logo_url()
        feed.tags = self.get_feed_tags()
        feed.hub = self.get_hub_url()
        feed.http_last_modified = self.get_last_modified()
        feed.http_etag = self.get_etag()

        #feed.content_types = self.get_podcast_types()
        #feed.logo_data = self.get_logo_inline()

        feed.episodes = self.get_episodes()

        return feed


    def get_title(self):
        return self.feed.feed.get('title', None)


    def get_urls(self):
        return [self.url]

    def get_link(self):
        return self.feed.feed.get('link', None)

    def get_description(self):
        return self.feed.feed.get('subtitle', None)


    def get_author(self):
        return self.feed.feed.get('author',
               self.feed.feed.get('itunes_author', None))

    def get_language(self):
        return self.feed.feed.get('language', None)


    def get_new_location(self):
            return super(Feedparser, self).get_new_location() or \
                self.feed.feed.get('newlocation', None)


    def get_logo_url(self):
        image = self.feed.feed.get('image', None)
        if image is not None:
            for key in ('href', 'url'):
                cover_art = getattr(image, key, None)
                if cover_art:
                    return cover_art

        return None



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
        parser = map(FeedparserEpisodeParser, self.feed.entries)
        return [p.get_episode() for p in parser]



class FeedparserEpisodeParser(object):
    """ Parses episodes from a feedparser feed """


    def __init__(self, entry):
        self.entry = entry



    def get_episode(self):
        episode = Episode()
        episode.guide = self.get_guid()
        episode.title = self.get_title()
        episode.description = self.get_description()
        episode.link = self.get_link()
        episode.author = self.get_author()
        episode.duration = self.get_duration()
        episode.language = self.get_language()
        episode.files = list(self.get_files())
        episode.released = self.get_timestamp()
        #episode.number = self.get_episode_number()
        #episode.short_title = self.get_short_title()
        return episode


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

            #TODO: optional: urls = httputils.get_redirect_chain(enclosure['href'])
            urls = [enclosure['href']]
            yield (urls, mimetype, filesize)


        media_content = getattr(self.entry, 'media_content', [])
        for media in media_content:
            if not 'url' in media:
                continue

            mimetype = get_mimetype(media.get('type', ''), media['url'])

            try:
                filesize = int(media.get('fileSize', None))
            except (TypeError, ValueError):
                filesize = None

            #TODO: optional: urls = httputils.get_redirect_chain(media['url'])
            urls = [media['url']]
            yield urls, mimetype, filesize


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
        return int(time.mktime(self.entry.updated_parsed))



    def get_files(self):
        """Get the download / episode URL of a feedparser entry"""

        files = []

        for urls, mtype, filesize in self.list_files():

            # skip if we've seen this list of URLs already
            if urls in [f.urls for f in files]:
                break

            if not mimetype.check_mimetype(mtype):
                continue

            f = File(urls, mtype, filesize)
            files.append(f)

        return files
