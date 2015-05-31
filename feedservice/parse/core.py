

class Parser(object):

    def __init__(self, url, resp):
        # resp is a file-like object as returned by urllib2.urlopen
        self.url = url
        self.resp = resp

    def get_etag(self):
        return self.resp.headers.get('etag')

    def get_last_modified(self):
        return self.resp.headers.get('last-modified')

    def get_new_location(self):
        if self.resp.status_code == 301 and self.url != self.resp.url:
            return self.resp.url
