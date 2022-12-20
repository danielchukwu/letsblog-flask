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


def group_record(record: dict, seen: dict, unseen: dict, seen_ids: dict, unseen_ids: dict):
   """Groups a record into either seen or unseen and adds time ago"""
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
      
   # Group record to seen or unseen
   def add_seen_unseen(time_period):
      if not record['seen']: 
         if record['group_id'] in unseen_ids[time_period]:
            index = unseen_ids[time_period][record['group_id']]       # unseen_ids: {'today': {'d5g6rd': index}}
            unseen[time_period][index].append(record)   # unseen: {'today' : [ [{}][{}][{}] ]}
                                                                                    #2
         else:
            if unseen.get(time_period) == None: unseen[time_period] = [[record]]
            else: unseen[time_period].append([record])
            # unseen[time_period] = [[record]] if unseen.get(time_period) == None else unseen[time_period].append([record])     # unseen: {'today' : [[]]}
            # print("UNSEEN")
            # print(unseen)
            index = len( unseen[time_period] ) - 1
            unseen_ids[time_period][record['group_id']] = index   # unseen_ids: {'today': {'ae3rf': index}}
            print("Unseen Ids")
            print(unseen_ids)

      else: 
         # seen[time_period].append(record)
         if record['group_id'] in seen_ids[time_period]:
            index = seen_ids[time_period][record['group_id']]       # seen_ids: {'today': {'d5g6rd': index}}
            seen[time_period][index].append(record)   # seen: {'today' : [ [{}][{}][{}] ]}
                                                                                    #2
         else:
            if seen.get(time_period) == None: seen[time_period] = [[record]]
            else: seen[time_period].append([record])

            index = len( seen[time_period] ) - 1
            seen_ids[time_period][record['group_id']] = index   # unseen_ids: {'today': {'ae3rf': index}}
            print("seen Ids")
            print(seen_ids)

   # Date and Time Grouping Logic
   
   # This Year
   if date.year == current.year:
      # This month
      if date.month == current.month:
         # This week
         if (current.day - date.day) <= 7:
            # Yesterday
            if (current.day - date.day) == 1:
               # record['section'] = 'yesterday'
               record['ago'] = '1 day ago'
               add_seen_unseen('yesterday')
            # Today
            elif current.day == date.day:
               # record['section'] = 'today'
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
               # record['section'] = 'week'
               days_ago = current.day - date.day
               record['ago'] = f'{days_ago} days ago' if days_ago != 1 else f'{days_ago} day ago'
               add_seen_unseen('this_week')
         # This Month
         else:
            # record['section'] = 'month'
            weeks_ago = (current.day - date.day) // 7
            record['ago'] = f'{weeks_ago} weeks ago' if weeks_ago != 1 else f'{weeks_ago} week ago'
            add_seen_unseen('this_month')
      # This Year or Last Month
      else:
         # record['section'] = 'year'
         months_ago = (current.month - date.month)
         record['ago'] = f'{months_ago} months ago' if months_ago != 1 else f'{months_ago} month ago'
         if months_ago == 1:
            add_seen_unseen('last_month')
         else:
            add_seen_unseen('this_year')

   # Old
   else:
      record['section'] = 'old'
      years_ago = (current.year - date.year)
      record['ago'] = f'{years_ago} years ago' if years_ago != 1 else f'{years_ago} year ago'
      add_seen_unseen('old')

   return {'seen': seen, 'unseen': unseen}