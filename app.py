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
DAYS_TOKEN_LAST = 1


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


   def get_blog(self, id, owner_id):
      self.cur.execute("""
         SELECT b.id, b.title, content, img, user_id, c.title, u.username, u.avatar, u.name, u.location, u.bio,
         (SELECT COUNT(*) as likes FROM likes WHERE likes.blog_id = %s AND likes.is_like = true ),
         (SELECT COUNT(*) as dislikes FROM likes WHERE likes.blog_id = %s AND likes.is_like = false )
         FROM blogs as b
         JOIN categories_blogs as cb ON b.id = cb.blog_id
         JOIN categories as c ON c.id = cb.category_id
         JOIN users as u ON b.user_id = u.id
         where b.id = %s;
      """, (id, id, id,))
      blog_row = self.cur.fetchone()
      keys = ["id", "title", "content", "img", "user_id", "category", "username", "avatar", "name", "location", "bio", "likes", "dislikes"]
      blog = { keys[i]:v for i,v in enumerate(blog_row) }

      self.add_owner_liked_blog([blog], owner_id)

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


   def add_comments_likes(self, comments_list):
      for comment in comments_list:
         # Get comments likes count
         self.cur.execute("""
            SELECT COUNT(*) FROM likes WHERE comment_id = %s AND is_like = true
         """, (comment['id'],))
         comment['likes'] = self.cur.fetchone()[0]

         # Get comments dislikes count
         self.cur.execute("""
            SELECT COUNT(*) FROM likes WHERE comment_id = %s AND is_like = false
         """, (comment['id'],))
         comment['dislikes'] = self.cur.fetchone()[0]


   def add_owner_liked_comment(self, comments_list, owner_id):
      for comment in comments_list:
         self.cur.execute("""
            SELECT * FROM likes WHERE comment_id = %s AND user_id = %s AND is_like = true;
         """, (comment['id'], owner_id))

         comment['liked'] = True if self.cur.fetchone() else False 

         self.cur.execute("""
            SELECT * FROM likes WHERE comment_id = %s AND user_id = %s AND is_like = false;
         """, (comment['id'], owner_id))

         comment['disliked'] = True if self.cur.fetchone() else False 
         
         print('LIKES and DISLIKES')
         print(comment['liked'], comment['disliked'])
      
      return


   def add_owner_liked_blog(self, blog_list, owner_id):
      for blog in blog_list:
         self.cur.execute("""
            SELECT * FROM likes WHERE blog_id = %s AND user_id = %s AND is_like = true;
         """, (blog['id'], owner_id))

         blog['liked'] = True if self.cur.fetchone() else False 

         self.cur.execute("""
            SELECT * FROM likes WHERE blog_id = %s AND user_id = %s AND is_like = false;
         """, (blog['id'], owner_id))

         blog['disliked'] = True if self.cur.fetchone() else False 
         
         print('LIKES and DISLIKES')
         print(blog['liked'], blog['disliked'])
      
      return


   def add_sub_comments_count(self, comments_list):
      for comment in comments_list:
         self.cur.execute("""
            SELECT COUNT(*)
            FROM comments
            WHERE comments.comment_id = %s;
         """, (comment['id'],))

         comment['sub_comments_count'] = self.cur.fetchone()[0];      


   def get_comments(self, owner_id, blog_id=None, comment_id=None):
      if blog_id:
         self.cur.execute("""
            SELECT comments.id, user_id, blog_id, comment_id, content, users.username, users.avatar
            FROM comments 
            JOIN users ON users.id = comments.user_id
            WHERE blog_id = %s
            ORDER BY comments.created_at DESC;
         """, (blog_id,))
      else:
         self.cur.execute("""
            SELECT comments.id, user_id, blog_id, comment_id, content, users.username, users.avatar
            FROM comments 
            JOIN users ON users.id = comments.user_id
            WHERE comment_id = %s
            ORDER BY comments.created_at DESC;
         """, (comment_id,))

      comments_raw = self.cur.fetchall()
      keys = ["id", "user_id", "blog_id", "comment_id", "content", "username", "avatar"]
      comments = [ { keys[i]:v for i,v in enumerate(row) } for row in comments_raw]

      self.add_comments_likes(comments)
      self.add_owner_liked_comment(comments, owner_id)
      self.add_sub_comments_count(comments)

      return comments


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


   def update_user(self, user_id, data : dict()):
      for key, value in data.items():
         self.cur.execute(f"""
         BEGIN;
         UPDATE users SET {key} = %s WHERE id = {user_id};
         COMMIT;
         """, (value,))
      
      return True


   def create_blog(self, data):
      # id, title, img, content, 
      category = self.get_category(data["category"].lower())

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
      print(f'Create Categories and Blogs Relationship WIth: {cat_id} {b_id}')
      
      self.cur.execute("""
      BEGIN;
      INSERT INTO categories_blogs (category_id, blog_id)
      VALUES (%s, %s);
      COMMIT;
      """, (cat_id, b_id,))
      # print("categories_blogs record updated")
      return


   def delete_categories_blogs(self, b_id):
      print(f'Remove Categories and Blogs Relationship: {b_id}')
      self.cur.execute("""
      BEGIN;
      DELETE FROM categories_blogs
      WHERE blog_id = %s;
      COMMIT;
      """, (b_id,))
      # print("categories_blogs record updated")
      return


   def delete_blog(self, user_id, blog_id):
      self.cur.execute("""
      BEGIN;
      DELETE FROM blogs WHERE (user_id = %s AND id = %s);
      COMMIT;
      """, (user_id, blog_id,))
      # blog = self.cur.fetchone()
      print(f'Deleted blog: ${blog}')


   def update_blog(self, blog_id, data):
      # Update Category if it's update exists
      if data.get('category'):
         category_id = self.get_category( data['category'] )[0]
         self.delete_categories_blogs(blog_id)
         self.create_categories_blogs(category_id, blog_id)
         data.remove('category')
         
      for key, value in data.items():
         self.cur.execute(f"""
         BEGIN;
         UPDATE blogs SET {key} = %s WHERE id = {blog_id};
         COMMIT;
         """, (value,))


   def like_exists(self, column_id, user_id, an_id):
      """Check whether a like for either the blog_id column or the comment_id column exists"""
      # column is either 'user_id' or 'blog_id'
      if column_id == 'blog_id':
         self.cur.execute("""
            SELECT * FROM likes WHERE (user_id = %s AND blog_id = %s)
         """, (user_id, an_id))
      else:
         self.cur.execute("""
            SELECT * FROM likes WHERE (user_id = %s AND comment_id = %s)
         """, (user_id, an_id))


      like = self.cur.fetchone()
      print(f"like: {like}")
      if like:
         is_like = like[4]
         return (True, is_like)
      return (False, None)


   def create_like(self, column, user_id, an_id, is_like):
      """Creates a like for either the blog_id column or the comment_id column"""
      
      like_exists, is_like_2 = self.like_exists(column, user_id, an_id)
      if like_exists == False:
         # if like doesn't exist, create like
         if column == 'blog_id':      # For Blogs
            self.cur.execute("""
               BEGIN;
               INSERT INTO likes (user_id, blog_id, is_like) VALUES (%s, %s, %s);
               COMMIT;
            """, (user_id, an_id, is_like))
         else:                        # For Comments

            self.cur.execute("""
               BEGIN;
               INSERT INTO likes (user_id, comment_id, is_like) VALUES (%s, %s, %s);
               COMMIT;
            """, (user_id, an_id, is_like))
            
      else:
         # If like does exist change is_like
         if is_like != is_like_2:
            # if user chose to dislike after liking or vice-versa
            if column == 'blog_id':   # For Blogs
               self.cur.execute("""
                  BEGIN;
                  UPDATE likes SET is_like = %s WHERE blog_id = %s;
                  COMMIT;
               """, (is_like, an_id))
            else:                     # For Comments
               self.cur.execute("""
                  BEGIN;
                  UPDATE likes SET is_like = %s WHERE comment_id = %s;
                  COMMIT;
               """, (is_like, an_id))

         else:
            # if user chose to re-like or re-dislike which means remove like or dislike, then remove
            if column == 'blog_id':     # For Blogs
               self.cur.execute("""
                  BEGIN;
                  UPDATE likes SET is_like = %s WHERE blog_id = %s;
                  COMMIT;
               """, (None, an_id))
            else:                       # For Comments
               self.cur.execute("""
                  BEGIN;
                  UPDATE likes SET is_like = %s WHERE comment_id = %s;
                  COMMIT;
               """, (None, an_id))

      return


   def create_comment(self, data):
      owner_id, blog_id, comment_id, content = data.get('owner_id'), data.get('blog_id'), data.get('comment_id'), data.get('content')

      self.cur.execute("""
         BEGIN;
         INSERT INTO comments (content, user_id, blog_id, comment_id)
         VALUES (%s, %s, %s, %s);
         COMMIT;

         SELECT id FROM comments WHERE user_id = %s ORDER BY created_at DESC LIMIT 1;
      """, (content, owner_id, blog_id, comment_id, owner_id,))
      
      comment_id = self.cur.fetchone()[0]
      if (blog_id):
         comment = self.get_comments(owner_id=data.get('owner_id'), blog_id=blog_id)
      else:
         comment = self.get_comments(owner_id=data.get('owner_id'), comment_id=comment_id)

      print(f"Comment: {comment}")
      return comment[0]

         


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
         if is_valid:
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
      token = request.args.get('x-access-token') if request.args.get('x-access-token') else request.headers.get('X-Access-Token')
      print(request.headers.get('X-Access-Token'))

      user = None
      
      if token:
         info = jwt.decode(token, key=os.getenv('FLASK_APP_SECRET'), algorithms=["HS256"])
         db = DbManager()
         user = db.get_user(id=info['user_id'])
         db.close_cur_conn()
      else:
         if f.__name__ not in OPEN_ROUTES:
            return jsonify({'message': 'a valid token is missing'})

      # print(args, kwargs)
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


