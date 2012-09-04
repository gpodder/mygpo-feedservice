# -*- coding: utf-8 -*-
#

import re
import logging

import Image
import StringIO

from feedservice import urlstore
from feedservice import httputils
from feedservice.utils import flatten, longest_substr
from feedservice.parse import mimetype
from feedservice.parse.bitlove import get_bitlove_torrent



class Feed(object):
    """ A parsed Feed """

    def get_logo_inline(self):
        """ Fetches the feed's logo and returns its data URI """

        if not self.inline_logo:
            return None

        logo_url = self.get_logo_url()

        if not logo_url:
            return None

        try:
            url, content, last_mod_up, last_mod_utc, etag, content_type, \
                length = urlstore.get_url(logo_url)

        except Exception, e:
            msg = 'could not fetch feed logo %(logo_url)s: %(msg)s' % \
                dict(logo_url=logo_url, msg=str(e))
            self.add_warning('fetch-logo', msg)
            logging.info(msg)
            return None

        # TODO: uncomment
        #if last_mod_up and mod_since_up and last_mod_up <= mod_since_up:
        #    return None

        mimetype = mimetype.get_mimetype(None, url)

        transform_args = dict(size=self.scale_to, img_format=self.logo_format)

        if any(transform_args.values()):
            content, mimetype = self.transform_image(content, mimetype, **transform_args)

        return httputils.get_data_uri(content, mimetype)


    @staticmethod
    def transform_image(content, mimetype, size, img_format):
        """
        Transforms (resizes, converts) the image and returns
        the resulting bytes and mimetype
        """

        content_io = StringIO.StringIO(content)
        img = Image.open(content_io)

        try:
            size = int(size)
        except (ValueError, TypeError):
            size = None

        if img.mode not in ('RGB', 'RGBA'):
            img = im.convert('RGB')

        if img_format:
            mimetype = 'image/%s' % img_format
        else:
            img_format = mimetype[mimetype.find('/')+1:]

        if size:
            img = img.resize((size, size), Image.ANTIALIAS)


        # If it's a RGBA image, composite it onto a white background for JPEG
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size)
            draw = ImageDraw.Draw(background)
            draw.rectangle((-1, -1, img.size[0]+1, img.size[1]+1), \
                    fill=(255, 255, 255))
            del draw
            img = Image.composite(img, background, img)

        io = StringIO.StringIO()
        img.save(io, img_format.upper())
        content = io.getvalue()

        return content, mimetype

