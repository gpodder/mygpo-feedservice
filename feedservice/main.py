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
        url = self.request.get('url')
        if url:
            podcast = feeddownloader.parse_feed(url)
            pretty = json.dumps(podcast, sort_keys=True, indent=4)
            self.response.out.write(pretty)
        else:
            self.response.set_status(400)
            self.response.out.write('parameter url missing')

application = webapp.WSGIApplication([
                                      ('/',      MainPage),
                                      ('/parse', Parse)
                                     ],
                                     debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
