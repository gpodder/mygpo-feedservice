from datetime import datetime
import base64

from couchdbkit.ext.django.schema import *


class URLObject(Document):
    url = StringProperty(required=True)
    urls = StringListProperty()
    content = StringProperty(required=False)
    etag = StringProperty(required=False)
    expires = DateTimeProperty(required=False)
    last_mod_up = DateTimeProperty(required=False)
    last_mod_utc = DateTimeProperty(required=False)
    content_type = StringProperty(required=False)
    length = IntegerProperty(required=False)
    permanent_redirect = StringProperty()

    def expired(self):
        return not self.expires or self.expires <= datetime.utcnow()

    def valid(self):
        return bool(self.content)

    def __repr__(self):
        return '%(url)s (%(etag)s, %(expires)s, %(last_mod_up)s)' % \
            dict(url=self.url, etag=self.etag,
                 expires=self.expires, last_mod_up=self.last_mod_up)


    def get_content(self):
        return base64.b64decode(self.content)


    @classmethod
    def for_url(cls, url):
        res = cls.view('urlstore/objects_by_url',
                key          = url,
                include_docs = True,
                limit        = 1,
            )
        return res.one() if res else None


    def changed_since(self, ts_utc):
        return not self.last_mod_utc or \
               not ts_utc or \
               self.last_mod_utc > ts_utc
