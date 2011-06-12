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

from django.http import HttpResponseNotFound
from couchdbkit.ext.django import *

from feedservice import urlstore
from feedservice.pubsubhubbub.models import SubscriptionError, SubscribedFeed
from feedservice.pubsubhubbub import get_subscription


# increased expiry time for subscribed feeds
INCREASED_EXPIRY = timedelta(days=7)


def subscribe(request):

    if request.method == 'GET':
        """ Callback used by the Hub to verify the subscription request """

        # received arguments: hub.mode, hub.topic, hub.challenge,
        # hub.lease_seconds, hub.verify_token
        mode          = request.GET.get('hub.mode')
        feed_url      = request.GET.get('hub.topic')
        challenge     = request.GET.get('hub.challenge')
        lease_seconds = request.GET.get('hub.lease_seconds')
        verify_token  = request.GET.get('hub.verify_token')

        logging.debug(('received subscription-parameters: mode: %(mode)s, ' +
                'topic: %(topic)s, challenge: %(challenge)s, lease_seconds: ' +
                '%(lease_seconds)s, verify_token: %(verify_token)s') % \
                dict(mode=mode, topic=feed_url, challenge=challenge,
                     lease_seconds=lease_seconds, verify_token=verify_token))

        subscription = get_subscription(feed_url)

        if subscription is None:
            logging.warn('subscription does not exist')
            return HttpResponseNotFound()

        if subscription.mode != mode:
            logging.warn('invalid mode, %s expected' %
                subscription.mode)
            return HttpResponseNotFound()

        if subscription.verify_token != verify_token:
            logging.warn('invalid verify_token, %s expected' %
                subscribe.verify_token)
            return HttpResponseNotFound()

        subscription.verified = True
        subscription.save()

        logging.info('subscription confirmed')
        return HttpResponse(challenge)


    elif request.method == 'POST':
        """ Callback to notify about a feed update """

        feed_url = request.GET.get('url')

        logging.info('received notification for %s' % feed_url)

        subscription = get_subscription(feed_url)

        if subscription is None:
            logging.warn('no subscription for this URL')
            return HttpResponse(status=400)

        if subscription.mode != 'subscribe':
            logging.warn('invalid subscription mode: %s' % subscription.mode)
            return HttpResponse(status=400)

        if not subscription.verified:
            logging.warn('the subscription has not yet been verified')
            return HttpResponse(status=400)

        # The changed parts in the POST data are ignored -- we simply fetch the
        # whole feed.
        # It is stored in memcache with all the normal (unsubscribed) feeds
        # but with increased expiry time.
        urlstore.fetch_url(feed_url, add_expires=INCREASED_EXPIRY)

        return HttpResponse(status=200)
