#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import urllib
import time
import email.utils
import cgi
from datetime import datetime

from django.http import HttpResponse
from django.shortcuts import render
from django.contrib.sites.models import get_current_site
from django.views.generic.base import View

from feedservice.httputils import select_matching_option
from feedservice.parse import parse_feeds
from feedservice.json import json
from feedservice.parse.text import get_text_processor
from feedservice.urlstore.cache import URLObjectCache


class ParseView(View):
    """ Parser Endpoint """

    def get(self, request):

        urls = map(urllib.unquote, request.GET.getlist('url'))

        parse_args = dict(
            inline_logo = request.GET.get('inline_logo', default=0),
            scale_to    = request.GET.get('scale_logo',  default=0),
            logo_format = request.GET.get('logo_format', None),
        )

        # support deprecated param 'strip_html'; newer 'process_text' overrides
        if int(request.GET.get('strip_html', 0)):
            process_text = get_text_processor('strip_html')

        process_text  = get_text_processor(request.GET.get('process_text', ''))

        if request.GET.get('use_cache', default=1):
            cache = URLObjectCache()
        else:
            cache = None

        mod_since_utc = request.META.get('HTTP_IF_MODIFIED_SINCE', None)
        accept = request.META.get('HTTP_ACCEPT', 'application/json')

        base_url = request.build_absolute_uri('/')

        if urls:
            podcasts = parse_feeds(urls, mod_since_utc, base_url, process_text,
                    cache, **parse_args)

            last_mod_utc = datetime.utcnow()
            response = self.send_response(request, podcasts, last_mod_utc, accept)

        else:
            response = HttpResponse()
            response.status_code = 400
            response.write('parameter url missing')

        return response


    def send_response(self, request, podcasts, last_mod_utc, accepted_formats):

        SUPPORTED_FORMATS = ['text/html', 'application/json']

        fmt = select_matching_option(SUPPORTED_FORMATS, accepted_formats)

        if fmt in (None, 'application/json'): #serve json as default
            content_type = 'application/json'
            response = HttpResponse()

            dense_json = json.dumps(podcasts, sort_keys=True,
                    indent=None, separators=(',', ':'))
            response.write(dense_json)

            last_mod_time = time.mktime(last_mod_utc.timetuple())
            response['Last-Modified'] = email.utils.formatdate(last_mod_time)


        else:
            content_type = 'text/html'
            pretty_json = json.dumps(podcasts, sort_keys=True, indent=4)
            pretty_json = cgi.escape(pretty_json)
            response = render(request, 'pretty_response.html', {
                    'response': pretty_json,
                    'site': get_current_site(request),
                })

        response['Content-Type'] = content_type
        response['Vary'] = 'Accept, User-Agent, Accept-Encoding'

        return response
