


class Parser(object):


    def __init__(self, url, resp):
        # resp is a file-like object as returned by urllib2.urlopen
        self.resp = resp


    def get_etag(self):
        return self.resp.info().getheader('etag')


    def get_last_modified(self):
        return self.resp.info().getheader('last-modified')


    def get_new_location(self):
        return getattr(self.resp, 'new_location', None)
