from datetime import datetime, timedelta
import time
import urllib2
import httplib
from email import utils
import base64
from collections import namedtuple
import logging

from couchdbkit.ext.django.schema import *
from django.core.cache import cache as ccache

from feedservice.urlstore.models import URLObject
from feedservice.httputils import SmartRedirectHandler


logger = logging.getLogger(__name__)

USER_AGENT = 'mygpo-feedservice +http://feeds.gpodder.net/'


class NotModified(Exception):
    """ raised instead of HTTPException with code 304 """


def get_url(url, use_cache=True, headers_only=False):
    """
    Gets the contents for the given URL from either memcache,
    the datastore or the URL itself
    """

    logger.info('URLStore: retrieving ' + url)

    cached = ccache.get(url) if use_cache else None

    if not cached or cached.expired() or not cached.valid():
        logger.info('URLStore: not using cache')
        obj = fetch_url(url, cached, headers_only)

    else:
        logger.info('URLStore: found in cache')
        obj = cached

    if use_cache:
        ccache.set(url, obj)

    return obj


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
