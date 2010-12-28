from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import feeddownloader
import simplejson as json

class MainPage(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('Hello, webapp World!')

class Parse(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        urls = self.request.get_all('url')
        inline_logo = self.is_set('inline_logo')

        if urls:
            podcasts = [feeddownloader.parse_feed(url, inline_logo) for url in urls]
            pretty = json.dumps(podcasts, sort_keys=True, indent=4)
            self.response.out.write(pretty)
        else:
            self.response.set_status(400)
            self.response.out.write('parameter url missing')

    def is_set(self, param, default='0'):
        try:
            return int(self.request.get(param, default))
        except:
            return 0

application = webapp.WSGIApplication([
                                      ('/',      MainPage),
                                      ('/parse', Parse)
                                     ],
                                     debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
