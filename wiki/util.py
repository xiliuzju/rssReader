import webapp2
import os
import jinja2
import hashlib
import re
from google.appengine.ext import db #gql database
from google.appengine.api import users
import logging

logging.error(os.path.dirname(__file__))
template_dir = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__),"..")), 'templates/wiki')
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
    return username and USER_RE.match(username)

def duplicate_username(username):
    user = db.GqlQuery("select * from wiki_user_info where username = :1", username)
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
salt = "wiki" #set the salt here' 

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

def get_wiki_item_name(self, *url):
    url = self.request.url
    return url.split("/")[len(url.split("/")) - 1].replace('%20', ' ')

