from ast import arg
from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import os
from functools import wraps
import jwt
import datetime
from dotenv import load_dotenv
import info
import json

load_dotenv()  # take environment variables from .env.


from utils import *
from flask_cors import CORS, cross_origin

ALLOWED_URLS = ["http://localhost:3000"]
OPEN_ROUTES = ['index']  # Routes that don't require authentication
DAYS_TOKEN_LAST = 365


# Manage dabatabase related tasks
class DbManager:

   def __init__(self) -> None:
      self.conn = psycopg2.connect(
                     host="localhost",
                     port="5432",
                     database="lets-blog",
                     user=os.getenv("FLASK_APP_USER"),
                     password=os.getenv("FLASK_APP_PASSWORD")
                  )
      self.cur = self.conn.cursor()


   def get_blogs(self):
      self.cur.execute("""
         SELECT b.id, b.title, content, img, user_id, c.title
         FROM blogs as b
         JOIN categories_blogs as cb ON b.id = cb.blog_id
         JOIN categories as c on c.id = cb.category_id
         ORDER BY b.created_at DESC
      """)
      blogs_row = self.cur.fetchall()
      keys = ["id", "title", "content", "img", "user_id", "category"]
      blogs = [ { keys[i]:v for i,v in enumerate(row) } for row in blogs_row]
      
      return blogs


   def get_user_blogs(self, id):
      self.cur.execute("""
         SELECT b.id, b.title, content, img, user_id, c.title
         FROM blogs as b
         JOIN categories_blogs as cb ON b.id = cb.blog_id
         JOIN categories as c on c.id = cb.category_id
         WHERE b.user_id = %s
         ORDER BY b.created_at DESC
      """, (id,))
      blogs_row = self.cur.fetchall()
      print(blogs_row)
      keys = ["id", "title", "content", "img", "user_id", "category"]
      blogs = [ { keys[i]:v for i,v in enumerate(row) } for row in blogs_row]
      
      return blogs


   def get_blog(self, id):
      self.cur.execute("""
         SELECT b.id, b.title, content, img, user_id, c.title, u.username, u.avatar, u.name, u.location, u.bio
         FROM blogs as b
         JOIN categories_blogs as cb ON b.id = cb.blog_id
         JOIN categories as c ON c.id = cb.category_id
         JOIN users as u ON b.user_id = u.id
         where b.id = %s;
      """, (id,))
      blog_row = self.cur.fetchone()
      keys = ["id", "title", "content", "img", "user_id", "category", "username", "avatar", "name", "location", "bio"]
      blog = { keys[i]:v for i,v in enumerate(blog_row) }

      return blog


   def get_user(self, id):
      self.cur.execute("""
         SELECT id, name, username, email, avatar, cover, bio, location, website, linkedin, facebook, twitter, instagram, youtube, created_at, updated_at 
         FROM users WHERE id = %s
      """, (id,))
      user_row = self.cur.fetchone()
      keys = ["id", "name", "username", "email", "avatar", "cover", "bio", "location", "website", "linkedin", "facebook", "twitter", "instagram", "youtube", "created_at", "updated_at"]
      user = { keys[i]:v for i,v in enumerate(user_row) }
      user["skills"] = self.get_skills(id)
      user["occupation"] = self.get_occupation(id)
      user["company"] = self.get_company(id)

      return user   


   def get_skills(self, id):
      self.cur.execute("""
         SELECT title
         FROM skills_users
         JOIN skills ON skills.id = skill_id
         WHERE user_id = %s;
      """, (id,))
      # print(f'SKILLS: ${self.cur.fetchall()}')
      skills_rows = self.cur.fetchall()
      skills = [value[0] for value in skills_rows]
      return skills


   def get_occupation(self, id):
      self.cur.execute("""
         SELECT occupations.title
         FROM occupations_users
         JOIN occupations ON occupation_id = occupations.id
         WHERE user_id = %s;
      """, (id,))
      # print(f'OCCUPATION: {self.cur.fetchone()}')
      occupation = self.cur.fetchone()[0]
      return occupation


   def get_company(self, id):
      self.cur.execute("""
         SELECT companies.title
         FROM companies_users
         JOIN companies ON company_id = companies.id
         WHERE user_id = %s;
      """, (id,))
      # print(f'COMPANY: {self.cur.fetchone()}')
      company = self.cur.fetchone()[0]
      return company


   def username_exists(self, username):
      self.cur.execute("SELECT username FROM users WHERE username = %s", (username,))
      username = self.cur.fetchone()
      # print(username)
      if username: return True
      else: return False


   def email_exists(self, email):
      self.cur.execute("SELECT email FROM users WHERE email = %s", (email,))
      email = self.cur.fetchone()
      # print(email)
      if email: return True
      else: return False


   def update_user(self, id, data : dict()):
      for key, value in data.items():
         self.cur.execute(f"""
         BEGIN;
         UPDATE users SET {key} = %s WHERE id = {id};
         COMMIT;
         """, (value,))
      
      return True


   def create_blog(self, data):
      # id, title, img, content, 
      category = self.get_category(data["category"].lower())
      # print("Called create blog")
      # print(data)
      # print(f"Type: {type(data['id'])}")
      # print(title)

      self.cur.execute("""
      BEGIN;
      INSERT INTO blogs (title, img, content, user_id)
      VALUES (%s, %s, %s, %s);
      COMMIT;

      SELECT * FROM blogs WHERE user_id = %s ORDER BY id DESC;
      """, (data["title"], data["cover"], data["content"], data["id"], data["id"]))

      blog = self.cur.fetchone()
      category_id, blog_id = category[0], blog[0]
      self.create_categories_blogs(category_id, blog_id)
      return blog


   def get_category(self, category_title):
      self.cur.execute("""
      SELECT * FROM categories WHERE title = %s;
      """, (category_title,))
      category_record = self.cur.fetchone()

      if category_record:
         return category_record
      else:
         self.create_category(category_title)
         category_record = self.get_category(category_title)   # Recursive call
         return category_record


   def create_category(self, title):
      self.cur.execute("""
      BEGIN;
      INSERT INTO categories (title) 
      VALUES (%s);
      COMMIT;
      """, (title,))


   def create_categories_blogs(self, cat_id, b_id):
      self.cur.execute("""
      BEGIN;
      INSERT INTO categories_blogs (category_id, blog_id)
      VALUES (%s, %s);
      COMMIT;
      """, (cat_id, b_id,))
      print("categories_blogs record updated")
      return


   def close_cur_conn(self):
      self.cur.close()
      self.conn.close()


