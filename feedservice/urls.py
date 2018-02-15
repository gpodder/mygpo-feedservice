from django.urls import path

from feedservice.webservice.views import ParseView, IndexView

urlpatterns = [

    path('',            IndexView.as_view(),     name='index'),

    path('parse',       ParseView.as_view(),     name='parse'),

]
