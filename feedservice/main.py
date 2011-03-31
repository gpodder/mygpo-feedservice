from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import feeddownloader
import pubsubhubbub


def main():

    endpoints = [
        ('/parse', feeddownloader.Parser),
        ('/subscribe',  pubsubhubbub.Subscriber)
    ]

    application = webapp.WSGIApplication(endpoints)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
