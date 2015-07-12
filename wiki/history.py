import webapp2
from google.appengine.ext import db #gql database
from google.appengine.api import users
from util import * #import utility python
import loginHandler
import wikiEntryHandler

class history_info(db.Model):
    username = db.StringProperty(required = True)
    item = db.StringProperty()
    content = db.TextProperty()
    edit_time = db.DateTimeProperty(auto_now_add = True)
    
    #prepare to render in json
    def to_dict(self):
        d = {'username' : self.username,
             'item' : self.item,
             'content' : self.content,
             'edit_time' : self.edit_time.strftime('%m/%d/%Y')
             }
        return d

class history(pageHandler):
    def get(self):
        (username, user_logged_in_stat) = loginHandler.parameters_for_wiki_template(self) #for wiki template
            
        #obtain history info
        his = db.GqlQuery("select * from history_info where username = :1 order by edit_time desc limit 50", username)
        his = list(his)
            #logging.error("items length = " + str(len(items)))
        self.render("history.html", username = username, history = his, user_logged_in_stat = user_logged_in_stat)

class page_history(pageHandler):
    def get(self, *url):
        (username, user_logged_in_stat) = loginHandler.parameters_for_wiki_template(self) #for wiki template
            
        #get the latest 50 updates for this item
        item = get_wiki_item_name(self)
        his = db.GqlQuery("select * from history_info where item = :1 order by edit_time desc limit 50", item)
        his = list(his)
        self.render("web_page_history.html", username = username, history = his, user_logged_in_stat = user_logged_in_stat, item = item)
        