@app.route("/api/", methods=['GET'])
@token_required
def get_owner(owner=None):
   return jsonify({'owner': owner})


@app.route("/api/owners/blogs")
@token_required
def owners_blogs(owner=None):
   db = DbManager()
   blogs = db.get_user_blogs(owner["id"])
   db.close_cur_conn()
   data = {'blogs': blogs, 'owner': owner}
   return jsonify(data)


@app.route("/api/users/<id>/blogs")
@token_required
def users_blogs(id, owner=None):
   db = DbManager()
   blogs = db.get_user_blogs(id)
   db.close_cur_conn()
   data = {'blogs': blogs, 'owner': owner}
   return jsonify(data)


@app.route("/api/users/<id>")
@token_required
def profile(id, owner=None):
   # print(f"User Id: {id}")
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


# Authentication
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


# Blogs
@app.route("/api/blogs/<id>", methods=["GET"])
@token_required
def blog(id, owner=None):
   db = DbManager()
   blog = db.get_blog(id, owner['id'])
   # liked = db.is_liked('blog_id', owner['id'], blog['id'])
   db.close_cur_conn()
   data = {'blog': blog, 'owner': owner}
   return jsonify(data)


@app.route("/api/blogs", methods=["POST"])
@token_required
def create_blog(owner=None):
   manager = DbManager()
   data = json.loads(request.data)
   data['id'] = owner['id']
   blog = manager.create_blog(data)
   blog_id = blog[0]
   manager.close_cur_conn()

   return jsonify({"id": blog_id})



