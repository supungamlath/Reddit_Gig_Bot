import discord
import os
import time
import requests
from replit import db
import asyncpraw
from keep_alive import keep_alive

def initDatabase():
  if "posts" not in db.keys():
    db["posts"] = {}
  if "subreddits" not in db.keys():
    db["subreddits"] = ['forhire', 'beermoney', 'slavelabour', 'ForHireFreelance', 'hireanartist', 'hireaprogrammer']
  if "blocked" not in db.keys():
    db["blocked"] = ["[for hire]", "[offer]"]

client = discord.Client()
reddit = asyncpraw.Reddit(client_id=os.environ['ClientID'],
    client_secret=os.environ['ClientSecret'],
    user_agent="PythonPraw", 
    username=os.environ['Username'],
    password=os.environ['Password'])
initDatabase()

async def getNewPosts(subreddit):
  submissions = []
  subreddit = await reddit.subreddit(subreddit)
  async for submission in subreddit.new(limit=10):
    submissions.append(submission)
  return submissions

def checkBlockedWords(title):
  for keyword in db["blocked"]:
    if title.lower().startswith(keyword):
      return True
  return False

def checkAndSavePost(title, subreddit):
  saved_posts = db["posts"]
  saved_subreddit_posts = saved_posts.get(subreddit,[])
  if title not in saved_subreddit_posts:
    saved_subreddit_posts.append(title)
    saved_posts[subreddit] = saved_subreddit_posts
    db["posts"] = saved_posts
    return True
  return False

def formatTimeDelta(seconds):
    seconds = abs(int(seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days > 0:
        return "{:d}d {:d}h {:d}m {:d}s".format(days, hours, minutes, seconds)
    elif hours > 0:
        return "{:d}h {:d}m {:d}s".format(hours, minutes, seconds)
    elif minutes > 0:
        return "{:d}m {:d}s".format(minutes, seconds)
    else:
        return "{:d}s".format(seconds)


def formatPost(post):
  if len(post.selftext) > 150:
    selftext = str("`{:s}...\n`".format(post.selftext[:150]))
  else:
    selftext = str("`{:s}\n`".format(post.selftext))
  text = "\n{:s} - {:s}\n{:s}\n".format(post.title, formatTimeDelta(time.time() - post.created_utc), selftext)
  return text

async def handleSearch(channel):
  for subreddit in db["subreddits"]:
    new_posts = await getNewPosts(subreddit)

    if len(new_posts)==0:
      msg = "\n\n__**No New Posts on r/{:s}**__\n".format(subreddit)
    
    filtered_posts = []
    for post in new_posts:
      if not checkBlockedWords(post.title) and checkAndSavePost(post.title, subreddit):
        filtered_posts.append(post)
    msg = "\n\n__**{:d} Filtered Posts on r/{:s}**__\n".format(len(filtered_posts), subreddit)

    for post in filtered_posts:
      msg += formatPost(post)

    await channel.send(msg)

async def handleView(view, channel):
  async def viewKeyValue(key):
    msg = ""
    for value in db[key]:
      msg += value + "\n"
    await channel.send(msg)

  key = view.split(" ")[1]
  if key in db.keys():
    await viewKeyValue(key)
  else:
    await channel.send("key doesn't exist in database")
    
async def handleAdd(add, channel):
  async def addKeyValue(key):
    new_value = add[len("add " + key):].strip()
    values = db[key]
    if new_value not in values:
      values.append(new_value)
      db[key] = values
      await channel.send("{:s} added to {:s} list".format(new_value, key))
    else:  
      await channel.send("{:s} already added to list".format(key))

  key = add.split(" ")[1]
  if key in db.keys():
    await addKeyValue(key)
  else:
    await channel.send("key doesn't exist in database")

async def handleRemove(remove, channel):
  async def removeKeyValue(key):
    new_value = remove[len("remove " + key):].strip()
    values = db[key]
    if new_value in values:
      values.remove(new_value)
      db[key] = values
      await channel.send("{:s} removed from {:s} list".format(new_value, key))
    else:  
      await channel.send("{:s} not in {:s} list".format(new_value, key))

  key = remove.split(" ")[1]
  if key in db.keys():
    await removeKeyValue(key)
  else:
    await channel.send("key doesn't exist in database")

def getHeader(req ,header):
  if header in req.headers.keys():
    return int(req.headers[header])
  return 0

async def handleLimits(channel):
  r = requests.head(url="https://discord.com/api/v1")
  retry_after = formatTimeDelta(getHeader(r,"Retry-After"))
  req_lim = getHeader(r,"X-RateLimit-Limit")
  req_rem = getHeader(r,"X-RateLimit-Remaining")
  reset = formatTimeDelta(getHeader(r,"X-RateLimit-Reset") - time.time())
  reset_after = formatTimeDelta(getHeader(r,"X-RateLimit-Reset-After"))
  text = """Retry After - {:s}
Requests Limit - {:d} requests
Requests Remaining - {:d} requests
Time to Reset - {:s}
Reset After Time - {:s}""".format(retry_after, req_lim, req_rem, reset, reset_after)
  await channel.send(text)


@client.event
async def on_ready():
  print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
  if message.author.bot:
    return

  msg = message.content
  if not client.is_ws_ratelimited():
    if "search" in msg.lower():
      await handleSearch(message.channel)
    
    if "view" in msg.lower():
      await handleView(msg, message.channel)

    if "add" in msg.lower():
      await handleAdd(msg, message.channel)
    
    if "remove" in msg.lower():
      await handleRemove(msg, message.channel)
    
    if "limits" in msg.lower():
      await handleLimits(message.channel)
      
  else:
    r = requests.head(url="https://discord.com/api/v1")
    print("Rate limited, retry after {:.2f} minutes".format(getHeader(r,"Retry-After")/60))

keep_alive()
client.run(os.environ['TOKEN'])

