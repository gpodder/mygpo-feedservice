#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# PubSubHubbub subscriber for mygpo-feedservice
#
#

import urllib, urllib2, urlparse, logging
from datetime import timedelta

from google.appengine.ext import webapp, db

import urlstore


# increased expiry time for subscribed feeds
INCREASED_EXPIRY = timedelta(days=7)


class SubscriptionError(Exception):
    pass


class SubscribedFeed(db.Model):
    url = db.StringProperty()
    verify_token = db.StringProperty()
    mode = db.StringProperty()
    verified = db.BooleanProperty()



class Subscriber(webapp.RequestHandler):
    """ request handler for pubsubhubbub subscriptions """


    def get(self):
        """ Callback used by the Hub to verify the subscription request """

        # received arguments: hub.mode, hub.topic, hub.challenge,
        # hub.lease_seconds, hub.verify_token
        mode          = self.request.get('hub.mode')
        feed_url      = self.request.get('hub.topic')
        challenge     = self.request.get('hub.challenge')
        lease_seconds = self.request.get('hub.lease_seconds')
        verify_token  = self.request.get('hub.verify_token')

        logging.debug('received subscription-parameters: mode: %(mode)s, ' +
                'topic: %(topic)s, challenge: %(challenge)s, lease_seconds: ' +
                '%(lease_seconds)s, verify_token: %(verify_token)s' % \
                dict(mode=mode, topic=feed_url, challenge=challenge,
                     lease_seconds=lease_seconds, verify_token=verify_token))

        subscription = Subscriber.get_subscription(feed_url)

        if subscription is None:
            logging.warn('subscription does not exist')
            self.response.set_status(404)
            return

        if subscription.mode != mode:
            logging.warn('invalid mode, %s expected' %
                subscription.mode)
            self.response.set_status(404)
            return

        if subscription.verify_token != verify_token:
            logging.warn('invalid verify_token, %s expected' %
                subscribe.verify_token)
            self.response.set_status(404)
            return

        subscription.verified = True
        subscription.put()

        logging.info('subscription confirmed')
        self.response.set_status(200)
        self.response.out.write(challenge)



    def post(self):
        """ Callback to notify about a feed update """

        feed_url = self.request.get('url')

        logging.info('received notification for %s' % feed_url)

        subscription = Subscriber.get_subscription(feed_url)

        if subscription is None:
            logging.warn('no subscription for this URL')
            self.response.set_status(400)
            return

        if subscription.mode != 'subscribe':
            logging.warn('invalid subscription mode: %s' % subscription.mode)
            self.response.set_status(400)
            return

        if not subscription.verified:
            logging.warn('the subscription has not yet been verified')
            self.response.set_status(400)
            return

        # The changed parts in the POST data are ignored -- we simply fetch the
        # whole feed.
        # It is stored in memcache with all the normal (unsubscribed) feeds
        # but with increased expiry time.
        urlstore.fetch_url(feed_url, add_expires=INCREASED_EXPIRY)

        self.response.set_status(200)


    @staticmethod
    def get_subscription(feedurl):
        q = SubscribedFeed.all()
        q.filter('url =', feedurl)
        return q.get()


    @staticmethod
    def subscribe(feedurl, huburl):
        """ Subscribe to the feed at a Hub """

        logging.info('subscribing for %(feed)s at %(hub)s' %
            dict(feed=feedurl, hub=huburl))

        verify_token = Subscriber.generate_verify_token()

        mode = 'subscribe'
        verify = 'sync'

        data = {
            "hub.callback":     Subscriber.get_callback_url(feedurl),
            "hub.mode":         mode,
            "hub.topic":        feedurl,
            "hub.verify":       verify,
            "hub.verify_token": verify_token,
        }

        subscription = Subscriber.get_subscription(feedurl)
        if subscription is not None:

            if subscription.mode == mode:
                logging.info('subscription already exists')
                return

            else:
                logging.info('subscription exists but has wrong mode: ' +
                    'old: %(oldmode)s, new: %(newmode)s. Overwriting.' %
                    dict(oldmode=subscription.mode, newmode=mode))

        else:
            subscription = SubscribedFeed()

        subscription.url = feedurl
        subscription.verify_token = verify_token
        subscription.mode = mode
        subscription.verified = False
        subscription.put()

        data = urllib.urlencode(data)
        logging.debug('sending request: %s' % repr(data))

        try:
            resp = urllib2.urlopen(huburl, data)
        except urllib2.HTTPError as e:
            msg = 'Could not send subscription to Hub: HTTP Error %d' % e.code
            logging.warn(msg)
            raise SubscriptionError(msg)
        except Exception as e:
            msg = 'Could not send subscription to Hub: %s' % repr(e)
            logging.warn(msg)
            raise SubscriptionError(msg)


        status = resp.code
        if status != 204:
            logging.error('received incorrect status %d' % status)
            raise SubscriptionError('Subscription has not been accepted by the Hub')



    @staticmethod
    def get_callback_url(feedurl):
        import settings
        url = urlparse.urljoin(settings.BASE_URL, 'subscribe')

        param = urllib.urlencode([('url', feedurl)])
        return '%s?%s' % (url, param)


    @staticmethod
    def generate_verify_token(length=32):
        import random, string
        return "".join(random.sample(string.letters+string.digits, length))
