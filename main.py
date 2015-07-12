import re
from string import letters

import webapp2
import jinja2 #blog templates
import hashlib #hashing fuctions
import hmac
import re #regular expressions
import os
from datetime import datetime
from google.appengine.ext import db #gql database
from google.appengine.api import users
from google.appengine.api import memcache #memcache
import json #json
from collections import namedtuple
import logging #used for debug purposes: logging.debug

#default jinja code
template_dir = os.path.join(os.path.dirname(__file__), 'templates/blog')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)

#default string render and templates
def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)

class BlogHandler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        return render_str(template, **params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))


##### HW 6, cache
last_db_query_time = datetime.now() #used to store time that visits db

def get_blogs_from_db():
    key = "frontPage"
    blogs = db.GqlQuery("select * from Post order by created desc limit 10")
    blogs = list(blogs)
    memcache.set(key, blogs)
    logging.error("DB query")
    return blogs
    
def set_last_db_query_time():
    global last_db_query_time 
    last_db_query_time = datetime.now()

def get_age():
    global last_db_query_time
    return int((datetime.now() - last_db_query_time).total_seconds())

class BlogFront(BlogHandler):
    def get(self):
        #clear single page cache
        memcache.set("singlePage", None)

        #standard cacheing step
        key = "frontPage"
        blogs = memcache.get(key)
        if blogs is None:
            blogs = get_blogs_from_db()
            set_last_db_query_time()
            
        self.render('blog_front_page.html', blogs = blogs, db_query_difference = "queried %s seconds ago" %get_age())

class PostPage(BlogHandler):
    def get(self, post_id):
        #standard caching step
        key = "singlePage"
        post = memcache.get(key)
        if post is None:
            db_key = db.Key.from_path('Post', int(post_id), parent=blog_key())
            post = db.get(db_key)
            set_last_db_query_time()
            memcache.set(key, post)
            logging.error("DB query")

        if not post:
            self.error(404)
            return

        self.render("permalink.html", post = post, db_query_difference = "queried %s seconds ago" %get_age())

class NewPost(BlogHandler):
    def get(self):
        self.render("newpost.html")

    def post(self):
        subject = self.request.get('subject')
        content = self.request.get('content')

        if subject and content:
            p = Post(parent = blog_key(), subject = subject, content = content)
            p.put()
            blogs = get_blogs_from_db()
            memcache.flush_all() #since you already posted a new page, flush all memcache
            self.redirect('/blog/%s' % str(p.key().id()))
        else:
            error = "subject and content, please!"
            self.render("newpost.html", subject=subject, content=content, error=error)

class flushPage(BlogHandler):
    def get(self):
        memcache.flush_all()
        self.redirect('/blog') #redirect to the main page
        
##### HW 5, json 
def generate_json_for_single_post(id):
    #parse url and get the page id
    post_id = int(id)
    #get info from db
    key = db.Key.from_path('Post', int(post_id), parent=blog_key())
    post = db.get(key)
        
    #construct the namedtuple
    j = json.dumps(post.to_dict())
    return j

def generate_json_for_front_page():
    #retrieve all info from db
    all_post = db.GqlQuery("select * from Post order by created desc limit 10") 
    all_post = list(all_post) #avoid running query twice!
    j = json.dumps([p.to_dict() for p in all_post])  #the correct way to dump a collection of stuff to json
    return j       
      
class jsonWriter (BlogHandler):
    def get(self, *url):
        self.response.headers['Content-Type'] = 'application/json' #set header to be json
        url = self.request.url
        post_id = url.split("/")[len(url.split("/")) - 1].split(".")[0]
        j = ""
        if (post_id.isdigit()):
            j = generate_json_for_single_post(post_id)
        else:
            j = generate_json_for_front_page()
            
        self.format = 'json' #set format to be json
        self.write(j)

    
##### HW 4, cookie handling
#db used to store all info
class user_info(db.Model):
    username = db.StringProperty(required = True)
    password_hash = db.StringProperty(required = True)
    email = db.StringProperty()


salt = "salt" #set the salt here' 

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

