from django.conf.urls import *

from feedservice.webservice.views import ParseView, IndexView

urlpatterns = patterns('',
    (r'^$',               IndexView.as_view()),
 url(r'^parse$',          ParseView.as_view(),     name='parse'),
)
