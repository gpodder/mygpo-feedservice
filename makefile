PYTHON=python2.5
APPENGINE_SDK=google_appengine
APPDIR=feedservice
APPID=mygpo-feedservice


runserver:
	${PYTHON} ${APPENGINE_SDK}/dev_appserver.py --clear_datastore ${APPDIR}

shell:
	cd ${APPDIR} && ${PYTHON} appengine_console.py ${APPID}

deploy:
	${PYTHON} ${APPENGINE_SDK}/appcfg.py update ${APPDIR}

.PHONY: runserver deploy shell
