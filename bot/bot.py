import sqlite3
import time
import praw
import prawcore
import requests
import logging
import datetime
import dateparser
import os
import re
import yaml
import pymysql
from bs4 import BeautifulSoup
import requests

os.environ['TZ'] = 'UTC'

responded = 0
footer = ""

con = pymysql.connect(
    host=os.environ['MYSQL_HOST'],
    user=os.environ['MYSQL_USER'],
    passwd=os.environ['MYSQL_PASS'],
    db=os.environ['MYSQL_DB']
)



REDDIT_CID=os.environ['REDDIT_CID']
REDDIT_SECRET=os.environ['REDDIT_SECRET']
REDDIT_USER = os.environ['REDDIT_USER']
REDDIT_PASS = os.environ['REDDIT_PASS']
REDDIT_SUBREDDIT= os.environ['REDDIT_SUBREDDIT']
AGENT="python:rGameDeals-messages:2.0b (by dgc1980)"
#AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36"

reddit = praw.Reddit(client_id=REDDIT_CID,
                     client_secret=REDDIT_SECRET,
                     password=REDDIT_PASS,
                     user_agent=AGENT,
                     username=REDDIT_USER)
subreddit = reddit.subreddit(REDDIT_SUBREDDIT)
wikiconfig=[]
apppath='/storage/'

f = open(apppath+"postids.txt","a+")
f.close()


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(message)s',
                    datefmt='%m-%d %H:%M')

def logID(postid):
    f = open(apppath+"postids.txt","a+")
    f.write(postid + "\n")
    f.close()

def check_post(submission):
    con.ping(reconnect=True)
### Find all URLS inside a .self post
    WHITELIST = reddit.subreddit('gamedeals').wiki['gamedealsbot-whitelist'].content_md
    headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.61 Safari/537.36'}
    cookies = {
                'wants_mature_content': '1',
                'birthtime': '-2148631199',
                'lastagecheckage': '1-0-1902' }
    urls = []
    if submission.is_self:
        urls = re.findall('(?:(?:https?):\/\/)?[\w/\-?=%.]+\.[\w/\-?=%.]+', submission.selftext)
        if len(urls) == 0:
            logging.info("NO LINK FOUND skipping: " + submission.title)
            logID(submission.id)
            report = "NO LINK"
            logging.info("Reporting post https://redd.it/" + submission.id + " for " + report)
            submission.report("Bot Report - " + report)

            return
    # remove duplicate URLs
        unique_urls = []
        for url in urls:
          if url in unique_urls:
            continue
          else:
            unique_urls.append(url)

        url = urls[0]    ### use only the first url
### get url for link post
    if not submission.is_self:
      url = submission.url
    report = ""

    today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    monday = today - datetime.timedelta(days=today.weekday())
    datetext = monday.strftime('%Y%m%d')
    if re.search("http.*steampowered.com/app", url) is not None:

      r = requests.get(url,headers=headers,cookies=cookies)

      devmatches = re.findall('<a href="https:\/\/store.steampowered.com\/developer\/.*?">(.*?)<\/a>',r.text,re.DOTALL)
      pubmatches = re.findall('<a href="https:\/\/store.steampowered.com\/publisher\/.*?">(.*?)<\/a>',r.text,re.DOTALL)

      for a in devmatches:
#        print( "*" + a + "*" )
        cursorObj = con.cursor()
        cursorObj.execute("SELECT * FROM devban WHERE dev = %s", (a,) )
        rows = cursorObj.fetchall()
        if len(rows) != 0:
          report = "Bad Dev: " + rows[0][2]
          logging.info("Reporting post https://redd.it/" + submission.id + " for " + report)
          submission.report("Bot Report - " + report)
          return
      for a in pubmatches:
        cursorObj = con.cursor()
        cursorObj.execute('SELECT * FROM pubban WHERE pub= %s', (a,) )
        rows = cursorObj.fetchall()
        if len(rows) != 0:
          report = "Bad Pub: " + rows[0][2]
          logging.info("Reporting post https://redd.it/" + submission.id + " for " + report)
          submission.report("Bot Report - " + report)
          return

      if re.search("tags/en/Free%20to%20Play", r.text) is not None:
        report = "Free-to-Play"
      elif re.search("/tags/en/Software", r.text) is not None:
        report = "Software"
      elif re.search("saleEventBannerStyle", r.text) is not None:
        report = "Larger Sale"