class Signup(BlogHandler):

    def get(self):
        self.render("signup-form.html")

    def post(self):
        have_error = False
        username = self.request.get('username')
        password = self.request.get('password')
        verify = self.request.get('verify')
        email = self.request.get('email')

        params = dict(username = username,
                      email = email)

        if not valid_username(username):
            params['error_username'] = "That's not a valid username."
            have_error = True
        elif duplicate_username(username):
            params['error_username'] = "duplicate username."
            have_error = True

        if not valid_password(password):
            params['error_password'] = "That wasn't a valid password."
            have_error = True
        elif password != verify:
            params['error_verify'] = "Your passwords didn't match."
            have_error = True

        if not valid_email(email):
            params['error_email'] = "That's not a valid email."
            have_error = True

        if have_error:
            self.render("signup-form.html", **params)
        else:
             self.response.headers['Content-Type'] = 'text/plain'
             #store username and password hash in the db
             u = user_info(username = username, password_hash = make_pw_hash(username, password, salt))
             u.put()
             user_id = u.key().id() 
        
             #pass cookie to browser
             cookie_content = '%s|%s' % (user_id, u.password_hash)
             self.response.headers.add_header('Set-Cookie', 'user_id=%s; Path =/blog' %cookie_content) #write your cookie to browser
             self.redirect('/blog/welcome')

class welcome_cookie(BlogHandler):
    def get(self):
        #get cookie first
        cookie = self.request.cookies.get('user_id')
        cookie_user_id = int(cookie.split('|')[0])
        cookie_pw = cookie.split('|')[1]
        
        #get the password hash by user id
        u = user_info.get_by_id(cookie_user_id)
        
        if (u == None):
            self.redirect('/blog/signup') #if this id does not exists, then direct to sign up page agains
        elif (not(cookie_pw == u.password_hash)):
            error = u.password_hash + "," + cookie_pw 
            self.redirect('/blog/signup?error=%s' %error)
        else:
            self.render('/welcome.html', username = u.username, pswd = u.password_hash)
         
            
class Signin_cookie(BlogHandler):
    def get(self):
        self.render('/Signin-form.html')
        
    def post(self):
        have_error = False
        #get username and password
        username = self.request.get('username')
        password = self.request.get('password')
        
        params = dict(username = username)
        #step 1, find the object in db
        user = db.GqlQuery('select * from user_info where username = :1', username)
        if not user:
            params['error_username'] = "username does not exist, please sign up"
            self.render('/signin-form.html', **params)
        elif not(user.get().password_hash == make_pw_hash(username, password, salt)):
            params['error_password'] = "password does not match with system records"
            self.render('/Signin-form.html', **params)
        else:
             cookie_content = '%s|%s' % (str(user.get().key().id()), str(user.get().password_hash))
             self.response.headers.add_header('Set-Cookie', 'user_id=%s; Path =/blog' %cookie_content) #write your cookie to browser
             self.redirect('/blog/welcome')
        

class Signout_cookie(BlogHandler):
    def get(self):
        self.redirect('/blog/signup') 
        #simplest way to delete cookie, by setting the same path and use black to cover it   
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/blog')    
            
##### blog stuff

def render_post(response, post):
    response.out.write('<b>' + post.subject + '</b><br>')
    response.out.write(post.content)

class MainPage(BlogHandler):
  def get(self):
      self.write('Hello, Udacity!')

def blog_key(name = 'default'):
    return db.Key.from_path('blogs', name)

class Post(db.Model):
    subject = db.StringProperty(required = True)
    content = db.TextProperty(required = True)
    created = db.DateTimeProperty(auto_now_add = True)
    last_modified = db.DateTimeProperty(auto_now = True)

    def render(self):
        self._render_text = self.content.replace('\n', '<br>')
        return render_str("post.html", p = self)
    
    def to_dict(self):
        d = {'content' : self.content.replace('\n', '<br>'),
             'created' : self.created.strftime('%m/%d/%Y'),
             'last_modified' : self.last_modified.strftime('%m/%d/%Y'),
             'subject' : self.subject}
        return d


###### Unit 2 HW's
class Rot13(BlogHandler):
    def get(self):
        self.render('rot13-form.html')

    def post(self):
        rot13 = ''
        text = self.request.get('text')
        if text:
            rot13 = text.encode('rot13')

        self.render('rot13-form.html', text = rot13)


USER_RE = re.compile(r"^[a-zA-Z0-9_-]{3,20}$")
def valid_username(username):
    return username and USER_RE.match(username)

def duplicate_username(username):
    user = db.GqlQuery("select * from user_info where username = :1", username)
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



#deploy configurations, page connection
app = webapp2.WSGIApplication([('/', MainPage),
                               ('/blog/rot13', Rot13),
                               ('/blog/signup', Signup),
                               ('/blog/login', Signin_cookie),
                               ('/blog/welcome', welcome_cookie),
                               ('/blog/logout',Signout_cookie),
                               ('/blog/?', BlogFront),
                               ('/blog/([0-9]+)', PostPage),
                               ('/blog/newpost', NewPost),
                               ('/blog/([0-9]+).json', jsonWriter),
                               ('/blog/.json', jsonWriter),
                               ('/blog/flush', flushPage),
                               ],
                              debug=True)
