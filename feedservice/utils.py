# -*- coding: utf-8 -*-
#
# This file is part of my.gpodder.org.
#
# my.gpodder.org is free software: you can redistribute it and/or modify it
# under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# my.gpodder.org is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Affero General Public
# License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with my.gpodder.org. If not, see <http://www.gnu.org/licenses/>.
#

import sys
import time
from itertools import chain
import collections
import urllib.parse
import re
from html.entities import entitydefs
import io
import http.client as httplib

import requests
from PIL import Image, ImageDraw
urlparse = urllib.parse

from urllib.request import (build_opener, HTTPPasswordMgrWithDefaultRealm,
    HTTPBasicAuthHandler, Request)

unicode = str


def _get_requests_defaults():
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'mygpo-feedservice +http://feeds.gpodder.net/',
    })
    return s


requests = _get_requests_defaults()


try:
    # If SimpleJSON is installed separately, it might be a recent version
    import simplejson as json
    JSONDecodeError = ValueError

except ImportError:
    print('simplejson not found', file=sys.stderr)

    # Otherwise use json from the stdlib
    import json
    JSONDecodeError = ValueError


def parse_time(value):
    """
    >>> parse_time(10)
    10

    >>> parse_time('05:10') #5*60+10
    310

    >>> parse_time('1:05:10') #60*60+5*60+10
    3910
    """
    if value is None:
        raise ValueError('None value in parse_time')

    if isinstance(value, int):
        # Don't need to parse already-converted time value
        return value

    if value == '':
        raise ValueError('Empty valueing in parse_time')

    for format in ('%H:%M:%S', '%M:%S'):
        try:
            t = time.strptime(value, format)
            return t.tm_hour * 60*60 + t.tm_min * 60 + t.tm_sec
        except (ValueError, TypeError):
            continue

    return int(value)


# from http://stackoverflow.com/questions/2892931/longest-common-substring-from-more-than-two-strings-python
# this does not increase asymptotical complexity
# but can still waste more time than it saves.
def shortest_of(strings):
    return min(strings, key=len)

def longest_substr(strings):
    """
    Returns the longest common substring of the given strings
    """

    substr = ""
    if not strings:
        return substr
    reference = shortest_of(strings) #strings[0]
    length = len(reference)
    #find a suitable slice i:j
    for i in range(length):
        #only consider strings long at least len(substr) + 1
        for j in range(i + len(substr) + 1, length):
            candidate = reference[i:j]
            if all(candidate in text for text in strings):
                substr = candidate
    return substr


def flatten(l):
    return chain.from_iterable(l)


# http://stackoverflow.com/questions/120951/how-can-i-normalize-a-url-in-python
def url_fix(s, charset='utf-8'):
    """Sometimes you get an URL by a user that just isn't a real
    URL because it contains unsafe characters like ' ' and so on.  This
    function can fix some of the problems in a similar way browsers
    handle data entered by the user:

    >>> url_fix(u'http://de.wikipedia.org/wiki/Elf (Begriffsklärung)')
    'http://de.wikipedia.org/wiki/Elf%20%28Begriffskl%C3%A4rung%29'

    :param charset: The target charset for the URL if the url was
                    given as unicode string.
    """
#    if isinstance(s, str):
#        s = s.encode(charset, 'ignore')
    scheme, netloc, path, qs, anchor = urllib.parse.urlsplit(s)
    path = urllib.parse.quote(path, '/%')
    qs = urllib.parse.quote_plus(qs, ':&=')
    return urllib.parse.urlunsplit((scheme, netloc, path, qs, anchor))


def remove_html_tags(html):
    """
    Remove HTML tags from a string and replace numeric and
    named entities with the corresponding character, so the
    HTML text can be displayed in a simple text view.
    """
    if html is None:
        return None

    # If we would want more speed, we could make these global
    re_strip_tags = re.compile('<[^>]*>')
    re_unicode_entities = re.compile('&#(\d{2,4});')
    re_html_entities = re.compile('&(.{2,8});')
    re_newline_tags = re.compile('(<br[^>]*>|<[/]?ul[^>]*>|</li>)', re.I)
    re_listing_tags = re.compile('<li[^>]*>', re.I)

    result = html

    # Convert common HTML elements to their text equivalent
    result = re_newline_tags.sub('\n', result)
    result = re_listing_tags.sub('\n * ', result)
    result = re.sub('<[Pp]>', '\n\n', result)

    # Remove all HTML/XML tags from the string
    result = re_strip_tags.sub('', result)

    # Convert numeric XML entities to their unicode character
    result = re_unicode_entities.sub(lambda x: chr(int(x.group(1))), result)

    # Convert named HTML entities to their unicode character
    result = re_html_entities.sub(lambda x: str(entitydefs.get(x.group(1),''), 'iso-8859-1'), result)

    # Convert more than two newlines to two newlines
    result = re.sub('([\r\n]{2})([\r\n])+', '\\1', result)

    return result.strip()


class NotModified(Exception):
    """ raised instead of HTTPException with code 304 """


def fetch_url(url, mod_since_utc=None):
    """
    Fetches the given URL and stores the resulting object in the Cache
    """

    headers = {}

    # TODO: how to handle redirect in requests?
    headers['User-Agent'] = ''

    if mod_since_utc:
        headers['If-Modified-Since'] = mod_since_utc

    return requests.get(url, headers=headers)


def basic_sanitizing(url):
    """
    does basic sanitizing through urlparse and additionally converts the netloc to lowercase
    """
    r = urllib.parse.urlsplit(url)
    netloc = r.netloc.lower()
    r2 = urllib.parse.SplitResult(r.scheme, netloc, r.path or '/', r.query, r.fragment)
    return r2.geturl()


