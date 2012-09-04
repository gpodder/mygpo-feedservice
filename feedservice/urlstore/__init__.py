from datetime import datetime, timedelta
import time
import urllib2
from email import utils
import base64
from collections import namedtuple
import logging

from couchdbkit.ext.django.schema import *
from django.core.cache import cache as ccache

from feedservice.urlstore.models import URLObject
from feedservice.httputils import RedirectCollector


logger = logging.getLogger(__name__)

USER_AGENT = 'mygpo-feedservice +http://feeds.gpodder.net/'


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


def fetch_url(url):
    """
    Fetches the given URL and stores the resulting object in the Cache
    """

    collector = RedirectCollector(url)

    request = urllib2.Request(url)

    request.add_header('User-Agent', USER_AGENT)
    opener = urllib2.build_opener(collector)

    try:
        r = opener.open(request)

        r.urls = collector.get_redirects()
        r.permanent_redirect = collector.permanent_redirect

#        obj.expires = parse_header_date(headers.get('expires', None))
#        obj.last_mod_up = parse_header_date(headers.get('last-modified', None))
#        obj.content_type = headers.get('content-type', None)
#        obj.last_mod_utc = datetime.utcnow()
#        obj.etag = r.headers.dict.get('etag', None)

#        length = headers.get('content-length', None)

    except urllib2.HTTPError, e:
        logger.info('HTTP %d' % e.code)

        if e.code == 304:
            obj = cached
        elif e.code == 403:
            return URLObject(url=url)
        else:
            raise

    return r


def parse_header_date(date_str):
    """
    Parses dates in RFC2822 format to datetime objects
    """
    if not date_str:
        return None
    ts = time.mktime(utils.parsedate(date_str))
    return datetime.utcfromtimestamp(ts)
