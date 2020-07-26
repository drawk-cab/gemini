#!/usr/bin/env python3

import os, re, urllib.parse, logging, datetime, csv

DB_PATH = "/var/gemini/guestbook"
USER_FILE = os.environ.get("USER_FILE","/home/jetforce/users.csv")

USERS = { hash: [name, sponsor, merit] for name,hash,sponsor,merit in csv.reader(open(USER_FILE,"r")) }
NOW = datetime.datetime.now()

def when(then):
  i = NOW - then
  if i>datetime.timedelta(1):
    return then.strftime()
  hours = i.seconds//3600
  if hours>1:
    return f"{hours} hours ago"
  minutes = i.seconds//60
  if minutes>1:
    return f"{minutes} minutes ago"
  return "just now"

user_hash = os.environ.get("TLS_CLIENT_HASH")
if not user_hash:
  print("60 Client certificate required")
  raise SystemExit

user_name = os.environ.get("REMOTE_USER","Anonymous")
user_name = re.sub("[\u0000-\u001f]","",user_name)
query = urllib.parse.unquote(os.environ["QUERY_STRING"])

if user_hash not in USERS:
  USERS[user_hash] = [user_name, None, 0]
  csv.writer(open(USER_FILE,"w")).writerows([[v[0],k,v[1],v[2]] for k,v in USERS.items()])

if int(USERS[user_hash][2]) < 0:
  print("61 This client cannot post")
  raise SystemExit

if not query:
  print(f"10 Hi {user_name}, leave a message")
  raise SystemExit

message = re.sub("[\r\n]+","\r\n",query)+"\r\n"
open(os.path.join(DB_PATH,f"{NOW:%Y%m%d%H%M%S}_{user_hash}.gmi"),"w").write(message)

lines = ["# Guestbook",""]
entries = sorted(os.listdir(DB_PATH))
for entry in entries:
  full_path = os.path.join(DB_PATH,entry)
  if os.path.isfile(full_path):
    m = re.match("([^_]*)_(.*).gmi",entry)
    if not m:
      raise ValueError(entry)
    created_at = when(datetime.datetime.strptime(m.group(1),"%Y%m%d%H%M%S"))
    user_hash = m.group(2)
    message = open(full_path,"r").read()

    user = USERS.get(user_hash,["Unknown",None,0])
    message = re.split("[\r\n]+",message.strip())
    lines.extend([f"> {line}" for line in message])
    lines.extend([f"        - {user[0]} ({user[2]} {user_hash[:3]}) {created_at}",""])

body = "\n".join(lines)
print("20 text/gemini")
print(body)