def parse_header_list(values):
    """
    Parses a list in a HTTP header with q parameters, such as
    Accept-Language: de;q=1, en;q=0.5; *;q=0
    and returns the results as a dictionary and a sorted list
    """

    q_re = re.compile('q=([01](\.\d{0,4})?|(\.\d{0,4}))')
    default_q = 1

    val_list = []

    values = [x.strip() for x in values.split(',')]
    for v in values:
        v, q = v.split(';') if ';' in v else (v, 'q=1')
        match = q_re.match(q)
        q = float(match.group(1)) if match else 1
        if v == '*':
            default_q = q
        val_list.append( (v, q) )

    val_list = sorted(val_list, key=lambda x: x[1], reverse=True)
    val_dict = collections.defaultdict(lambda: default_q)
    val_dict.update(dict(val_list))

    return val_dict, val_list


def select_matching_option(supported_values, accepted_values):
    val_dict, val_list = parse_header_list(accepted_values)

    # see if any of the accepted values is supported
    for v, q in val_list:
        if v in supported_values:
            return v

    # if not, we just need to try the first one to
    # get the default value
    if val_dict[supported_values[0]] > 0:
        return supported_values[0]
    else:
        return None

def get_data_uri(data, mimetype):
    """
    returns the Data URI for the data
    """

    import base64
    encoded = base64.b64encode(data)
    return 'data:%s;base64,%s' % (mimetype, encoded)


def transform_image(content, mtype, size, img_format):
    """
    Transforms (resizes, converts) the image and returns
    the resulting bytes and mimetype
    """

    content_io = io.StringIO(content)
    img = Image.open(content_io)

    try:
        size = int(size)
    except (ValueError, TypeError):
        size = None

    if img.mode not in ('RGB', 'RGBA'):
        img = img.convert('RGB')

    if img_format:
        mtype = 'image/%s' % img_format
    else:
        img_format = mtype[mtype.find('/')+1:]

    if size:
        img = img.resize((size, size), Image.ANTIALIAS)

    # If it's a RGBA image, composite it onto a white background for JPEG
    if img.mode == 'RGBA':
        background = Image.new('RGB', img.size)
        draw = ImageDraw.Draw(background)
        draw.rectangle((-1, -1, img.size[0]+1, img.size[1]+1),
                       fill=(255, 255, 255))
        del draw
        img = Image.composite(img, background, img)

    io = io.StringIO()
    img.save(io, img_format.upper())
    content = io.getvalue()

    return content, mtype


def http_request(url, method='HEAD'):
    (scheme, netloc, path, parms, qry, fragid) = urlparse.urlparse(url)
    conn = httplib.HTTPConnection(netloc)
    start = len(scheme) + len('://') + len(netloc)
    conn.request(method, url[start:])
    return conn.getresponse()


def username_password_from_url(url):
    r"""
    Returns a tuple (username,password) containing authentication
    data from the specified URL or (None,None) if no authentication
    data can be found in the URL.

    See Section 3.1 of RFC 1738 (http://www.ietf.org/rfc/rfc1738.txt)

    >>> username_password_from_url('https://@host.com/')
    ('', None)
    >>> username_password_from_url('telnet://host.com/')
    (None, None)
    >>> username_password_from_url('ftp://foo:@host.com/')
    ('foo', '')
    >>> username_password_from_url('http://a:b@host.com/')
    ('a', 'b')
    >>> username_password_from_url(1)
    Traceback (most recent call last):
      ...
    ValueError: URL has to be a string or unicode object.
    >>> username_password_from_url(None)
    Traceback (most recent call last):
      ...
    ValueError: URL has to be a string or unicode object.
    >>> username_password_from_url('http://a@b:c@host.com/')
    ('a@b', 'c')
    >>> username_password_from_url('ftp://a:b:c@host.com/')
    ('a', 'b:c')
    >>> username_password_from_url('http://i%2Fo:P%40ss%3A@host.com/')
    ('i/o', 'P@ss:')
    >>> username_password_from_url('ftp://%C3%B6sterreich@host.com/')
    ('\xc3\xb6sterreich', None)
    >>> username_password_from_url('http://w%20x:y%20z@example.org/')
    ('w x', 'y z')
    >>> username_password_from_url('http://example.com/x@y:z@test.com/')
    (None, None)
    """
    if type(url) not in (str, unicode):
        raise ValueError('URL has to be a string or unicode object.')

    (username, password) = (None, None)

    (scheme, netloc, path, params, query, fragment) = urlparse.urlparse(url)

    if '@' in netloc:
        (authentication, netloc) = netloc.rsplit('@', 1)
        if ':' in authentication:
            (username, password) = authentication.split(':', 1)
            # RFC1738 dictates that we should not allow ['/', '@', ':']
            # characters in the username and password field (Section 3.1):
            #
            # 1. The "/" can't be in there at this point because of the way
            #    urlparse (which we use above) works.
            # 2. Due to gPodder bug 1521, we allow "@" in the username and
            #    password field. We use netloc.rsplit('@', 1), which will
            #    make sure that we split it at the last '@' in netloc.
            # 3. The colon must be excluded (RFC2617, Section 2) in the
            #    username, but is apparently allowed in the password. This
            #    is handled by the authentication.split(':', 1) above, and
            #    will cause any extraneous ':'s to be part of the password.

            username = urllib.unquote(username)
            password = urllib.unquote(password)
        else:
            username = urllib.unquote(authentication)

    return (username, password)
