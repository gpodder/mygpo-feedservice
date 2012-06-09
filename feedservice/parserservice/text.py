import re
from htmlentitydefs import entitydefs
from functools import partial


try:
    import html2text
except ImportError:
    html2text = None



def get_text_processor(s):
    processing = TEXT_PROCESSORS.get(s, lambda x: x)
    return partial(apply_text_processing, processing)


def apply_text_processing(processing, obj):
    """ recursively applies the text processing to obj """

    if isinstance(obj, basestring):
        return processing(obj)

    elif isinstance(obj, list):
        return [apply_text_processing(processing, x) for x in obj]

    return obj



# taken from gpodder.util
def remove_html_tags(html):
    """
    Remove HTML tags from a string and replace numeric and
    named entities with the corresponding character, so the
    HTML text can be displayed in a simple text view.
    """
    if html is None:
        return None

    # If we would want more speed, we could make these global
    re_strip_tags = re.compile('<[^>]*>')
    re_unicode_entities = re.compile('&#(\d{2,4});')
    re_html_entities = re.compile('&(.{2,8});')
    re_newline_tags = re.compile('(<br[^>]*>|<[/]?ul[^>]*>|</li>)', re.I)
    re_listing_tags = re.compile('<li[^>]*>', re.I)

    result = html

    # Convert common HTML elements to their text equivalent
    result = re_newline_tags.sub('\n', result)
    result = re_listing_tags.sub('\n * ', result)
    result = re.sub('<[Pp]>', '\n\n', result)

    # Remove all HTML/XML tags from the string
    result = re_strip_tags.sub('', result)
    # Convert numeric XML entities to their unicode character
    result = re_unicode_entities.sub(lambda x: unichr(int(x.group(1))), result)

    # Convert named HTML entities to their unicode character
    result = re_html_entities.sub(lambda x: unicode(entitydefs.get(x.group(1),''), 'iso-8859-1'), result)

    # Convert more than two newlines to two newlines
    result = re.sub('([\r\n]{2})([\r\n])+', '\\1', result)

    return result.strip()


def convert_markdown(s):
    if html2text is None:
        return s

    print 'converting %s to markdown: %s' % (s, html2text.html2text(s))
    return html2text.html2text(s).strip()


TEXT_PROCESSORS = {
    "strip_html": remove_html_tags,
    "markdown": convert_markdown,
    "none": lambda x: x
}
