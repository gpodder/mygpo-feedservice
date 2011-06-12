from couchdbkit.ext.django.schema import *


class SubscriptionError(Exception):
    pass


class SubscribedFeed(Document):
    url = StringProperty()
    verify_token = StringProperty()
    mode = StringProperty()
    verified = BooleanProperty()


    @classmethod
    def for_url(cls, url):
        r = cls.view('pubsubhubbub/subscriptions_by_url',
                key          = url,
                include_docs = True,
            )
        return r.first() if r else None