#      elif re.search("WEEK LONG DEAL", r.text) is not None:
#        cursorObj.execute('SELECT * FROM weeklongdeals WHERE week = ' + datetext )
#        rows = cursorObj.fetchall()
#        if len(rows) == 0:
#          report = "WEEK LONG DEAL - No Post Detected"
#        else:
#          report = "WEEK LONG DEAL - https://redd.it/" + rows[0][2]

    elif re.search("steampowered.com.*?filter=weeklongdeals", url) is not None:
      cursorObj = con.cursor()
      cursorObj.execute('SELECT * FROM weeklongdeals WHERE week = ' + datetext )
      rows = cursorObj.fetchall()
      if len(rows) == 0:
        cursorObj = con.cursor()
        cursorObj.execute('INSERT INTO weeklongdeals (week, post) VALUES (%s, %s)', (monday.strftime('%Y%m%d'), submission.id))
        con.commit()
    elif re.search("itch.io", url) is not None:
      try:
        r = requests.get(url,headers=headers,timeout=10)
        if '<span class="buy_message"><span class="sub">Name your own price</span>' in r.text:
          report = "always free game"
      except:
        logging.info("error checking " + url)
#    elif re.search("almart.com", url) is not None:
#      try:
#        r = requests.get(url,headers=headers,timeout=10)
#        if re.search('data-tl-id="ProductSellerInfo-SellerName" tabindex="0">Walmart</a>', r.text.lower()) is None and re.search('sold and shipped by <!-- -->walmart.com', r.text.lower()) is None:
#          report = "Walmart Marketplace item"
#      except:
#        logging.info("error checking " + url)


    else:
      if re.search("(?:https?:\/\/)?(?:www\.)?([\w\-\.]+)\/", url) is not None:
        match1 = re.search("(?:https?:\/\/)?(?:www\.)?([\w\-\.]+)\/", url)
        if match1.group(1) not in WHITELIST:
          logging.info("checking url " + url)
          try:
            r = requests.get(url,headers=headers,timeout=10)
            if re.search("amzn.to|amazon\.co.*tag=|amazon\.com\/.*asin", r.text.lower()) is not None:
              report = "Amazon Affailiates Found"
            elif re.search("(amzn_assoc_tracking_id|amazon-adsystem.com)", r.text.lower()) is not None:
              report = "Amazon Ads found, may be spam"
            elif re.search("g2a.com|cdkeys.com|cjs-cdkeys|g2play|kinguin|mmoga|allkeyshop|instant-gaming|gamivo|eneba", r.text.lower()) is not None:
              report = "UKR Links Found"
            elif re.search("shopify.com|wix.com", r.text.lower()) is not None:
              report = "Wix/Shopify Found check if legit store"
            elif re.search("rakuten.com/r/(.*)[?&]eeid=", r.text.lower()) is not None:
              report = "rakuten referral found"
          except:
            logging.info("error checking " + url)
      elif re.search("(?:https?:\/\/)?(?:www\.)?([\w\-\.]+)", url) is not None:
        match1 = re.search("(?:https?:\/\/)?(?:www\.)?([\w\-\.]+)", url)
        if match1.group(1) not in WHITELIST:
          logging.info("checking url " + url)
          try:
            r = requests.get(url,headers=headers,timeout=10)
            if re.search("amzn.to|amazon\.co.*tag=|amazon\.com\/.*asin", r.text.lower()) is not None:
              report = "Amazon Affailiates Found"
            elif re.search("(amzn_assoc_tracking_id|amazon-adsystem.com)", r.text.lower()) is not None:
              report = "Amazon Ads found, may be spam"
            elif re.search("g2a.com|cdkeys.com|cjs-cdkeys|g2play|kinguin|mmoga|allkeyshop|instant-gaming|gamivo|eneba", r.text.lower()) is not None:
              report = "UKR Links Found"
            elif re.search("shopify.com|wix.com", r.text.lower()) is not None:
              report = "Wix/Shopify Found check if legit store"
            elif re.search("rakuten.com/r/(.*)[?&]eeid=", r.text.lower()) is not None:
              report = "rakuten referral found"
          except:
            logging.info("error checking " + url)
    if report != "":
      logging.info("Reporting post https://redd.it/" + submission.id + " for " + report)
      submission.report("Bot Report - " + report)




