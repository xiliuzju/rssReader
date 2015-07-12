import webapp2
from google.appengine.ext import db #gql database
from google.appengine.api import users
import hashlib #hashing fuctions
import logging
from util import * #import utility python
import rssParser
import SimpleHTTPServer
import json
import urllib2
sys.path.append(os.path.abspath("lib"))
import six
import httplib2
sys.path.append(os.path.abspath("lib"))
import client, crypt

#db class to store all user info
class rss_user_info(db.Model):
    username = db.StringProperty(required = True)
    password_hash = db.StringProperty(required = True)
    email = db.StringProperty()

class Signup(pageHandler):

    def get(self):
        next_url = self.request.headers.get('referer', '/') #get the previous page url
        self.render("signup-form.html", next_url = next_url)

    def post(self):
        have_error = False
        username = self.request.get('username')
        password = self.request.get('password')
        verify = self.request.get('verify')
        email = self.request.get('email')

        #direct back to the previous page
        next_url = str(self.request.get('next_url'))
        if not next_url or next_url.startswith('/login'):
            next_url = '/rss'
            
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
             u = rss_user_info(username = username, password_hash = make_pw_hash(username, password, salt))
             u.put()
             user_id = u.key().id() 
             
            #create a new db entry in the rss_user_data db
             rss_feeds = json.dumps({})
             r = rssParser.rss_user_data(username = username, rss_feeds = rss_feeds);
             r.put();
             
             #pass cookie to browser
             cookie_content = '%s|%s' % (user_id, u.password_hash)
             self.response.headers.add_header('Set-Cookie', 'user_id=%s; Path =/rss' %cookie_content) #write your cookie to browser
             logging.error(next_url)
             self.redirect(next_url)
             
def get_user_name(self):
    cookie = self.request.cookies.get('user_id')
    if cookie:
        cookie_user_id = int(cookie.split('|')[0])
        cookie_pw = cookie.split('|')[1]
        
        #get the password hash by user id
        u = rss_user_info.get_by_id(cookie_user_id)
        if (u == None):
            return None
        elif (not(cookie_pw == u.password_hash)):
            error = u.password_hash + "," + cookie_pw 
            return error
        else:
            return u.username
    else:
        return None    
         
            
class Signin_cookie(pageHandler, SimpleHTTPServer.SimpleHTTPRequestHandler):
    def get(self, *url):
        next_url = self.request.headers.get('referer', '/')
        self.render('/Signin-form.html', next_url = next_url)
            
        
    def post(self, *url):
        #prevent error msg from refresh the login page
        username = ""
        password = ""
        #external login situation
        if (len(self.request.url.split("?ext=")) >= 2):
            external_source = self.request.url.split("?ext=")[1]
#             #external login #1, google
#             if (external_source == "google"):
#                 CLIENT_ID = "272314817438-s673suoqf7grlk38jvttruhl919bcp84.apps.googleusercontent.com"
#                 req = urllib2.Request(self.request.url)
#                 response = urllib2.urlopen(req)
#                 token = response.read()
#                 logging.error(token)
#                 try:
#                     idinfo = client.verify_id_token(token, CLIENT_ID)
#                     # If multiple clients access the backend server:
#                     if idinfo['aud'] not in [ANDROID_CLIENT_ID, IOS_CLIENT_ID, WEB_CLIENT_ID]:
#                         raise crypt.AppIdentityError("Unrecognized client.")
#                     if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
#                         raise crypt.AppIdentityError("Wrong issuer.")
#                     if idinfo['hd'] != APPS_DOMAIN_NAME:
#                         raise crypt.AppIdentityError("Wrong hosted domain.")   
#                 except crypt.AppIdentityError:
#                     # Invalid token
#                     username = idinfo['sub']
#                     password = idinfo['at_hash']
#                     logging.error(userid)  
                      
        else:
            have_error = False
            #get username and password
            username = self.request.get('username')
            password = self.request.get('password')
        
        #direct back to the previous page
        next_url = str(self.request.get('next_url'))
        if not next_url or next_url.startswith('/login'):
            next_url = '/rss'

        params = dict(username = username)
        #step 1, find the object in db
        user = db.GqlQuery('select * from rss_user_info where username = :1', username) 
        if not user.get():
            logging.error("user name not exist")
            params['error_username'] = "username does not exist, please <a href=/rss/signup>sign up</a>"
            self.render('/Signin-form.html', **params)
        elif not(user.get().password_hash == make_pw_hash(username, password, salt)):
            params['error_password'] = "password does not match with system records"
            self.render('/Signin-form.html', **params)
        else:
             cookie_content = '%s|%s' % (str(user.get().key().id()), str(user.get().password_hash))
             self.response.headers.add_header('Set-Cookie', 'user_id=%s; Path =/rss' %cookie_content) #write your cookie to browser
             self.redirect('/rss')
        

class Signout_cookie(pageHandler):
    def get(self):

        self.redirect('/rss') 
        #simplest way to delete cookie, by setting the same path and use black to cover it   
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/rss')   
