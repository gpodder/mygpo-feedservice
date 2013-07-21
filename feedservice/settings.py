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
PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

STATIC_ROOT = 'staticfiles'
STATIC_URL = '/static/'

STATICFILES_DIRS = (
    os.path.join(PROJECT_DIR, 'htdocs', 'media'),
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = os.getenv('MYGPOFS_SECRET_KEY', '')

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

WSGI_APPLICATION = 'feedservice.wsgi.application'

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

FLATTR_THING = os.getenv('MYGPOFS_FLATTR_THING', '')

ALLOWED_HOSTS = filter(None, os.getenv('MYGPOFS_ALLOWED_HOSTS', '').split(';'))


# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error when DEBUG=False.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}


try:
    from settings_prod import *
except ImportError, e:
    import sys
    print >> sys.stderr, 'create settings_prod.py with your customized settings'
