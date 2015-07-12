import webapp2
import sys
import os
sys.path.append(os.path.abspath("wiki"))
from util import * #import utility python
import loginHandler
import logging
import wikiEntryHandler
import history
from google.appengine.api import memcache #memcache
from google.appengine.ext import db #gql database
from google.appengine.api import users


#this py file handles front page and all directing work
class WikiHandler(pageHandler):
    def get(self):
        user_logged_in_stat = False
        username = ""
        cookie = self.request.cookies.get('user_id')
        if cookie:
            cookie_user_id = int(cookie.split('|')[0])
            u = loginHandler.wiki_user_info.get_by_id(cookie_user_id)
            if (u):
                username = u.username
                user_logged_in_stat = True
            #logging.error("username = " + username) 
        #take first 100 words from list of words
        words = wikiEntryHandler.queue_to_list(wikiEntryHandler.queue_of_words)
        logging.debug("length of edited words = " + str(len(words))) 
        self.render('wiki_front_page.html',  user_logged_in_stat = user_logged_in_stat, username = username, words = words)       

#deploy configurations, page connection
app = webapp2.WSGIApplication([('/wiki/_edit/.*', wikiEntryHandler.wiki_edit_page),
                               ('/wiki/login', loginHandler.Signin_cookie),
                               ('/wiki/history', history.history), #user editing history
                               ('/wiki/logout', loginHandler.Signout_cookie),
                               ('/wiki/signup', loginHandler.Signup),
                               ('/wiki', WikiHandler),
                               (r'/wiki/_history/(.*)', history.page_history), #page edit history
                               ('/wiki/(.*)', wikiEntryHandler.wiki_entry_page),
                               ],
                              debug=True)
