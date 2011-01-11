import urllib2
import urlparse

class RedirectCollector(urllib2.HTTPRedirectHandler):
    """Collects all seen (intermediate) redirects for a HTTP request"""

    def __init__(self, *args, **kwargs):
        self.urls = []

    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        self.urls.append(newurl)
        return urllib2.HTTPRedirectHandler.redirect_request(self, req, fp, code, msg, hdrs, newurl)


def get_redirects(url):
    """ Returns the complete redirect chain, starting from url """
    collector = RedirectCollector()
    collector.urls.append(url)
    opener = urllib2.build_opener(collector)
    opener.open(url)
    urls = map(basic_sanitizing, collector.urls)

    # include un-sanitized URL for easy matching of
    #response to request URLs
    if urls[0] != url:
        urls = [url] + urls

    return urls


def basic_sanitizing(url):
    """
    does basic sanitizing through urlparse and additionally converts the netloc to lowercase
    """
    r = urlparse.urlsplit(url)
    netloc = r.netloc.lower()
    r2 = urlparse.SplitResult(r.scheme, netloc, r.path or '/', r.query, r.fragment)
    return r2.geturl()

