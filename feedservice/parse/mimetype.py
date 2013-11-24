import mimetypes
from collections import Counter


# If 20% of the episodes of a podcast are of a given type,
# then the podcast is considered to be of that type, too
TYPE_THRESHOLD=.2


CONTENT_TYPES = ('image', 'audio', 'video')

def get_podcast_types(episode_mimetypes):
    """Returns the types of a podcast

    A podcast is considered to be of a given types if the ratio of episodes that are of that type equals TYPE_THRESHOLD
    """

    episode_types = map(get_type, episode_mimetypes)
    episode_types = filter(None, episode_types)
    episode_types = Counter(episode_types)

    max_episodes = sum(episode_types.itervalues())
    l = episode_types.items()
    l.sort(key=lambda x: x[1], reverse=True)

    return [x[0] for x in filter(lambda x: max_episodes / float(x[1]) >= TYPE_THRESHOLD, l)]


def get_type(mimetype):
    """Returns the simplified type for the given mimetype

    All "wanted" mimetypes are mapped to one of audio/video/image
    Everything else returns None
    """
    if not mimetype:
        return None

    if '/' in mimetype:
        category, type = mimetype.split('/', 1)
        if category in ('audio', 'video', 'image'):
            return category
        elif type == 'ogg':
            return 'audio'
        elif type == 'x-youtube':
            return 'video'
        elif type == 'x-vimeo':
            return 'vimeo'
    return None


def get_mimetype(mimetype, url):
    """Returns the mimetype; if None is given it tries to guess it"""

    TORRENT_EXT='.torrent'

    # handle torrent files
    if url[-len(TORRENT_EXT):] == TORRENT_EXT:
        # by removing the extension
        url = url[:len(url)-len(TORRENT_EXT)]
        # and resetting the mimetype, so it is guessed below
        mimetype = None

    if not mimetype:
        mimetype, _encoding = mimetypes.guess_type(url)

    return mimetype

