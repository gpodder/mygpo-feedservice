from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import urllib
import feeddownloader
import simplejson as json

class MainPage(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('Hello, webapp World!')

class Parse(webapp.RequestHandler):

    def post(self):
        return self.get()

    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        urls = self.request.get_all('url')
        urls = map(urllib.unquote, urls)
        inline_logo = self.get_int('inline_logo')
        scale_to = self.get_int('scale_logo', None)
        modified = self.request.headers.get('If-Modified-Since', None)

        if urls:
            podcasts, last_modified = feeddownloader.parse_feeds(urls, inline_logo, scale_to, modified)
            pretty = json.dumps(podcasts, sort_keys=True, indent=4)

            if last_modified:
                from email import utils
                import time
                self.response.headers.add_header('Last-Modified', utils.formatdate(time.mktime(last_modified)))

            self.response.out.write(pretty)

        else:
            self.response.set_status(400)
            self.response.out.write('parameter url missing')

    def get_int(self, param, default=0):
        try:
            return int(self.request.get(param, default))
        except:
            return default


application = webapp.WSGIApplication([
                                      ('/',      MainPage),
                                      ('/parse', Parse)
                                     ],
                                     debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
