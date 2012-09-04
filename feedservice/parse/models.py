# -*- coding: utf-8 -*-
#

import re

from feedservice.utils import flatten, longest_substr
from feedservice.parse import mimetype
from feedservice.parse.bitlove import get_bitlove_torrent



class ParsedObject(object):
    pass



class Feed(ParsedObject):
    """ A parsed Feed """

    def __init__(self):
        self.errors = {}
        self.warnings = {}


    def add_error(self, key, msg):
        """ Adds an error entry to the feed """
        self.errors[key] = msg


    def add_warning(self, key, msg):
        """ Adds a warning entry to the feed """
        self.warnings[key] = msg



    def get_urls(self):
        if self.url_obj:
            return self.url_obj.urls

        return None


    # TODO: call somewhere
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



    def get_podcast_types(self):
        files = (episode.get_files() for episode in self.get_episode_objects())
        files = list(flatten(files))
        return mimetype.get_podcast_types(f.get('mimetype', None) for f in files)



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



class Episode(ParsedObject):
    """ A parsed Episode """


    def get_files(self):
        """Get the download / episode URL of a feedparser entry"""

        files = []

        for urls, mtype, filesize in self.list_files():

            # skip if we've seen this list of URLs already
            if urls in [f['urls'] for f in files]:
                break

            if not mimetype.check_mimetype(mtype):
                continue

            f = dict(urls=urls)
            if mtype:
                f['mimetype'] = mtype
            if filesize:
                f['filesize'] = filesize

#           TODO: optional
#           bitlove_torrent = get_bitlove_torrent(urls)
#           if bitlove_torrent:
#               f['bitlove'] = bitlove_torrent

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



class File(ParsedObject):

    def __init__(self, urls, mimetype=None, filesize=None):
        self.urls = urls

        if mimetype is not None:
            self.mimetype = mimetype

        if filesize is not None:
            self.filesize = filesize
