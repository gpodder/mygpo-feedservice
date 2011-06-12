from datetime import datetime

from couchdbkit.ext.django.schema import *


class URLObject(Document):
    url = StringProperty(required=True)
    content = StringProperty(required=False)
    etag = StringProperty(required=False)
    expires = DateTimeProperty(required=False)
    last_mod_up = DateTimeProperty(required=False)
    last_mod_utc = DateTimeProperty(required=False)

    def expired(self):
        return not self.expires or self.expires <= datetime.utcnow()

    def valid(self):
        return len(self.content) > 0

    def __repr__(self):
        return '%(url)s (%(etag)s, %(expires)s, %(last_mod_up)s)' % \
            dict(url=self.url, etag=self.etag,
                 expires=self.expires, last_mod_up=self.last_mod_up)
