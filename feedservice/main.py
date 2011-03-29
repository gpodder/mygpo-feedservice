from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import feeddownloader


def main():

    endpoints = [
        ('/parse', feeddownloader.Parser),
    ]

    application = webapp.WSGIApplication(endpoints)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
