#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# PubSubHubbub subscriber for mygpo-feedservice
#
#

import urllib
import urllib2
import urlparse
import logging
from datetime import timedelta

from couchdbkit.ext.django import *

from feedservice import urlstore
from feedservice.pubsubhubbub.models import SubscriptionError, SubscribedFeed


# increased expiry time for subscribed feeds
INCREASED_EXPIRY = timedelta(days=7)



def subscribe(feedurl, huburl, base_url):
    """ Subscribe to the feed at a Hub """

    logging.info('subscribing for %(feed)s at %(hub)s' %
        dict(feed=feedurl, hub=huburl))

    verify_token = generate_verify_token()

    mode = 'subscribe'
    verify = 'sync'

    data = {
        "hub.callback":     get_callback_url(feedurl, base_url),
        "hub.mode":         mode,
        "hub.topic":        feedurl,
        "hub.verify":       verify,
        "hub.verify_token": verify_token,
    }

    subscription = SubscribedFeed.for_url(feedurl)
    if subscription is not None:

        if subscription.mode == mode:
            if subscription.verified:
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
    subscription.save()

    data = urllib.urlencode(data)
    logging.debug('sending request: %s' % repr(data))

    resp = None

    try:
        resp = urllib2.urlopen(huburl, data)
    except urllib2.HTTPError, e:
        if e.code != 204: # we actually expect a 204 return code
            msg = 'Could not send subscription to Hub: HTTP Error %d' % e.code
            logging.warn(msg)
            raise SubscriptionError(msg)
    except Exception, e:
        raise
        msg = 'Could not send subscription to Hub: %s' % repr(e)
        logging.warn(msg)
        raise SubscriptionError(msg)


    if resp:
        status = resp.code
        if status != 204:
            logging.error('received incorrect status %d' % status)
            raise SubscriptionError('Subscription has not been accepted by the Hub')



def get_callback_url(feedurl, base_url):
    url = urlparse.urljoin(base_url, 'subscribe')

    param = urllib.urlencode([('url', feedurl)])
    return '%s?%s' % (url, param)


def generate_verify_token(length=32):
    import random
    import string
    return "".join(random.sample(string.letters+string.digits, length))
