from json import json

from feedservice.parse.models import ParsedObject


class ObjectEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, ParsedObject):
            return self.to_dict(obj)

        return json.JSONEncoder.default(self, obj)


    def to_dict(self, obj):
        """
        Parses a feed and returns its JSON object, a list of urls that refer to
        this feed, an outgoing redirect and the timestamp of the last modification
        of the feed
        """

        d = {}
        for key in dir(obj):

            if key.startswith('_'):
                continue

            val = getattr(obj, key)
            if callable(val):
                continue

            d[key] = getattr(obj, key)

        return d

