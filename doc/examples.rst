Example Requests
================

Some example requests

* http://feeds.gpodder.net/parse?url=http://feeds.feedburner.com/linuxoutlaws&inline_logo=1&scale_logo=30
* http://feeds.gpodder.net/parse?url=http://youtube.com/rss/user/TEDtalksDirector/videos.rss
* http://feeds.gpodder.net/parse?url=http://soundcloud.com/scheibosan
* http://feeds.gpodder.net/parse?url=http://onapp1.orf.at/webcam/fm4/fod/soundpark.xspf
* http://feeds.gpodder.net/parse?url=http://leo.am/podcasts/floss&url=http://feeds.twit.tv/floss_video_large
* http://feeds.gpodder.net/parse?url=http://www.dancarlin.com/cswdc.xml&process_text=strip_html
* http://feeds.gpodder.net/parse?url=http://feeds.feedburner.com/linuxoutlaws

For executing requests from the commandline you can use ``curl``. ::

   SERVER=http://feeds.gpodder.net/parse
    curl --header "Accept: application/json" "$SERVER?url=http://feeds.feedburner.com/linuxoutlaws&inline_logo=1&scale_logo=30" #^
    curl --header "Accept: application/json" "$SERVER?url=http://youtube.com/rss/user/TEDtalksDirector/videos.rss" #^
