PYTHON=python2.5
APPENGINE_SDK=google_appengine
APPDIR=feedservice


runserver:
	${PYTHON} ${APPENGINE_SDK}/dev_appserver.py ${APPDIR}

deploy:
	${PYTHON} ${APPENGINE_SDK}/appcfg.py update ${APPDIR}

.PHONY: runserver deploy
