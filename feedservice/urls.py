import os

from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template
from django.views.generic import TemplateView
from django.conf import settings

from feedservice.parserservice.views import ParseView
from feedservice.pubsubhubbub.views import SubscribeView


urlpatterns = patterns('',
    (r'^$',               TemplateView.as_view(template_name='index.html')),
    (r'^media/(?P<path>.*)$', 'django.views.static.serve', {'document_root': settings.MEDIA_ROOT}),
    (r'^parse$',          ParseView.as_view()),
    (r'^subscribe$',      SubscribeView.as_view()),
)
