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
import urllib
import urllib2
import urlparse
import re
from htmlentitydefs import entitydefs


USER_AGENT = 'mygpo-feedservice +http://feeds.gpodder.net/'


try:
    # If SimpleJSON is installed separately, it might be a recent version
    import simplejson as json
    JSONDecodeError = ValueError

except ImportError:
    print >> sys.stderr, 'simplejson not found'

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
        except ValueError, e:
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
    for i in xrange(length):
        #only consider strings long at least len(substr) + 1
        for j in xrange(i + len(substr) + 1, length):
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
    if isinstance(s, unicode):
        s = s.encode(charset, 'ignore')
    scheme, netloc, path, qs, anchor = urlparse.urlsplit(s)
    path = urllib.quote(path, '/%')
    qs = urllib.quote_plus(qs, ':&=')
    return urlparse.urlunsplit((scheme, netloc, path, qs, anchor))


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
    result = re_unicode_entities.sub(lambda x: unichr(int(x.group(1))), result)

    # Convert named HTML entities to their unicode character
    result = re_html_entities.sub(lambda x: unicode(entitydefs.get(x.group(1),''), 'iso-8859-1'), result)

    # Convert more than two newlines to two newlines
    result = re.sub('([\r\n]{2})([\r\n])+', '\\1', result)

    return result.strip()


class SmartRedirectHandler(urllib2.HTTPRedirectHandler):

    def http_error_301(self, req, fp, code, msg, headers):
        result = urllib2.HTTPRedirectHandler.http_error_301(
            self, req, fp, code, msg, headers)
        result.status = code
        return result

    def http_error_302(self, req, fp, code, msg, headers):
        result = urllib2.HTTPRedirectHandler.http_error_302(
            self, req, fp, code, msg, headers)
        result.status = code
        return result


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


class PermanentRedirectException(Exception):
    """ Raised on a permanent redirect, if it should not be followed """


class HeadRequest(urllib2.Request):
    def get_method(self):
        return "HEAD"


class RedirectCollector(urllib2.HTTPRedirectHandler):
    """Collects all seen (intermediate) redirects for a HTTP request"""

    def http_error_301(self, req, fp, code, msg, hdrs):

        self.permanent_redirect = hdrs['Location']
        return True

    def redirect_request(self, req, fp, code, msg, hdrs, newurl):

        # automatically follow non-permanent redirects
        if code in (302, 303):
            self.urls.append(newurl)
            return urllib2.HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, hdrs, newurl)

        # record permanent redirects but don't follow
        elif code == 301:
            self.permanent_redirect = newurl
            return None


    def get_redirects(self):
        """ Returns the complete redirect chain, starting from url """

        urls = map(basic_sanitizing, self.urls)

        # include un-sanitized URL for easy matching of
        #response to request URLs
        if urls[0] != self.url:
            urls.insert(0, self.url)

        return urls


def get_redirect_chain(url):
    collector = RedirectCollector(url)
    request = HeadRequest(url)
    request.add_header('User-Agent', USER_AGENT)
    opener = urllib2.build_opener(collector)
    r = opener.open(request)

    urls = collector.get_redirects()
    if collector.permanent_redirect:
        urls.append(collector.permanent_redirect)

    return urls


def basic_sanitizing(url):
    """
    does basic sanitizing through urlparse and additionally converts the netloc to lowercase
    """
    r = urlparse.urlsplit(url)
    netloc = r.netloc.lower()
    r2 = urlparse.SplitResult(r.scheme, netloc, r.path or '/', r.query, r.fragment)
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
