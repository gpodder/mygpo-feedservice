#
# Tries to import the best JSON module available
#

import sys


try:
    # If SimpleJSON is installed separately, it might be a recent version
    import simplejson as json
    JSONDecodeError = json.JSONDecodeError

except:
    print >> sys.stderr, 'simplejson not found'

    # Otherwise use json from the stdlib
    import json
    JSONDecodeError = ValueError
