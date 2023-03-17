# from ast import arg
from flask_cors import CORS, cross_origin
import utils
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import os
import jwt
import datetime
from dotenv import load_dotenv
import json
import uuid

load_dotenv()  # take environment variables from .env.


ALLOWED_URLS = ["http://localhost:3000"]
OPEN_ROUTES = ['index']  # Routes that don't require authentication
DAYS_TOKEN_LAST = 1

PORT  = 5000
HOST  = '0.0.0.0'
DEBUG = True

# Create flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, origins=ALLOWED_URLS)


# Manage database related tasks
class DbManager:

    def __init__(self) -> None:
        self.conn = psycopg2.connect(
            host=os.getenv("FLASK_APP_DB_HOST"),
            port="5432",
            database=os.getenv("FLASK_APP_DB_DATABASE"),
            user    =os.getenv("FLASK_APP_DB_USERNAME"),
            password=os.getenv("FLASK_APP_DB_PASSWORD")
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
        blogs = [{keys[i]:v for i, v in enumerate(row)} for row in blogs_row]

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
        # print(blogs_row)
        keys = ["id", "title", "content", "img", "user_id", "category"]
        blogs = [{keys[i]:v for i, v in enumerate(row)} for row in blogs_row]

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
        keys = ["id", "title", "content", "img", "user_id", "category",
                "username", "avatar", "name", "location", "bio", "likes", "dislikes"]
        blog = {keys[i]: v for i, v in enumerate(blog_row)}

        self.add_owner_liked_blog([blog], owner_id)

        return blog

    def follow(self, data):
        if (data['follow']):
            self.cur.execute("""
            BEGIN;
            INSERT INTO followers (follower_id, leader_id)
            VALUES (%s, %s);
            COMMIT;
        """, (data['owner_id'], data['leader_id']))
        else:
            self.cur.execute("""
                BEGIN;
                DELETE FROM followers
                WHERE (follower_id = %s AND leader_id = %s);
                COMMIT;
            """, (data['owner_id'], data['leader_id']))

        return

    def is_following(self, user_id, owner_id):
        self.cur.execute("""
            SELECT *
            FROM followers
            WHERE (follower_id = %s AND leader_id = %s);
        """, (owner_id, user_id,))
        following_row = self.cur.fetchone()
        if following_row:
            return True
        else:
            return False

    def get_following_count(self, user_id):
        self.cur.execute("""
            SELECT COUNT(*)
            FROM followers
            WHERE follower_id = %s;
        """, (user_id,))
        following_count_row = self.cur.fetchone()
        # print(f"Following count: {following_count_row}")
        if following_count_row:
            return following_count_row[0]
        else:
            return 0

    def get_followers_count(self, user_id):
        self.cur.execute("""
            SELECT COUNT(*)
            FROM followers
            WHERE leader_id = %s;
        """, (user_id,))
        followers_count_row = self.cur.fetchone()
        # print(f"Followers count: {followers_count_row}")
        if followers_count_row:
            return followers_count_row[0]
        else:
            return 0

    # Grab user with all its major data

    def get_user(self, user_id, owner_id=None):
        self.cur.execute("""
            SELECT id, name, username, email, avatar, cover, bio, location, website, linkedin, facebook, twitter, instagram, youtube, created_at, updated_at 
            FROM users WHERE id = %s
        """, (user_id,))
        user_row = self.cur.fetchone()
        keys = ["id", "name", "username", "email", "avatar", "cover", "bio", "location", "website",
                "linkedin", "facebook", "twitter", "instagram", "youtube", "created_at", "updated_at"]
        user = {keys[i]: v for i, v in enumerate(user_row)}
        user["skills"] = self.get_skills(user_id)
        user["occupation"] = self.get_occupation(user_id)
        user["company"] = self.get_company(user_id)
        user["following_count"] = self.get_following_count(user_id)
        user["followers_count"] = self.get_followers_count(user_id)
        if (owner_id):
            user["following"] = self.is_following(user_id, owner_id)

        return user

    # Grab users followers or following list of users

    def get_follow(self, user_id, owner_id, type):
        if type == 'following':
            self.cur.execute("""
            SELECT leader_id FROM followers WHERE follower_id = %s ORDER BY created_at DESC;
         """, (user_id,))
        elif type == 'followers':
            self.cur.execute("""
            SELECT follower_id FROM followers WHERE leader_id = %s ORDER BY created_at DESC;
         """, (user_id,))

        follow_rows = self.cur.fetchall()
        users_list = []
        for record in follow_rows:
            # print(record[0])
            user = self.get_user_light(record[0], owner_id)
            users_list.append(user)

        return users_list

    # Grab user for mainly frontend following/followers page. (Grabs only name, username, avatar)

    def get_user_light(self, user_id, owner_id=None):
        self.cur.execute("""
            SELECT id, name, username, avatar
            FROM users WHERE id = %s
        """, (user_id,))
        user_row = self.cur.fetchone()
        # print(f'user_row: {user_row}')
        keys = ["id", "name", "username", "avatar"]
        user = {keys[i]: v for i, v in enumerate(user_row)}
        if (owner_id):
            user["following"] = self.is_following(user_id, owner_id)

        return user

    # Create notification

    def create_notification(self, owner_id, junior_id, senior_id,  type):
        # n.id, n.leader_id, n.junior_id, n.senior_id, n.group_id, n.seen, n.type
        try:
            self.cur.execute("""
            BEGIN;
            INSERT INTO notifications (leader_id, junior_id, senior_id, seen, type)
            VALUES (%s, %s, %s, %s, %s);
            COMMIT;
         """, (owner_id, junior_id, senior_id, False, type))
        except:
            print("Notification already exists!")
        print('Notification successfully created!')

    # Get Owners Notifications all types
    # (follow, liked_blog, liked_comment, commented_)

    def get_notifications(self, owner_id):
        # Notification Types
        # follow
        # liked         blog
        # liked       comment
        # comment       blog
        # comment     comment

        # Tree Structure to be returned to the frontend
        # seen
        # - today -> [[], [], ...]
        # - yesterday -> [[], [], ...]
        # - this week -> [[], [], ...]
        # - this month -> [[], [], ...]
        # - this year -> [[], [], ...]
        # - old -> [[], [], ...]
        # unseen
        # - ... (same as the above)
        unseen = {'today': [], 'yesterday': [], 'this_week': [],
                  'this_month': [], 'last_month': [], 'this_year': [], 'old': []}
        seen = {'today': [], 'yesterday': [], 'this_week': [],
                'this_month': [], 'last_month': [], 'this_year': [], 'old': []}
        notifications = {}

        # Get Follow Notifications
        follows = self.get_notification_of_type(
            owner_id, 'follow', unseen, seen)
        # Get liked_blog  Notifications
        liked_blogs = self.get_notification_of_type(
            owner_id, 'liked_blog', unseen, seen)
        # Get liked_comment  Notifications
        liked_comments = self.get_notification_of_type(
            owner_id, 'liked_comment', unseen, seen)
        # Get commented_blog  Notifications
        commented_blogs = self.get_notification_of_type(
            owner_id, 'commented_blog', unseen, seen)

        # Get commented_comment  Notifications
        commented_comment = self.get_notification_of_type(
            owner_id, 'commented_comment', unseen, seen)

        # print("\n\n\n")
        # print({'unseen': unseen, 'seen': seen})

        return {'unseen': unseen, 'seen': seen}

    # Get a particular type of notification

    def get_notification_of_type(self, owner_id, type, unseen, seen):
        # Junior_id will always be a user_id
        # Senior_id will either be a blog_id, comment_id or  user_id
        if type == 'liked_blog' or type == 'commented_blog':
            self.cur.execute("""
            SELECT n.id, n.leader_id, n.junior_id, n.senior_id, n.group_id, n.seen, n.type, n.created_at, s.avatar, s.username, b.img
            FROM notifications as n 
            JOIN users as s ON s.id = n.junior_id 
            JOIN blogs as b ON b.id = n.senior_id
            WHERE (leader_id = %s AND type = %s)
            ORDER BY n.created_at DESC;
         """, (owner_id, type))
            keys = ['id', 'leader_id', 'junior_id', 'senior_id', 'group_id',
                    'seen', 'type', 'created_at', 'avatar', 'username', 'blog_img']
        else:
            # For type == 'liked_comment' or type == 'commented_comment' or type == 'follow'
            self.cur.execute("""
            SELECT n.id, n.leader_id, n.junior_id, n.senior_id, n.group_id, n.seen, n.type, n.created_at, s.avatar, s.username
            FROM notifications as n 
            JOIN users as s ON s.id = n.junior_id
            WHERE (leader_id = %s AND type = %s)
            ORDER BY n.created_at DESC;
         """, (owner_id, type))
            keys = ['id', 'leader_id', 'junior_id', 'senior_id', 'group_id',
                    'seen', 'type', 'created_at', 'avatar', 'username']
        notifications_raw = self.cur.fetchall()
        records = [{keys[i]: v for i, v in enumerate(
            row)} for row in notifications_raw]
        # print("notifications_raw: ")
        # print(f"owner_id: {owner_id}\ntype: {type}")
        # print(notifications_raw)

        # Generate a random uuid to group unseen notifications
        # (for a particular notification type that is)
        group_id = str(uuid.uuid4())

        # Use this structure to group comments that are alike
        seen_ids = {'today': {}, 'yesterday': {}, 'this_week': {},
                    'this_month': {}, 'last_month': {}, 'this_year': {}, 'old': {}}
        unseen_ids = {'today': {}, 'yesterday': {}, 'this_week': {},
                      'this_month': {}, 'last_month': {}, 'this_year': {}, 'old': {}}

        # Add Section and Time Ago
        for record in records:
            if record['group_id'] == None:
                record['group_id'] = group_id
            utils.group_record(record, seen, unseen, seen_ids, unseen_ids)

        # Insert group id to records in database
        self.cur.execute("""
         BEGIN;
         UPDATE notifications SET group_id = %s WHERE (leader_id = %s AND type = %s and seen = %s); 
         COMMIT;
      """, (group_id, owner_id, type, False,))

        # Set all notification records fetched to seen
        self.update_notifications_to_seen(owner_id, type)

        # return {'unseen': unseen, 'seen': seen}
        return {'seen': seen, 'unseen': unseen}

    # Grabs the unseen notifications count of a user (preferably the owner)

    def get_unseen_notification_count(self, owner_id):
        ...
        self.cur.execute("""
         SELECT COUNT(*) FROM notifications WHERE (leader_id = %s AND seen = %s);
      """, (owner_id, False))
        count_raw = self.cur.fetchone()

        return count_raw[0]

    # Update fetched notifications to seen

    def update_notifications_to_seen(self, owner_id, type):
        self.cur.execute("""
         BEGIN;
         UPDATE notifications
         SET seen = true
         WHERE (leader_id = %s AND type = %s);
         COMMIT;
      """, (owner_id, type))
        # ...
        # return

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

            # print('LIKES and DISLIKES')
            # print(blog['liked'], blog['disliked'])

        return

    def add_sub_comments_count(self, comments_list):
        for comment in comments_list:
            self.cur.execute("""
            SELECT COUNT(*)
            FROM comments
            WHERE comments.comment_id = %s;
         """, (comment['id'],))

            comment['sub_comments_count'] = self.cur.fetchone()[0]

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
            # print('get comments on Comments')
            # print(comment_id)
            self.cur.execute("""
            SELECT comments.id, user_id, blog_id, comment_id, content, users.username, users.avatar
            FROM comments 
            JOIN users ON users.id = comments.user_id
            WHERE comment_id = %s
            ORDER BY comments.created_at DESC;
         """, (comment_id,))

        comments_raw = self.cur.fetchall()
        keys = ["id", "user_id", "blog_id", "comment_id",
                "content", "username", "avatar"]
        comments = [{keys[i]:v for i, v in enumerate(
            row)} for row in comments_raw]

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
        self.cur.execute(
            "SELECT username FROM users WHERE username = %s", (username,))
        username = self.cur.fetchone()
        # print(username)
        if username:
            return True
        else:
            return False

    def email_exists(self, email):
        self.cur.execute("SELECT email FROM users WHERE email = %s", (email,))
        email = self.cur.fetchone()
        # print(email)
        if email:
            return True
        else:
            return False

    def update_user(self, user_id, data: dict(), type):
        if type == 'main':
            for key, value in data.items():
                self.cur.execute(f"""
            BEGIN;
            UPDATE users SET {key} = %s WHERE id = {user_id};
            COMMIT;
            """, (value,))
        elif type == 'others':
            # update occupation
            if data.get('occupation'):
                self.add_occupation(user_id, data.get('occupation'))

            # update company
            if data.get('company'):
                self.add_company(user_id, data.get('company'))
            # remove skills
            if len(data.get('removed_skills')):
                self.remove_skills(user_id, data.get('removed_skills'))
            # skills
            if len(data.get('skills')):
                self.add_skills(user_id, data.get('skills'))

    def get_or_create_skill(self, skill):
        self.cur.execute("SELECT * FROM skills WHERE title = %s", (skill,))
        skill_row = self.cur.fetchone()
        if skill_row != None:
            # skill exists. return skill id
            return skill_row[0]
        else:
            # create skill. and return skill id
            self.cur.execute("""
         BEGIN;
         INSERT INTO skills (title) VALUES (%s);
         COMMIT;
         """, (skill,))
            return self.get_or_create_skill(skill)

    def add_skills(self, user_id, skillList):
        skill_ids = []
        for skill in skillList:
            # Get ids for all skills
            skill_ids.append(self.get_or_create_skill(skill))

        # Create skills_users relationship
        for skill_id in skill_ids:
            try:
                self.cur.execute("""
               BEGIN;
               INSERT INTO skills_users (skill_id, user_id)
               VALUES (%s, %s);
               COMMIT;
            """, (skill_id, user_id,))
            except:
                continue

    def remove_skills(self, user_id, skillList):
        skill_ids = []
        for skill in skillList:
            # Get ids for all skills
            skill_ids.append(self.get_or_create_skill(skill))

        # Create skills_users relationship
        for skill_id in skill_ids:
            self.cur.execute("""
            BEGIN;
            DELETE FROM skills_users
            WHERE (skill_id = %s AND user_id = %s);
            COMMIT;
         """, (skill_id, user_id,))

    def add_occupation(self, user_id, occupation):
        # fetch occupation
        self.cur.execute(
            "SELECT * FROM occupations WHERE title = %s;", (occupation.lower(),))
        occupation_row = self.cur.fetchone()

        if occupation_row:
            # if occupation exists.
            # Create occupations_users relationship
            occupation_id = occupation_row[0]
            self.cur.execute("""
            BEGIN;

            DELETE FROM occupations_users WHERE user_id = %s;
            
            INSERT INTO occupations_users (occupation_id, user_id)
            VALUES (%s, %s);
            COMMIT;
         """, (user_id, occupation_id, user_id,))
        else:
            # if occupation doesn't exist. Create it
            self.cur.execute("""
            BEGIN;
            INSERT INTO occupations (title)
            VALUES (%s);
            COMMIT;
         """, (occupation.lower(),))

            # After creating occupation. Make Recursive call
            # to create occupations_users relationship
            self.add_occupation(user_id, occupation)

    def add_company(self, user_id, company):
        # fetch company
        self.cur.execute(
            "SELECT * FROM companies WHERE title = %s;", (company.lower(),))
        company_row = self.cur.fetchone()

        if company_row:
            # if company exists.
            # Create companies_users relationship
            company_id = company_row[0]
            self.cur.execute("""
            BEGIN;

            DELETE FROM companies_users WHERE user_id = %s;

            INSERT INTO companies_users (company_id, user_id)
            VALUES (%s, %s);
            COMMIT;
         """, (user_id, company_id, user_id,))
        else:
            # if company doesn't exist. Create it
            self.cur.execute("""
            BEGIN;
            INSERT INTO companies (title)
            VALUES (%s);
            COMMIT;
         """, (company.lower(),))

            # After creating company. Make Recursive call
            # to create companies_users relationship
            self.add_company(user_id, company)

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
            category_record = self.get_category(
                category_title)   # Recursive call
            return category_record

    def create_category(self, title):
        self.cur.execute("""
      BEGIN;
      INSERT INTO categories (title) 
      VALUES (%s);
      COMMIT;
      """, (title,))

    def create_categories_blogs(self, cat_id, b_id):
        # print(f'Create Categories and Blogs Relationship WIth: {cat_id} {b_id}')

        self.cur.execute("""
      BEGIN;
      INSERT INTO categories_blogs (category_id, blog_id)
      VALUES (%s, %s);
      COMMIT;
      """, (cat_id, b_id,))
        # print("categories_blogs record updated")
        return

    def delete_categories_blogs(self, b_id):
        # print(f'Remove Categories and Blogs Relationship: {b_id}')
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
        # print(f'Deleted blog: ${blog}')

    def update_blog(self, blog_id, data):
        # Update Category if it's update exists
        if data.get('category'):
            category_id = self.get_category(data['category'])[0]
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
        # print(f"like: {like}")
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
                  UPDATE likes SET is_like = %s WHERE (blog_id = %s AND user_id = %s);
                  COMMIT;
               """, (is_like, an_id, user_id))
                else:                     # For Comments
                    self.cur.execute("""
                  BEGIN;
                  UPDATE likes SET is_like = %s WHERE (comment_id = %s AND user_id = %s);
                  COMMIT;
               """, (is_like, an_id, user_id))

            else:
                # if user chose to re-like or re-dislike which means remove like or dislike, then remove
                if column == 'blog_id':     # For Blogs
                    self.cur.execute("""
                  BEGIN;
                  UPDATE likes SET is_like = %s WHERE (blog_id = %s AND user_id = %s);
                  COMMIT;
               """, (None, an_id, user_id))
                else:                       # For Comments
                    self.cur.execute("""
                  BEGIN;
                  UPDATE likes SET is_like = %s WHERE (comment_id = %s AND user_id = %s);
                  COMMIT;
               """, (None, an_id, user_id))

        return

    def create_comment(self, data):
        owner_id, blog_id, comment_id, content = data.get('owner_id'), data.get(
            'blog_id'), data.get('comment_id'), data.get('content')

        self.cur.execute("""
         BEGIN;
         INSERT INTO comments (content, user_id, blog_id, comment_id)
         VALUES (%s, %s, %s, %s);
         COMMIT;

         SELECT comments.id, user_id, blog_id, comment_id, content, users.username, users.avatar
         FROM comments 
         JOIN users ON users.id = comments.user_id
         WHERE users.id = %s
         ORDER BY comments.created_at DESC
         LIMIT 1;
      """, (content, owner_id, blog_id, comment_id, owner_id,))

        comments_raw = self.cur.fetchall()
        keys = ["id", "user_id", "blog_id", "comment_id",
                "content", "username", "avatar"]
        comments = [{keys[i]:v for i, v in enumerate(
            row)} for row in comments_raw]

        self.add_comments_likes(comments)
        self.add_owner_liked_comment(comments, owner_id)
        self.add_sub_comments_count(comments)

        # print(f"Comment: {comments}")
        return comments[0]

    def update_avatar(self, data):
        # update avatar
        self.cur.execute("""
         BEGIN;
         UPDATE users SET avatar = %s WHERE id = %s;
         COMMIT;
      """, (data["avatar"], data["owner_id"]))

    def update_cover(self, data):
        self.cur.execute("""
         BEGIN;
         UPDATE users SET cover = %s WHERE id = %s;
         COMMIT;
      """, (data["cover"], data["owner_id"]))

    def close_cur_conn(self):
        self.cur.close()
        self.conn.close()


# Authenticate User
class UserManager:

    def __init__(self, cur, request) -> None:
        self.cur = cur
        self.request = request

    # Login

    def login(self, **kwargs) -> tuple:
        """
        Returns a user Object if the forms username and password is valid
        """
        username, password = kwargs['username'].strip(
        ), kwargs['password'].strip()
        self.cur.execute(
            'SELECT id, username, password FROM users WHERE username = %s', (username,))
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
        username = body['username'].lower()
        name = body['name'].lower()
        email = body['email']
        occupation = body['occupation'].title()
        company = body['company'].title()
        password = body['password']
        password_hash = generate_password_hash(password)

        manager = DbManager()
        invalid_fields = utils.check_username_email(manager, username, email)
        manager.close_cur_conn()

        # Check Password
        utils.is_valid_password(password, invalid_fields)

        # print(f'Invalid Fields: ${invalid_fields}')
        if len(invalid_fields) == 0:
            # Form is valid
            user = self.create_user(
                username, name, email, occupation, company, password_hash)
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
        self.cur.execute(
            'SELECT * FROM users WHERE username = %s;', (username,))
        user = self.cur.fetchone()
        user_id = user[0]

        # Add Occupation
        self.add_occupation(user_id, occupation_title)

        # Add Company
        self.add_company(user_id, company_title)

        return user

    # for create_user

    def add_occupation(self, user_id, occupation):
        # fetch occupation
        self.cur.execute(
            "SELECT * FROM occupations WHERE title = %s;", (occupation.lower(),))
        occupation_row = self.cur.fetchone()

        if occupation_row:
            # if occupation exists.
            # Create occupations_users relationship
            occupation_id = occupation_row[0]
            self.cur.execute("""
            BEGIN;
            INSERT INTO occupations_users (occupation_id, user_id)
            VALUES (%s, %s);
            COMMIT;
         """, (occupation_id, user_id,))
        else:
            # if occupation doesn't exist. Create it
            self.cur.execute("""
            BEGIN;
            INSERT INTO occupations (title)
            VALUES (%s);
            COMMIT;
         """, (occupation.lower(),))

            # After creating occupation. Make Recursive call
            # to create occupations_users relationship
            self.add_occupation(user_id, occupation)

    def add_company(self, user_id, company):
        # fetch company
        self.cur.execute(
            "SELECT * FROM companies WHERE title = %s;", (company.lower(),))
        company_row = self.cur.fetchone()

        if company_row:
            # if company exists.
            # Create companies_users relationship
            company_id = company_row[0]
            self.cur.execute("""
            BEGIN;
            INSERT INTO companies_users (company_id, user_id)
            VALUES (%s, %s);
            COMMIT;
         """, (company_id, user_id,))
        else:
            # if company doesn't exist. Create it
            self.cur.execute("""
            BEGIN;
            INSERT INTO companies (title)
            VALUES (%s);
            COMMIT;
         """, (company.lower(),))

            # After creating company. Make Recursive call
            # to create companies_users relationship
            self.add_company(user_id, company)


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
#          data = jwt.decode(token, os.getenv('FLASK_APP_JWT_SECRET_KEY'), algorithms=["HS256"])
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
        token = request.headers.get('x-access-token') or request.args.get('x-access-token')
        user = None
        print(token)

        if token:
            info = jwt.decode(token, key=os.getenv(
                'FLASK_APP_JWT_SECRET_KEY'), algorithms=["HS256"])
            db = DbManager()
            user = db.get_user(user_id=info['user_id'])
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




# Routes
@app.route("/api/", methods=['GET'])
@token_required
def index(owner=None):
    db = DbManager()
    blogs = db.get_blogs()
    db.close_cur_conn()
    return jsonify(blogs)


@app.route("/api/users/me", methods=['GET'])
@token_required
def get_owner(owner=None):
    db = DbManager()
    owner['notifications_count'] = db.get_unseen_notification_count(
        owner['id'])
    db.close_cur_conn()
    return jsonify(owner)


@app.route("/api/users/<id>/blogs")
@token_required
def users_blogs(id, owner=None):
    db = DbManager()
    blogs = db.get_user_blogs(id)
    db.close_cur_conn()
    return jsonify(blogs)


@app.route("/api/users/<id>")
@token_required
def profile(id, owner=None):
    # print(f"User Id: {id}")
    if request.method == "GET":
        db = DbManager()
        user = db.get_user(id, owner['id'])
        db.close_cur_conn()
        return jsonify(user)
    else:
        return jsonify("Backend Response: successfully arrived.")


@app.route("/api/users/<id>", methods=["PUT"])
def update_profile(id, owner=None):
    manager = DbManager()
    data = json.loads(request.data)
    username, email = data.get("username"), data.get("email")
    invalid_fields = utils.check_username_email(manager, username, email)

    # If data is valid. Update data
    if len(invalid_fields) == 0:
        manager.update_user(id, data, 'main')
        manager.close_cur_conn()
    else:
        manager.close_cur_conn()
        return jsonify({"invalid_fields": invalid_fields})

    return jsonify({"message": "successful"})


@app.route("/api/users/update", methods=["PUT"])
@token_required
def update_profile_2(owner=None):
    manager = DbManager()
    data = json.loads(request.data)
    manager.update_user(owner['id'], data, 'others')
    # print(f'data: {data}')
    manager.close_cur_conn()

    return {'message': 'successful'}


# Authentication
@app.route("/api/login", methods=["POST"], strict_slashes=False)
def login():
    db = DbManager()
    username, password = request.json['username'], request.json['password']
    manager = UserManager(db.cur, request)
    user = manager.login(username=username, password=password)
    db.close_cur_conn()

    if user:
        token = jwt.encode({'user_id': user[0], 'exp': datetime.datetime.utcnow(
        ) + datetime.timedelta(days=DAYS_TOKEN_LAST)}, os.getenv('FLASK_APP_JWT_SECRET_KEY'), "HS256")
        return jsonify({'token': token})
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
    # data = {'blog': blog, 'owner': owner}
    return jsonify(blog)


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
    # print(data)
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
    # print(comments)
    return jsonify(comments)


@app.route("/api/comments/<id>/comments", methods=["GET"])
@token_required
def get_comments_comments(id, owner=None):
    comment_id = id
    manager = DbManager()
    comments = manager.get_comments(owner['id'], comment_id=comment_id)
    manager.close_cur_conn()
    # print(comments)
    return jsonify(comments)


# LIKES
@app.route("/api/blogs/<id>/likes", methods=["POST"])
@token_required
def like_blog(id, owner=None):
    manager = DbManager()
    data = json.loads(request.data)
    # print("liked: ")
    # print(data)
    manager.create_like('blog_id', owner['id'], id, True)
    if owner['id'] != data.get('user_id'):
        manager.create_notification(owner_id=data.get(
            'user_id'), junior_id=owner['id'], senior_id=id, type='liked_blog')
    manager.close_cur_conn()
    return jsonify({"message": 'successful'})


@app.route("/api/blogs/<id>/dislikes", methods=["POST"])
@token_required
def dislike_blog(id, owner=None):
    blog_id = id
    manager = DbManager()
    manager.create_like('blog_id', owner['id'], blog_id, False)
    manager.close_cur_conn()
    return jsonify({"message": 'successful'})


@app.route("/api/comments/<id>/likes", methods=["POST"])
@token_required
def like_comment(id, owner=None):
    comment_id = id
    manager = DbManager()
    data = json.loads(request.data)
    # print('data')
    # print(data)
    manager.create_like('comment_id', owner['id'], comment_id, True)
    if owner['id'] != data.get('user_id'):
        manager.create_notification(owner_id=data.get(
            'user_id'), junior_id=owner['id'], senior_id=id, type='liked_comment')
    manager.close_cur_conn()

    return jsonify({"message": 'successful'})


@app.route("/api/comments/<id>/dislikes", methods=["POST"])
@token_required
def dislike_comment(id, owner=None):
    comment_id = id
    manager = DbManager()
    manager.create_like('comment_id', owner['id'], comment_id, False)
    manager.close_cur_conn()
    return jsonify({"message": 'successful'})


# Comments
@app.route("/api/comments", methods=["POST"])
@token_required
def create_comment(owner=None):
    manager = DbManager()
    data = json.loads(request.data)
    # print("comment: ")
    # print(data)
    data['owner_id'] = owner['id']
    comment = manager.create_comment(data)
    if owner['id'] != data.get('user_id'):
        if (data.get('blog_id')):
            # commented_blog
            manager.create_notification(owner_id=data.get(
                'user_id'), junior_id=owner['id'], senior_id=data.get('blog_id'), type='commented_blog')
        else:
            # commented_comment
            manager.create_notification(owner_id=data.get(
                'user_id'), junior_id=owner['id'], senior_id=data.get('comment_id'), type='commented_comment')

    manager.close_cur_conn()
    return jsonify(comment)


# Follow
@app.route("/api/users/follow", methods=["POST"])
@token_required
def follow(owner=None):
    manager = DbManager()
    data = json.loads(request.data)
    data['owner_id'] = owner['id']
    manager.follow(data)
    manager.create_notification(
        data['leader_id'], owner['id'], data['leader_id'], 'follow')
    manager.close_cur_conn()

    return jsonify({"message": 'successful'})


@app.route("/api/users/<id>/following", methods=["GET"])
@token_required
def get_following(id, owner=None):
    manager = DbManager()
    following_list = manager.get_follow(id, owner['id'], type="following")
    # print(following_list)
    manager.close_cur_conn()

    return jsonify(following_list)


@app.route("/api/users/<id>/followers", methods=["GET"])
@token_required
def get_followers(id, owner=None):
    manager = DbManager()
    followers_list = manager.get_follow(id, owner['id'], type="followers")
    manager.close_cur_conn()

    return jsonify(followers_list)


# Notifications
@app.route("/api/users/notifications", methods=["GET"])
@token_required
def get_notifications(owner=None):
    manager = DbManager()
    notifications = manager.get_notifications(owner['id'])
    manager.close_cur_conn()

    return jsonify(notifications)


# Update Owners Avatar
@app.route("/api/users/avatar", methods=["POST"])
@token_required
def update_avatar(owner=None):
    manager = DbManager()
    data = json.loads(request.data)
    data["owner_id"] = owner["id"]
    manager.update_avatar(data)
    # print(data)
    manager.close_cur_conn()

    return jsonify({"message": 'successful'})


# Update Owners Cover
@app.route("/api/users/cover", methods=["POST"])
@token_required
def update_cover(owner=None):
    manager = DbManager()
    data = json.loads(request.data)
    data["owner_id"] = owner["id"]
    manager.update_cover(data)
    manager.close_cur_conn()

    return jsonify({"message": 'successful'})


# Run App
if __name__ == "__main__":
    print(os.getenv("FLASK_APP_DB_HOST"))
    print(os.getenv("FLASK_APP_DB_DATABASE"))
    print(os.getenv("FLASK_APP_DB_USERNAME"))
    print(os.getenv("FLASK_APP_DB_PASSWORD"))
    app.run(port=5000, debug=False, host='0.0.0.0')