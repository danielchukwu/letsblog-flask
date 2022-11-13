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
