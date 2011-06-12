import os

from django.conf.urls.defaults import *
from django.views.generic.simple import direct_to_template


urlpatterns = patterns('',
    (r'^$',             direct_to_template, {'template': 'index.html'}),
    (r'^media/(?P<path>.*)$', 'django.views.static.serve',
                       {'document_root': os.path.abspath('%s/../htdocs/media/' % os.path.dirname(__file__))}),
    (r'^parse$',          'feedservice.parserservice.views.parse'),
    (r'^subscribe$',      'feedservice.pubsubhubbub.views.subscribe'),
)
