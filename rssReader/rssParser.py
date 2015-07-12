from google.appengine.ext import db #gql database
from google.appengine.api import users
from google.appengine.api import memcache #memcache
import logging
import json
import util
import os
import sys
import collections
from datetime import datetime
sys.path.append(os.path.abspath("lib"))
import feedparser as fp

#configuration of feedparser to allow it support embedded objects
fp._HTMLSanitizer.acceptable_elements.add("object")
fp._HTMLSanitizer.acceptable_elements.add("embed")
fp._HTMLSanitizer.acceptable_elements.add("iframe")

#global variables section
INITIAL_UNREAD_ITEM_NUM = "10"
FEED_QUERY_GAP_SECONDS = 1200
FEED_NUM_IN_CACHE = 100
TIME_INITIAL = util.serialize_time(datetime.strptime("1900-01-01 00:00:00.1000","%Y-%m-%d %H:%M:%S.%f"))

#user section, user info control, user adds or deletes a feed
class rss_user_data(db.Model):
    username = db.StringProperty(required = True)
    rss_feeds = db.TextProperty() #can be empty at initial stage
    
#feed section, store entire feed flow for each feed in the db
class feed_db_info(db.Model):
    feed_url = db.StringProperty(required=True)
    feed_flow = db.TextProperty() #can be empty at initial stage
    last_entry = db.StringProperty()
    

def add_feed(username, feed):
    logging.error("adding this feed" + feed)
    global TIME_INITIAL
    #flush this username
    memcache.delete(username)
    #update db
    q = db.GqlQuery('select * from rss_user_data where username = :1', username)
    q = q.get()
    if q:
        feeds = json.loads(q.rss_feeds) 
    else:
        feeds = {}
    feeds[feed] = get_title_from_feed(feed) #modify this feed
    setattr(q, "rss_feeds", json.dumps(feeds)) #serialize the feed
    q.put()
    
    #deal with the feed_cache_info class
    global INITIAL_UNREAD_ITEM_NUM
    addSubscriber = False
    feedData = memcache.get(feed)
    if (not feedData):
        #initialize the feed_cache_info class
        f = {"last_query":TIME_INITIAL, "subscriber":[], "cached_flow":[]}
        addSubscriber = True
    else:
        f = json.loads(feedData)
        if(subscriber for subscriber in f["subscriber"] if subscriber["username"] == username):
             #test whether it contains the same username or not, if contains, do nothing
            logging.error("add subscriber to feed_cache_info: user already exists")
        else:
            addSubscriber = True
    
    if (addSubscriber):
        subscriber={"username":username, "unread":INITIAL_UNREAD_ITEM_NUM, "last_read":""}
        f["subscriber"].append(subscriber)
        memcache.set(feed, json.dumps(f))


def del_feed(username, feed):
    #flush this username
    memcache.delete(username)
    logging.error("memcache username deteleted")
    #update db
    r = db.GqlQuery('select * from rss_user_data where username = :1', username)
    q = r.get()
    feeds = q.rss_feeds
    feeds = json.loads(feeds) 
    del feeds[feed] #modify this feed
    for entry in r: 
        entry.rss_feeds = json.dumps(feeds)
        db.put(entry)
   
    
def feeds_to_list(username):
    if (memcache.get(username)):
        feeds= json.loads(memcache.get(username))
    else:
        q = db.GqlQuery('select * from rss_user_data where username = :1', username)
        q = q.get()
        feeds = {}
        if q:   
            feeds = q.rss_feeds
        memcache.set(username, feeds)
        logging.error("DB query")
        if feeds:
            feeds = json.loads(feeds) 
        else:
            feeds = {}
    #sort feed keys
    feeds = collections.OrderedDict(sorted(feeds.items()))
    return feeds

def get_title_from_feed(feed):
    f = fp.parse(feed)
    return f.feed.title

