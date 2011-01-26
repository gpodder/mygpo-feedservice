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
        urls = self.request.get_all('url')
        urls = map(urllib.unquote, urls)
        inline_logo = self.request.get_range('inline_logo', 0, 1, default=0)
        scale_to = self.request.get_range('scale_logo', 0, 1, default=0)
        strip_html = self.request.get_range('strip_html', 0, 1, default=0)
        use_cache = self.request.get_range('use_cache', 0, 1, default=1)
        modified = self.request.headers.get('If-Modified-Since', None)
        accept = self.request.headers.get('Accept', 'application/json')

        if urls:
            podcasts, last_modified = feeddownloader.parse_feeds(urls, inline_logo, scale_to, strip_html, modified, use_cache)
            self.send_response(podcasts, last_modified, accept)

        else:
            self.response.set_status(400)
            self.response.out.write('parameter url missing')


    def send_response(self, podcasts, last_modified, format):
        self.response.headers.add_header('Vary', 'Accept')

        if 'json' in format:
            content_type = 'application/json'
            content = json.dumps(podcasts, sort_keys=True, indent=None, separators=(',', ':'))
            from email import utils
            import time
            self.response.headers.add_header('Last-Modified', utils.formatdate(time.mktime(last_modified)))


        else:
            import cgi
            content_type = 'text/html'
            pretty_json = json.dumps(podcasts, sort_keys=True, indent=4)
            pretty_json = cgi.escape(pretty_json)
            content = """<html><head>
<link href="static/screen.css" type="text/css" rel="stylesheet" />
<link href="static/prettify.css" type="text/css" rel="stylesheet" />
<script type="text/javascript" src="static/prettify.js"></script>
</head><body onload="prettyPrint()"><h1>HTML Response</h1><p>This response is HTML formatted. To get just the JSON data for processing in your client, <a href="/#accept">send the HTTP Header <em>Accept: application/json</em></a>. <a href="/">Back to the Documentation</a></p><pre class="prettyprint">%s</pre></body></html>""" % pretty_json

        self.response.headers['Content-Type'] = content_type
        self.response.out.write(content)


application = webapp.WSGIApplication([
                                      ('/',      MainPage),
                                      ('/parse', Parse)
                                     ],
                                     debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
