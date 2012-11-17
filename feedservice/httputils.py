import urllib2
import urlparse


USER_AGENT = 'mygpo-feedservice +http://feeds.gpodder.net/'


class PermanentRedirectException(Exception):
    """ Raised on a permanent redirect, if it should not be followed """


class HeadRequest(urllib2.Request):
    def get_method(self):
        return "HEAD"


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
    import re
    import collections

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
