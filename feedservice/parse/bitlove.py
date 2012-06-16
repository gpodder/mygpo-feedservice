import urllib
from feedservice.json import json


"""
Queries the bitlove.org API
https://bitlove.org/help/podcaster/api
"""

BITLOVE_API='http://api.bitlove.org/by-enclosure.json?'

def get_bitlove_torrent(urls):

    params = [ ('url', url) for url in urls]
    query = urllib.urlencode(params)

    r = urllib.urlopen(BITLOVE_API + query)
    resp = json.loads(r.read())

    for info in resp.values():

        # no data for this url
        if not info:
            continue

        for source in info.get('sources', []):
            torrent = source.get('torrent', None)

            if torrent:
                return {'torrent': torrent}


