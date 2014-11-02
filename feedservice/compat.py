try:  # Python 3
    from urllib.error import URLError, HTTPError
    from http.client import InvalidURL, BadStatusLine
    from urllib.request import build_opener, HTTPRedirectHandler, Request
    from html.entities import entitydefs
    from html.parser import HTMLParseError
    from urllib.parse import (parse_qs, unquote, urlsplit, quote, quote_plus,
        urlunsplit, SplitResult)
    from io import StringIO

except ImportError:
    from http.client import InvalidURL, BadStatusLine
    from urllib2 import build_opener, HTTPRedirectHandler, Request, HTTPError
    from htmlentitydefs import entitydefs
    from HTMLParser import HTMLParseError
    from urlparse import parse_qs, urlsplit, urlunsplit, SplitResult
    from urllib import unquote, quote, quote_plus
    from StringIO import StringIO
