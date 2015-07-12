import webapp2
from google.appengine.ext import db #gql database
from google.appengine.api import users
import hashlib #hashing fuctions
import logging
from util import * #import utility python

#global parameter, determine if user is logged in
user_logged_in = False

#user loggin status functions
def parameters_for_wiki_template(self, *url):
    #for wiki template
    username = get_user_name(self)
    user_logged_in_stat = get_user_logging_status()
    logging.error(user_logged_in_stat)
    username = ""
    if (user_logged_in_stat):
        username = get_user_name(self)
        logging.error("username = " + username)   
    return (username, user_logged_in_stat)

def set_user_logged_in():
    global user_logged_in
    logging.error("user logged in")
    user_logged_in = True
    
def set_user_logged_out():
    global user_logged_in
    logging.error("user logged out")
    user_logged_in = False
    
def get_user_logging_status():
    global user_logged_in
    logging.error("user logging stat is " + str(user_logged_in))
    return user_logged_in

#db class to store all info
class wiki_user_info(db.Model):
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
            next_url = '/wiki'
            
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
             u = wiki_user_info(username = username, password_hash = make_pw_hash(username, password, salt))
             u.put()
             user_id = u.key().id() 
        
             #pass cookie to browser
             cookie_content = '%s|%s' % (user_id, u.password_hash)
             self.response.headers.add_header('Set-Cookie', 'user_id=%s; Path =/wiki' %cookie_content) #write your cookie to browser
             logging.error(next_url)
             self.redirect(next_url)
             set_user_logged_in()  #set it to be true

def get_user_name(self):
    cookie = self.request.cookies.get('user_id')
    if cookie:
        cookie_user_id = int(cookie.split('|')[0])
        cookie_pw = cookie.split('|')[1]
        
        #get the password hash by user id
        u = wiki_user_info.get_by_id(cookie_user_id)
        if (u == None):
            return None
        elif (not(cookie_pw == u.password_hash)):
            error = u.password_hash + "," + cookie_pw 
            return error
        else:
            return u.username
    else:
        return None    
         
            
class Signin_cookie(pageHandler):
    def get(self):
        next_url = self.request.headers.get('referer', '/')
        self.render('/Signin-form.html', next_url = next_url)
        
    def post(self):
        have_error = False
        #get username and password
        username = self.request.get('username')
        password = self.request.get('password')
        
        #direct back to the previous page
        next_url = str(self.request.get('next_url'))
        if not next_url or next_url.startswith('/login'):
            next_url = '/wiki'
        
        params = dict(username = username)
        #step 1, find the object in db
        user = db.GqlQuery('select * from wiki_user_info where username = :1', username) 
        if not user.get():
            logging.error("user name not exist")
            params['error_username'] = "username does not exist, please <a href=/wiki/signup>sign up</a>"
            self.render('/Signin-form.html', **params)
        elif not(user.get().password_hash == make_pw_hash(username, password, salt)):
            params['error_password'] = "password does not match with system records"
            self.render('/Signin-form.html', **params)
        else:
             cookie_content = '%s|%s' % (str(user.get().key().id()), str(user.get().password_hash))
             self.response.headers.add_header('Set-Cookie', 'user_id=%s; Path =/wiki' %cookie_content) #write your cookie to browser
             set_user_logged_in()
             self.redirect(next_url)
        

class Signout_cookie(pageHandler):
    def get(self):
        set_user_logged_out()
        self.redirect('/wiki') 
        #simplest way to delete cookie, by setting the same path and use black to cover it   
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/wiki')   
