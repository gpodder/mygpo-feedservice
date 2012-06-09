import hashlib

from django.core.cache import cache

from feedservice.urlstore.models import URLObject


class URLObjectCache(object):

    def get_key(url):
        return hashlib.sha1(url).hexdigest()


    def set(self, obj):
        key = self.get_key(obj.url)
        obj.save()
        cache.set(key, obj)


    def get(self, url):
        key = self.get_key(obj.url)
        return cache.get(key) or URLObject.for_url(url)
