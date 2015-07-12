import webapp2
import sys
import os
sys.path.append(os.path.abspath("rssReader"))
import logging
import util
import rssParser

class update_all(util.pageHandler):          
      def get(self):
          logging.error("scheduled update all every 24 hours")
          rssParser.scheduled_update_all_feed()   
          
#deploy configurations, page connection
app = webapp2.WSGIApplication([('/scheduledTasks/rss', update_all),
                               ],
                              debug=True)