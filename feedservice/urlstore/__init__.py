from datetime import datetime, timedelta
import time
import urllib2
import httplib
from email import utils
import base64
from collections import namedtuple
import logging


from feedservice.httputils import SmartRedirectHandler


logger = logging.getLogger(__name__)

USER_AGENT = 'mygpo-feedservice +http://feeds.gpodder.net/'


class NotModified(Exception):
    """ raised instead of HTTPException with code 304 """


def fetch_url(url, mod_since_utc=None):
    """
    Fetches the given URL and stores the resulting object in the Cache
    """

    handler = SmartRedirectHandler()

    request = urllib2.Request(url)

    request.add_header('User-Agent', USER_AGENT)

    if mod_since_utc:
        request.add_header('If-Modified-Since', mod_since_utc)

    opener = urllib2.build_opener(handler)

    try:
        return opener.open(request)

    except urllib2.HTTPError as e:
        if e.code == 304: # Not Modified
            raise NotModified
        else:
            raise


def parse_header_date(date_str):
    """
    Parses dates in RFC2822 format to datetime objects
    """
    if not date_str:
        return None
    ts = time.mktime(utils.parsedate(date_str))
    return datetime.utcfromtimestamp(ts)
