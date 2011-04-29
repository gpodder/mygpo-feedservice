from datetime import datetime, timedelta
import time
import urllib2
from email import utils

from google.appengine.ext import db
from google.appengine.api import memcache


USER_AGENT = 'mygpo-feedservice +http://mygpo-feedservice.appspot.com/'


class URLObject(db.Model):
    url = db.StringProperty(required=True)
    content = db.Blob()
    etag = db.StringProperty(required=False)
    expires = db.DateTimeProperty(required=False)
    last_mod_up = db.DateTimeProperty(required=False)
    last_mod_utc = db.DateTimeProperty(required=False)

    def expired(self):
        return self.expires and self.expires <= datetime.utcnow()

    def valid(self):
        return len(self.content) > 0

    def __repr__(self):
        return '%(url)s (%(etag)s, %(expires)s, %(last_mod_up)s)' % \
            dict(url=self.url, etag=self.etag,
                 expires=self.expires, last_mod_up=self.last_mod_up)


def get_url(url, use_cache=True):
    """
    Gets the contents for the given URL from either memcache,
    the datastore or the URL itself
    """

    cached = from_cache(url) if use_cache else None

    if not cached or cached.expired() or not cached.valid():
        resp = fetch_url(url, cached)
    else:
        resp = cached.url, cached.content, cached.last_mod_up, cached.last_mod_utc, cached.etag

    return resp


def from_cache(url):
    """
    Tries to get the object for the given URL from Memcache or the Datastore
    """
    return memcache.get(url)


def fetch_url(url, cached=None, add_expires=timedelta()):
    """
    Fetches the given URL and stores the resulting object in the Cache
    """

    request = urllib2.Request(url)
    request.add_header('User-Agent', USER_AGENT)
    opener = urllib2.build_opener()

    if getattr(cached, 'last_modified', False):
        lm_str = utils.formatdate(time.mktime(cached.last_mod_up.timetuple()))
        request.add_header('If-Modified-Since', lm_str)

    if getattr(cached, 'etag', False):
        request.add_header('If-None-Match', cached.etag)

    try:
        r = opener.open(request)
        obj = cached or URLObject(url=url)
        obj.content = r.read()
        obj.expires = parse_header_date(r.headers.dict.get('expires', None))
        obj.last_mod_up = parse_header_date(r.headers.dict.get('last-modified', None))
        obj.last_mod_utc = datetime.utcnow()
        obj.etag = r.headers.dict.get('etag', None)

        if obj.expires is not None:
            obj.expires += add_expires
        elif add_expires:
            obj.expires = datetime.utcnow() + add_expires

        memcache.set(url, obj)

    except urllib2.HTTPError, e:
        if e.code == 304:
            obj = cached
            pass
        else:
            raise

    return obj.url, obj.content, obj.last_mod_up, obj.last_mod_utc, obj.etag


def parse_header_date(date_str):
    """
    Parses dates in RFC2822 format to datetime objects
    """
    if not date_str:
        return None
    ts = time.mktime(utils.parsedate(date_str))
    return datetime.utcfromtimestamp(ts)
