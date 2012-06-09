#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# PubSubHubbub subscriber for mygpo-feedservice
#
#

import logging
from datetime import timedelta

from django.http import HttpResponseNotFound
from django.views.generic.base import View
from couchdbkit.ext.django import *

from feedservice import urlstore
from feedservice.pubsubhubbub.models import SubscriptionError, SubscribedFeed


logger = logging.getLogger(__name__)


# increased expiry time for subscribed feeds
INCREASED_EXPIRY = timedelta(days=7)


class SubscribeView(View):
    """ Endpoint for Pubsubhubbub subscriptions """

    def get(request):
        """ Callback used by the Hub to verify the subscription request """

        # received arguments: hub.mode, hub.topic, hub.challenge,
        # hub.lease_seconds, hub.verify_token
        mode          = request.GET.get('hub.mode')
        feed_url      = request.GET.get('hub.topic')
        challenge     = request.GET.get('hub.challenge')
        lease_seconds = request.GET.get('hub.lease_seconds')
        verify_token  = request.GET.get('hub.verify_token')

        logger.debug(('received subscription-parameters: mode: %(mode)s, ' +
                'topic: %(topic)s, challenge: %(challenge)s, lease_seconds: ' +
                '%(lease_seconds)s, verify_token: %(verify_token)s') % \
                dict(mode=mode, topic=feed_url, challenge=challenge,
                     lease_seconds=lease_seconds, verify_token=verify_token))

        subscription = SubscribedFeed.for_url(feed_url)

        if subscription is None:
            logger.warn('subscription does not exist')
            return HttpResponseNotFound()

        if subscription.mode != mode:
            logger.warn('invalid mode, %s expected' %
                subscription.mode)
            return HttpResponseNotFound()

        if subscription.verify_token != verify_token:
            logger.warn('invalid verify_token, %s expected' %
                subscribe.verify_token)
            return HttpResponseNotFound()

        subscription.verified = True
        subscription.save()

        logger.info('subscription confirmed')
        return HttpResponse(challenge)


    def post(request):
        """ Callback to notify about a feed update """

        feed_url = request.GET.get('url')

        logger.info('received notification for %s' % feed_url)

        subscription = SubscribedFeed.for_url(feed_url)

        if subscription is None:
            logger.warn('no subscription for this URL')
            return HttpResponse(status=400)

        if subscription.mode != 'subscribe':
            logger.warn('invalid subscription mode: %s' % subscription.mode)
            return HttpResponse(status=400)

        if not subscription.verified:
            logger.warn('the subscription has not yet been verified')
            return HttpResponse(status=400)

        # The changed parts in the POST data are ignored -- we simply fetch the
        # whole feed.
        # It is stored in memcache with all the normal (unsubscribed) feeds
        # but with increased expiry time.
        urlstore.fetch_url(feed_url, add_expires=INCREASED_EXPIRY)

        return HttpResponse(status=200)