@app.route("/api/blogs/<id>", methods=["DELETE"])
@token_required
def delete_blog(id, owner=None):
   manager = DbManager()
   user_id = owner['id']
   manager.delete_blog(user_id, id)
   manager.close_cur_conn()

   return jsonify({'message': 'testing'})


@app.route("/api/blogs/<id>", methods=["PUT"])
@token_required
def update_blog(id, owner=None):
   manager = DbManager()
   data = json.loads(request.data)
   print(data)
   manager.update_blog(id, data)
   manager.close_cur_conn()
   return jsonify({"id": id})


@app.route("/api/blogs/<id>/comments", methods=["GET"])
@token_required
def get_blogs_comments(id, owner=None):
   blog_id = id
   manager = DbManager()
   comments = manager.get_comments(owner['id'], blog_id)
   manager.close_cur_conn()
   print(comments)
   return jsonify(comments)


@app.route("/api/comments/<id>/comments", methods=["GET"])
@token_required
def get_comments_comments(id, owner=None):
   comment_id = id
   manager = DbManager()
   comments = manager.get_comments(owner['id'], comment_id=comment_id)
   manager.close_cur_conn()
   print(comments)
   return jsonify(comments)


# LIKES
@app.route("/api/blogs/<id>/likes", methods=["GET"])
@token_required
def like_blog(id, owner=None):
   blog_id = id
   manager = DbManager()
   manager.create_like('blog_id', owner['id'], blog_id, True)
   manager.close_cur_conn()
   return jsonify({"message": 'successful!'})


@app.route("/api/blogs/<id>/dislikes", methods=["GET"])
@token_required
def dislike_blog(id, owner=None):
   blog_id = id
   manager = DbManager()
   manager.create_like('blog_id', owner['id'], blog_id, False)
   manager.close_cur_conn()
   return jsonify({"message": 'successful!'})


@app.route("/api/comments/<id>/likes", methods=["GET"])
@token_required
def like_comment(id, owner=None):
   print('Like Comment....')
   comment_id = id
   manager = DbManager()
   manager.create_like('comment_id', owner['id'], comment_id, True)
   manager.close_cur_conn()
   return jsonify({"message": 'successful!'})


@app.route("/api/comments/<id>/dislikes", methods=["GET"])
@token_required
def dislike_comment(id, owner=None):
   print('DisLike Comment....')
   comment_id = id
   manager = DbManager()
   manager.create_like('comment_id', owner['id'], comment_id, False)
   manager.close_cur_conn()
   return jsonify({"message": 'successful!'})


# Comments
@app.route("/api/comments", methods=["POST"])
@token_required
def create_comment(owner=None):
   manager = DbManager()
   data = json.loads(request.data)
   data['owner_id'] = owner['id']
   comment = manager.create_comment(data)
   manager.close_cur_conn()

   return jsonify(comment)

# Run App
if __name__ == "__main__":
   app.run(debug=True)

