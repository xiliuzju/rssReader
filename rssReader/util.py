import webapp2
import jinja2
import hashlib
import re
import urllib2
import logging
from datetime import datetime
from google.appengine.ext import db #gql database
from google.appengine.api import users
from google.appengine.api import memcache #memcache
from urlparse import urlparse
import os
import sys
sys.path.append(os.path.abspath("lib"))
from BeautifulSoup import BeautifulSoup


#change the jinja encoding to utf-8, basically just reload the system default encoding to utf-8
reload(sys)
sys.setdefaultencoding('utf-8')

#jinja template default
logging.error(os.path.dirname(__file__))
template_dir = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__),"..")), 'templates/rssReader')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)

def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)
	
class pageHandler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        return render_str(template, **params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))
        

#username checking
USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
def valid_username(username):
    if username == "root":
        return False
    return username and USER_RE.match(username)

def duplicate_username(username):
    user = db.GqlQuery("select * from rss_user_info where username = :1", username)
    if user:
        return False
    else: 
        return True

PASS_RE = re.compile(r"^.{3,20}$")
def valid_password(password):
    return password and PASS_RE.match(password)

EMAIL_RE  = re.compile(r'^[\S]+@[\S]+\.[\S]+$')
def valid_email(email):
    return not email or EMAIL_RE.match(email)

#salting and hashing functions
salt = "rss_feed" #set the salt here' 

def make_salt():
    salt_length = 5
    return ''.join(random.choice(string.letters) for x in xrange(salt_length))

def hash_str(s):
    return hashlib.sha256(s).hexdigest()
            
def valid_user(name, pw):
    user = get_user(name)
    if user and user.password == pw:
        return user
    
def make_pw_hash(name, pw):
    salt=make_salt()
    h = hashlib.sha256(name + pw + salt).hexdigest()
    return h

def make_pw_hash(name, pw, salt):
    if not salt:
        salt=make_salt()
    h = hashlib.sha256(name + pw + salt).hexdigest()
    return h

def valid_pw(name, pw, cookie, salt):
    h = cookie.split('|')[1]
    return h == make_pw_hash(name, pw, salt)

#caching part, use memcache for less load on db
#return True after setting the data
def cache_set(key, value):
    memcache.set(key, value)
    return True

#return the value for key
def cache_get(key):
    return memcache.get(key)

#delete key from the cache
def cache_delete(key):
    if key in memcache:
        memcache.delete(key)

#clear the entire cache
def cache_flush():
    memcache.flush_all()

#return a tuple of (value, h), where h is hash of the value. a simple hash
#we can use here is hash(repr(val))
def cache_gets(key):
    ###Your gets code here.
    if memcache.get(key):
        return (memcache.get(key), hash(repr(memcache.get(key))))
    else:
        return None

# set key = value and return True if cas_unique matches the hash of the value
# already in the cache. if cas_unique does not match the hash of the value in
# the cache, don't set anything and return False.
def cache_cas(key, value, cas_unique):
    ###Your cas code here.
    unique = cache_gets(key)[1]
    if (cas_unique == unique):
        cache_set(key, value)
        return True
    else:
        return False

#character encoding decoding section, copied from https://groups.google.com/forum/#!topic/python-cn/vW1tTy5h1bk
def mdcode( str, encoding='utf-8' ):
    if isinstance(str, unicode):
        return str.encode(encoding)

    for c in ('utf-8', 'gbk', 'gb2312','gb18030','utf-16'):
        try:
            return str.decode(c).encode( encoding )
        except:
            pass
    raise 'Unknown charset'

def getCharSet( data ):
    maping = ['utf-8','gbk','gb2312','gb18030','utf-16']

    if isinstance(data, unicode):
        return "unicode"

    for i in maping:
        try:
            data.decode(i)
            return i
        except:
            pass
    return "Unknow"

#get fav icon and use memcache to store it
def get_feed_domain(feed):
    parsed_uri = urlparse(feed)
    return '{uri.netloc}'.format(uri=parsed_uri)

#parse a url if it is not a direct rss
def parse_rss_feed(url):
    #edge case, add header to url
    if not(url.startswith("http://") or url.startswith("https://")):
        url = "http://" + url
      
    page = urllib2.urlopen(url)
    soup = BeautifulSoup(page.read())
    
    #edge case, if it is already a rss
    if soup.find("rss"):
        return url
    #case 1, it contains rss formats
    elif soup.find("link", {"type":"application/rss+xml"}):
        return soup.find("link", {"type":"application/rss+xml"})['href'] #standard rss format
    else:
        return None
    
#time seralize & deserialize
def serialize_time(time):
    return str(time)

def deserialize_time(timeString):
    return datetime.strptime(timeString, "%Y-%m-%d %H:%M:%S.%f")

