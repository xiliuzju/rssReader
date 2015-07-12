import webapp2
import sys
import os
sys.path.append(os.path.abspath("rssReader"))
from util import * #import utility python
from loginHandler import *
import logging
import rssParser
from google.appengine.api import memcache #memcache
from google.appengine.ext import db #gql database
from google.appengine.api import users
import json

#configuration for the main page
class rssHandler(pageHandler):
    def get(self, *url):
        user_logged_in_stat = False
        cookie = self.request.cookies.get('user_id')
        
        if cookie:
            username = get_user_name(self)
            if (username):
                logging.error("user logged in, username =" +  username)
                user_logged_in_stat = True
                
                #get manage feed status
                manage_feed_switch = False
                delete_feed = ""
                if self.request.url.endswith("?manage=true"):
                    manage_feed_switch = True
                if (len(self.request.url.split("?delete=")) >= 2):
                    delete_feed = self.request.url.split("?delete=")[1]
                    rssParser.del_feed(username, delete_feed)
                
                #get error message
                error_message=""
                if (len(self.request.url.split("?error=")) >= 2):
                    error_message = self.request.url.split("?error=")[1]
                    error_message = " ".join(error_message.split("_"))
                
                #generate list of entries for selected rss feed
                #parse the url
                content = []
                selectedFeed = ""
                if (len(self.request.url.split("?feed=")) >= 2):
                    selectedFeed = self.request.url.split("?feed=")[1]
                    content = rssParser.get_content_from_feed(selectedFeed, username)
                    if not content:
                        content = []
             
                #generate list of rss feeds
                feedList = rssParser.feeds_to_list(username)
                                   
                #generate page
                self.render('rss_front_page_bootstrap.html', manage_feed_switch = manage_feed_switch, delete_feed = delete_feed, 
                            username = username, feedList = feedList, content = content, user_logged_in_stat = user_logged_in_stat, 
                            selectedFeed = selectedFeed, error_message = error_message)       
             
        else:
            logging.error("did not detect username in cookie")
            self.redirect('/rss/login')
        
    def post(self):
        #get the feed
         feed = self.request.get('input_feed')
         username = get_user_name(self)
         logging.error(feed+username)
         feed = parse_rss_feed(feed)
         if feed:
             logging.error(feed)
             rssParser.add_feed(username, feed)
             self.redirect('/rss?feed='+feed)
         else:
             self.redirect('/rss?error=invalid_RSS_URL') #still, use url to pass the error message
             
#flush all, bascially resets memcache and db
class flush_all(pageHandler):
    def get(self):
        memcache.flush_all()
        rss = rssParser.rss_user_data.all()
        for p in rss:
            p.delete()
        feed = rssParser.feed_db_info.all()
        for p in feed:
            p.delete()
        self.redirect('/rss/signup') 

#debug, update all
class update_all(pageHandler):          
      def get(self):
          logging.error("debug, update all feeds")
          rssParser.scheduled_update_all_feed() 
          self.redirect('/rss')   

#deploy configurations, page connection
app = webapp2.WSGIApplication([('/rss/login', Signin_cookie),
                               ('/rss/logout', Signout_cookie),
                               ('/rss/signup', Signup),
							   ('/rss', rssHandler),
                               ('/rss/flush_all', flush_all),
                               ('/rss/update_all', update_all)
                               ],
                              debug=True)