# Authenticate User
class UserManager:

   def __init__(self, cur, request) -> None:
      self.cur = cur
      self.request = request

   
   # Login
   def login(self, **kwargs) -> tuple :
      """
      Returns a user Object if the forms username and password is valid
      """
      username, password = kwargs['username'].strip(), kwargs['password'].strip()
      self.cur.execute('SELECT id, username, password FROM users WHERE username = %s', (username,))
      user = self.cur.fetchone()

      if user:
         is_valid = check_password_hash(user[2], password=password)
         if is_valid: # TODO: Authenticate user
            # print("login user...")
            return user
      return None


   # Registration
   def register(self, body) -> dict():
      """
      Returns a tuple containing 2 items. 
      1st: is to be either a user object or a None value if registration was unsuccessful.
      2nd: is to be either a list of invalid fields or an empty list with no invalid field found. 
      """

      # Credentials
      username   = body['username'].lower()
      name       = body['name'].lower()
      email      = body['email']
      occupation = body['occupation'].title()
      company    = body['company'].title()
      password   = body['password']
      password_hash = generate_password_hash(password)

      manager = DbManager()
      invalid_fields = check_username_email(manager, username, email)
      manager.close_cur_conn()

      # Check Password
      is_valid_password(password, invalid_fields)

      # print(f'Invalid Fields: ${invalid_fields}')
      if len(invalid_fields) == 0:
         # Form is valid
         user = self.create_user(username, name, email, occupation, company, password_hash)
         return ({"username": username, "password": password})
      else:
         # Form is not valid
         return ({"message": invalid_fields})


   # for register_user
   def create_user(self, username, name, email, occupation_title, company_title, password):
      self.cur.execute("""
         BEGIN;

         INSERT INTO users (username, name, email, password, bio)
         VALUES (%s, %s, %s, %s, 'Hello there, I am now on lets blog');

         COMMIT;
      """, (username, name, email, password))
      self.cur.execute('SELECT * FROM users WHERE username = %s;', (username,))
      user = self.cur.fetchone()
      user_id = user[0]
      
      # Add Occupation
      self.add_occupation(user_id, occupation_title)

      # Add Company
      self.add_company(user_id, company_title)

      return user


   # for create_user
   def add_occupation(self, user_id, occupation_title):
      try:
         # Get Occupation
         self.cur.execute('SELECT * FROM occupations WHERE title = %s', (occupation_title,))
         occupation = self.cur.fetchone()
         occupation_id = occupation[0]
      except:
         # Create Occupation
         self.cur.execute("""
            BEGIN;
         
            INSERT INTO occupations (title)
            VALUES (%s);

            COMMIT;
         """, (occupation_title,))
         # Get occupation
         self.cur.execute('SELECT * FROM occupations WHERE title = %s', (occupation_title,))
         occupation = self.cur.fetchone()
         occupation_id = occupation[0]

      # Create Relationship
      self.cur.execute("""
         BEGIN;

         INSERT INTO occupations_users (occupation_id, user_id)
         VALUES (%s, %s);

         COMMIT;
      """, (occupation_id, user_id))


   # for add_company
   def add_company(self, user_id, company_title):
      try:
         # Get company
         self.cur.execute('SELECT * FROM companies WHERE title = %s', (company_title,))
         company = self.cur.fetchone()
         company_id = company[0]
      except:
         # Create company
         self.cur.execute("""
            BEGIN;
         
            INSERT INTO companies (title)
            VALUES (%s);

            COMMIT;
         """, (company_title,))
         # Get company
         self.cur.execute('SELECT * FROM companies WHERE title = %s', (company_title,))
         company = self.cur.fetchone()
         company_id = company[0]

      # Create Relationship
      self.cur.execute("""
         BEGIN;

         INSERT INTO companies_users (company_id, user_id)
         VALUES (%s, %s);

         COMMIT;
      """, (company_id, user_id))


