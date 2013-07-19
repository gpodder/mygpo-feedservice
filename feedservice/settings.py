# -*- coding: utf-8 -*-


import os, os.path

def bool_env(val, default):
    """Replaces string based environment values with Python booleans"""

    if not val in os.environ:
        return default

    return True if os.environ.get(val) == 'True' else False


DEBUG = bool_env('MYGPOFS_DEBUG', True)
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    ('Stefan Kögl', 'stefan@skoegl.net'),
)

MANAGERS = ADMINS

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'UTC'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True


# Static asset configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.join(BASE_DIR, '../htdocs')

STATIC_ROOT = 'static'
STATIC_URL = '/media/'

STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'media'),
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'm6jkg5lzard@k^p(wui4gtx_zu4s=26c+c0bk+k1xsik6+derf'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.app_directories.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
)

ROOT_URLCONF = 'feedservice.urls'

TEMPLATE_DIRS = (
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'feedservice.parse',
    'feedservice.urlstore',
    'feedservice.webservice',
)

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

BASE_URL='http://localhost:8080/'

import dj_database_url
DATABASES = {'default': dj_database_url.config()}

SOUNDCLOUD_CONSUMER_KEY = os.getenv('MYGPOFS_SOUNDCLOUD_CONSUMER_KEY', '')

FLATTR_THING = ''

ALLOWED_HOSTS = filter(None, os.getenv('MYGPOFS_ALLOWED_HOSTS', '').split(';'))


try:
    from settings_prod import *
except ImportError, e:
    import sys
    print >> sys.stderr, 'create settings_prod.py with your customized settings'
