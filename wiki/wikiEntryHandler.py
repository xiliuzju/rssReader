import webapp2
from google.appengine.ext import db #gql database
from google.appengine.api import users
from util import * #import utility python
import loginHandler
from google.appengine.api import memcache #memcache
import logging
from history import *
import Queue

queue_of_words = Queue.Queue()
hash_of_words = set()
queue_length = 100

#use a queue to store latest 100 entered items
def queue_to_list(q):
    """ Dump a Queue to a list """

    # A new list
    l = []

    while q.qsize() > 0:
        l.append(q.get())
    
    for item in l:
        q.put(item)
    
    return l

class wiki_info(db.Model):
    username = db.StringProperty(required = True)
    item = db.StringProperty(required = True)
    wiki_content = db.TextProperty(required = True)
    last_modified = db.DateTimeProperty(auto_now = True)
    
    #prepare to render in json
    def to_dict(self):
        d = {'username' : self.username,
             'item' : self.item,
             'last_modified' : self.last_modified.strftime('%m/%d/%Y'),
             'content' : self.wiki_content
             }
        return d

def get_content(item):
    tup = memcache.get(item)
    if tup:
        logging.debug("update page, no db query")
    else:
         #grab data from db
        wiki_entry = db.GqlQuery("select * from wiki_info where item = :1", item) 
        wiki_entry = wiki_entry.get()
        if wiki_entry:
            content = wiki_entry.wiki_content 
            tup = (wiki_entry.username, content)
        else:
            tup = (None, None)
        logging.debug("update page, with db query")
    return tup
    
class wiki_entry_page(pageHandler):
    def get(self, *url):
        (username, user_logged_in_stat) = loginHandler.parameters_for_wiki_template(self)
        #a, for a normal wiki entry page, url like this: /wiki/...
        item = get_wiki_item_name(self)
        content = ""
        last_modified_username = ""  
        #b, for url like this: /wiki/...?v=...
        if (len(item.split("?v=")) > 1):
            (item, version) = item.split("?v=")
            version = int(version)
            tup = get_content(item)
            if tup[1]:
                his = db.GqlQuery("select * from history_info where item = :1 order by edit_time desc limit 50", item)
                his = list(his)
                content = his[version - (len(his) - 1)].content
        else:
            tup = get_content(item)
            if tup[1]:
                 content = tup[1]
         
        last_modified_username = tup[0]

        if user_logged_in_stat and (not tup[1]):
            self.redirect('/wiki/_edit/' + item)

        else:
            self.render("wiki_single_page.html", item = item, content = content, username = username, user_logged_in_stat = user_logged_in_stat,
                        last_modified_username = last_modified_username)   

    
class wiki_edit_page(pageHandler):
    def get(self):
        user_logged_in_stat = loginHandler.get_user_logging_status()
        item = get_wiki_item_name(self)
        if user_logged_in_stat:
            username = loginHandler.get_user_name(self)
            tup = get_content(item)
            content = "" #default is empty value
            if tup[1]:
                content = tup[1]
            self.render("wiki_post_page.html", item = item, content = content, username = username, user_logged_in_stat = user_logged_in_stat)
        else:
            self.render('/wiki/login') #redirect to the front page        
        
        
    def post(self):
        content = self.request.get('content').replace('\n', '')
        username = loginHandler.get_user_name(self)
        item = get_wiki_item_name(self)
        
        #for front page
        global hash_of_words
        global queue_of_words
        global queue_length
        if not (item in hash_of_words):
            if (queue_of_words.qsize() >= 100):
                queue_of_words.dequeue()
            queue_of_words.put(item)
            hash_of_words.add(item)
        logging.debug("queue finished")

        if memcache.get(item):
            logging.debug("update a existing item in wiki, item = " + item)
            wiki_entry = db.GqlQuery("select * from wiki_info where item = :1", item) 
            wiki_entry.wiki_content = content
            wiki_entry = wiki_entry.get() #update content in db
            wiki_entry.put() 
        else:
            logging.debug("create a new item in wiki, item =" + item)
            p = wiki_info(username = username, wiki_content = content, item = item)
            p.put()
        memcache.set(item, (username, content))  #use memcache to update this item
        
        #add current item to user history page
        h = history_info(username = username, item = item, content = content)
        h.put()
        self.redirect('/wiki/' + item)
        
               