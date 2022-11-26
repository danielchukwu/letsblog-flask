import datetime

# codes ['short', 'characters']

def is_valid_password(password, issue_list):
   if len(password) < 8:
      issue_list.append('short')
      return False

   valid_character_count = 0
   allowed_symbols = ('@', '$', '&', '_', '!')
   for i in password:
      if i.islower():
         valid_character_count += 1
      elif i.isupper():
         valid_character_count += 1
      elif i.isdigit():
         valid_character_count +=1
      elif i in allowed_symbols:
         valid_character_count +=1
      else:
         print(i)
         issue_list.append('characters')
         break

   if len(password) == valid_character_count:
      # valid password
      return True
   else: 
      # invalid password
      return False


def check_username_email(manager, username, email):
   invalid_fields = []
   # Check Username
   if (username):
      for letter in username:
         if letter.islower() or letter == '_':
            continue
         else:
            invalid_fields.append("invalid_username")
      username_exists = manager.username_exists(username)
      if username_exists: invalid_fields.append("username")
   # Check Email
   if (email):
      email_exists = manager.email_exists(email)
      if email_exists: 
         invalid_fields.append("email")

   return invalid_fields


def add_section_and_timeago(record: dict, seen: dict, unseen: dict, seen_group_ids: dict, index: int):
   current = datetime.datetime.now()
   date = record['created_at']
   del record['created_at']

   # Tree
   # seen
      # - today
      # - yesterday
      # - this week
      # - this month
      # - this year
      # - old
      
   # Add record to seen and o to seen or unseen
   def add_seen_unseen(time_period):
      # if record['seen']: seen[time_period].append(record) if seen.get(time_period) else [record]
      # else: unseen[time_period].append(record) if unseen.get(time_period) else [record]
      if record['seen']:
         seen[time_period].append(record)
      else: 
         unseen[time_period].append(record)
   
   # This Year
   if date.year == current.year:
      # This month
      if date.month == current.month:
         # This week
         if (current.day - date.day) <= 7:
            # Yesterday
            if (current.day - date.day) == 1:
               record['section'] = 'yesterday'
               record['ago'] = '1 day ago'
               add_seen_unseen('yesterday ')
            # Today
            elif current.day == date.day:
               record['section'] = 'today'
               add_seen_unseen('today')
               # Hour
               if current.hour == date.hour:
                  minutes_ago = current.minute - date.minute
                  record['ago'] = f'{minutes_ago} minutes ago' if minutes_ago != 1 else f'{minutes_ago} minute ago'
               # Today
               else:
                  hours_ago = current.hour - date.hour
                  record['ago'] = f'{hours_ago} hours ago' if hours_ago != 1 else f'{hours_ago} hour ago'
            # This week
            else:
               record['section'] = 'week'
               days_ago = current.day - date.day
               record['ago'] = f'{days_ago} days ago' if days_ago != 1 else f'{days_ago} day ago'
               add_seen_unseen('this week')
         # This Month
         else:
            record['section'] = 'month'
            weeks_ago = (current.day - date.day) // 7
            record['ago'] = f'{weeks_ago} weeks ago' if weeks_ago != 1 else f'{weeks_ago} week ago'
            add_seen_unseen('this month')
      # This Year
      else:
         record['section'] = 'year'
         months_ago = (current.month - date.month)
         record['ago'] = f'{months_ago} months ago' if months_ago != 1 else f'{months_ago} month ago'
         add_seen_unseen('this year')
   # Old
   else:
      record['section'] = 'old'
      years_ago = (current.year - date.year)
      record['ago'] = f'{years_ago} years ago' if years_ago != 1 else f'{years_ago} year ago'
      add_seen_unseen('old')

   return {'seen': seen, 'unseen': unseen}