def update_feedflow(feed, username): #update feed flow, # to memcache, all to db
    global FEED_NUM_IN_CACHE
    global TIME_INITIAL
    feedContent = feed_query(feed)
    f = db.GqlQuery('select * from feed_db_info where feed_url = :1', feed) #get the db feed flow first
    f = f.get()
    if f:
        feed_flow_db = json.loads(f.feed_flow)
        last_entry = f.last_entry
    
    else:#initialize
        feed_flow_db = []
        last_entry = ""
    
    #update content
    if feedContent:
            update_feed_flow_db = []
            for i in range(0, len(feedContent)):
                feeditem = feedContent[i]
                if (feeditem[3] == last_entry): #if it is already the most recent feed, by comparing the url
                    break
                else:
                    update_feed_flow_db.append(feeditem)
            feed_flow_db = update_feed_flow_db + feed_flow_db #append to the left
    
            
    #determine the latest entry
    if len(feedContent) > 0:
        last_entry = feedContent[0][3]
    else:
        last_entry = ""
            
    #update db first
    if f:
        setattr(f, "feed_flow", json.dumps(feed_flow_db))
        setattr(f, "last_entry", last_entry)
    else:
        f = feed_db_info(feed_url = feed, feed_flow = json.dumps(feed_flow_db), last_entry = last_entry)
    f.put()
      
    #update memcache
    feed_info_cache = memcache.get(feed)
    if (feed_info_cache):
        feed_info_cache = json.loads(feed_info_cache)
        feed_info_cache["cached_flow"] = feed_flow_db[0:min(FEED_NUM_IN_CACHE, len(feed_flow_db))]
        feed_info_cache["last_query"] = util.serialize_time(datetime.now())
    else: #initialize the data structure
        feed_flow_cache = feed_flow_db[0:min(FEED_NUM_IN_CACHE, len(feedContent)) - 1] #only save # items in cache
        subscriber={"username":username, "unread":INITIAL_UNREAD_ITEM_NUM, "last_read":""}
        feed_info_cache = {"last_query":TIME_INITIAL, "subscriber":subscriber, "cached_flow":feed_flow_cache}
            
    memcache.set(feed, json.dumps(feed_info_cache))

#std library to query the feed from rss,
#please refer to the code below for the sequence of feed information, 
#here I use title -> description -> time -> link -> media(if exist)        
def feed_query(feed):
    #media extensions
    media_ext = ["jpg", "png", "gif", "jpeg,", "tiff", "bmp", "mp4",
           ".avi", ".flv", ".mkv", ".mov", ".mpg", ".mpeg",".swf", ".vob", ".wmv"]
    #use list to maintain the order of original feed list
    f = fp.parse(feed)
    c=[]
    for i in f.entries:
        #if it contains media, for example, jpg...etc
        if ('media_content' in i):
            media = i.media_content
            media_html = '<img id = "media" src="' + \
            '"></img><div><br></div><img id = "media" src="'.join(
            m['url'] for m in media if m['url'].endswith(tuple(media_ext)))+'"></img>'  #add a filter to the useless media
            c.append([i.title, util.mdcode(i.description), " ".join(i.published.split(" ")[0:4]), i.link, media_html])
        else:
            c.append([i.title, util.mdcode(i.description), " ".join(i.published.split(" ")[0:4]), i.link, ""])
    return c


def get_content_from_feed(feed, username):
    global FEED_QUERY_GAP_SECONDS
    now = datetime.now()
    feedflowCache = memcache.get(feed)
    if feedflowCache:
        lastQuery = json.loads(feedflowCache)["last_query"]
        if (int((now - util.deserialize_time(lastQuery)).total_seconds()) <= FEED_QUERY_GAP_SECONDS):
            logging.error("feed:" + feed + "start to refresh from memcache")
            return json.loads(feedflowCache)["cached_flow"]
        else:
            logging.error("feed:" + feed + "start to refresh content since last query is " + str(FEED_QUERY_GAP_SECONDS) + "seconds ago")
            update_feedflow(feed, username)
            return json.loads(memcache.get(feed))["cached_flow"]
    else:
        logging.error("feed does not exist in cache")
        update_feedflow(feed, username)
        return json.loads(memcache.get(feed))["cached_flow"]
    
def scheduled_update_all_feed():
    feeds = db.GqlQuery('select * from feed_db_info')
    if feeds:
        for feed in feeds:
            update_feedflow(feed.feed_url, "root")
        logging.error("updated all feeds at" + str(datetime.now()))

            
    