# Token Decorator
# def token_required(f):
#    print('outer')
#    @wraps(f)
#    def decorator(*args, **kwargs):
#       token = None
#       if 'x-access-token' in request.args:
#          token = request.args.get('x-access-token')

#       if not token:
#          return jsonify({'message': 'a valid token is missing'})
#       try:
#          print(token)
#          data = jwt.decode(token, os.getenv('FLASK_APP_SECRET'), algorithms=["HS256"])
#          db = DbManager()
#          current_user = db.get_user()
#          db.close_cur_conn()
#       except:
#          return jsonify({'message': 'token is invalid'})

#       return f(current_user, *args, **kwargs)
#    return decorator


# Token Decorator
def token_required(f):
   def decorator(*args, **kwargs):
      token = request.args.get('x-access-token')
      user = None
      
      if token:
         info = jwt.decode(token, key=os.getenv('FLASK_APP_SECRET'), algorithms=["HS256"])
         db = DbManager()
         user = db.get_user(id=info['user_id'])
         db.close_cur_conn()
      else:
         if f.__name__ not in OPEN_ROUTES:
            return jsonify({'message': 'a valid token is missing'})

      print(args, kwargs)
      if kwargs.get('id'):
         return f(kwargs.get('id'), user)
      elif user:
         return f(user)
      else:
         return f()

   decorator.__name__ = f.__name__
   return decorator




# Create flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, origins=ALLOWED_URLS)


# Routes
@app.route("/api/", methods=['GET'])
@token_required
def index(owner=None):
   db = DbManager()
   blogs = db.get_blogs()
   db.close_cur_conn()
   data = {'blogs': blogs, 'owner': owner}
   return jsonify(data)


@app.route("/api/blogs/<id>")
@token_required
def blog(id, owner=None):
   db = DbManager()
   blog = db.get_blog(id)
   db.close_cur_conn()
   data = {'blog': blog, 'owner': owner}
   return jsonify(data)


@app.route("/api/users/<id>")
@token_required
def profile(id, owner=None):
   print(f"User Id: {id}")
   if request.method == "GET":
      db = DbManager()
      user = db.get_user(id)
      blogs = db.get_user_blogs(id)
      db.close_cur_conn()
      data = {"user": user, "blogs": blogs, "owner":owner}
      return jsonify(data)
   else:
      return jsonify("Backend Response: successfully arrived.")


@app.route("/api/users/<id>", methods=["PUT"])
def update_profile(id, owner=None):
   manager = DbManager()
   data = json.loads(request.data)
   username, email = data.get("username"), data.get("email")
   invalid_fields = check_username_email(manager, username, email)

   # If data is valid. Update data
   if len(invalid_fields) == 0:
      manager.update_user(id, data)
      manager.close_cur_conn()
   else:
      manager.close_cur_conn()
      return jsonify({"invalid_fields" : invalid_fields})

   return jsonify({"message": "successful"})


@app.route("/api/login", methods=["POST"], strict_slashes=False)
def login():
   db = DbManager()
   username, password = request.json['username'], request.json['password']
   manager = UserManager(db.cur, request)
   user = manager.login(username=username, password=password)
   db.close_cur_conn()

   if user:
      token = jwt.encode({'user_id' : user[0], 'exp' : datetime.datetime.utcnow() + datetime.timedelta(days=DAYS_TOKEN_LAST)}, os.getenv('FLASK_APP_SECRET'), "HS256")
      return jsonify({'token' : token})
   return jsonify({'message': 'unsuccessful'})


@app.route("/api/register", methods=["POST"])
def sign_up():
   db = DbManager()
   manager = UserManager(db.cur, request)
   body = request.json
   user = manager.register(body)
   # print(user)
   db.close_cur_conn()
   return jsonify(user)


@app.route("/api/blogs", methods=["POST"])
def create_blog():
   manager = DbManager()
   data = json.loads(request.data)
   blog = manager.create_blog(data)
   blog_id = blog[0]
   manager.close_cur_conn()

   return jsonify(blog_id)


# Run App
if __name__ == "__main__":
   app.run(debug=True)