while True:
    try:
        logging.info("Initializing bot...")
        for submission in subreddit.stream.submissions():
            if submission.created < int(time.time()) - 86400:
                continue
            if submission.id in open(apppath+'postids.txt').read():
                continue
# Dev Post
            #con.ping(reconnect=True)
            con.ping(reconnect=True)

            cursorObj = con.cursor()
            cursorObj.execute('SELECT * FROM devs WHERE username = %s', (submission.author.name ,  ))
            rows = cursorObj.fetchall()
            if len(rows) > 0:

                  logging.info("Dev/Pub post by " + submission.author.name )
                  cursorObj = con.cursor()
                  cursorObj.execute('SELECT * FROM all_posts WHERE poster = %s AND posttime > %s ', (submission.author.name , int(submission.created_utc) - (86400 * 12)  ))
                  rows = cursorObj.fetchall()
                  if len(rows) > 0:
                      if 1 == 1:
                          logging.info("- dev poromoting within limit")
                          report = "Developer/Publisher submission within 2 weeks of last - https://redd.it/" + rows[0][2]
                          logging.info("Reporting post https://redd.it/" + submission.id + " for " + report)
                          submission.report("Bot Report - " + report)
                  else:
                      logging.info("- post ok")
              #cursorObj = con.cursor()
              #cursorObj.execute('INSERT INTO dev_posts (dev, postid, posttime, reported, poster) VALUES (%s, %s, %s, 0, %s)', (submission.author.name, submission.id, submission.created_utc, submission.author.name))
              #con.commit()
                  logID(submission.id)


            if submission.author_flair_css_class is not None and submission.author_flair_css_class != "":
# Rep Post
              if submission.author_flair_css_class == "rep":
                con.ping(reconnect=True)
                logging.info("Rep post by " + submission.author_flair_text )
                #print ( submission.author_flair_text )
                #print ( submission.author_flair_css_class )
                cursorObj = con.cursor()
                cursorObj.execute('SELECT * FROM rep_posts WHERE rep = %s AND posttime > %s ', (submission.author_flair_text , int(submission.created_utc) - (3600 * 22)  ))
                rows = cursorObj.fetchall()
                if len(rows) > 0:
                    lastpost = '{:.2f}'.format((int(submission.created_utc) - int(rows[0][3]))/3600)
                    #if lastpost > 1.0:
                    if 1 == 1:
                        logging.info("- " + str(lastpost) )
                        logging.info("- last post within last 24 hours")
                        report = "24 hour rule " + lastpost + "hrs https://redd.it/" + rows[0][2]
                        logging.info("Reporting post https://redd.it/" + submission.id + " for " + report)
                        submission.report("Bot Report - " + report)
                else:
                    logging.info("- post ok")
                cursorObj = con.cursor()
                cursorObj.execute('INSERT INTO rep_posts (rep, postid, posttime, reported, poster) VALUES (%s, %s, %s, 0, %s)', (submission.author_flair_text, submission.id, submission.created_utc, submission.author.name))
                con.commit()
                logID(submission.id)

            else:
                con.ping(reconnect=True)
                cursorObj = con.cursor()
                cursorObj.execute('INSERT INTO all_posts (rep, postid, posttime, reported, poster) VALUES (%s, %s, %s, 0, %s)', (submission.author_flair_text, submission.id, submission.created_utc, submission.author.name))
                con.commit()
                check_post(submission)
                logID(submission.id)

    except (prawcore.exceptions.RequestException, prawcore.exceptions.ResponseException):
        logging.info("Error connecting to reddit servers. Retrying in 1 minute...")
        time.sleep(60)
    except Exception as error:
        logging.info("An exception occurred:")
        logging.info(error) # An exception occurred: division by zero
        logging.info("Retrying in 1 minute")
    # handle the exception
        time.sleep(60)
