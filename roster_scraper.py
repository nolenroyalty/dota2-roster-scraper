#!/usr/bin/env python
import requests
import bs4
import re
import sqlite3
import os
import time
from slacker import Slacker
import arrow
import argparse

URL = "http://www.dota2.com/majorsregistration/rosters"
TABLE = "roster_status"

def log_print(message):
    # yeah yeah I'm sure there's a library that does this asciishrug
    now = arrow.now()
    now = now.strftime("%Y-%m-%d %H:%M:%S")
    print u"[{}] {}".format(now, message)

def get_divs():
    response = requests.get(URL)
    soup = bs4.BeautifulSoup(response.text)
    rows = soup.find_all("div", **{"class": "Confirmation"})
    return rows

def div_class(div, class_):
    return div.find_all("div", **{"class": class_})

def maybe_row_from_div(div):
    classes = ("Nickname", "FullName", "TeamName", "TeamID", "Timestamp")
    row = [div_class(div, class_) for class_ in classes]
    row = [c[0].text.strip() if c else None for c in row]
    if all(row): 
        return tuple(row)
    else:
        return None

def get_all_rows():
    divs = get_divs()
    rows = [maybe_row_from_div(div) for div in divs]
    return [row for row in rows if row]

def get_existing_rows(conn):
    cursor = conn.cursor()
    rows = cursor.execute("SELECT * FROM {}".format(TABLE))
    # Don't add "action" to the set here because we don't dedupe on it (see below)
    return set(rows)

def add_row(conn, row):
    cursor = conn.cursor()
    cursor.execute("INSERT INTO {} VALUES (?, ?, ?, ?, ?)".format(TABLE), row)

def do_loop(database, slack_token, chatroom, should_post):
    bot = Slacker(slack_token)
    with sqlite3.connect(database) as conn:
        existing_rows = get_existing_rows(conn)
        all_rows = set(get_all_rows())
        new_rows = all_rows - existing_rows

        for row in sorted(new_rows, key=lambda x:(arrow.get(x[-1], "dddd, DD-MMM-YY HH:mm:ss"))):
            nick, full, team, teamid, time = row
            message = u"{} {} joined {} on {}".format(nick, full, team, time)
            log_print(message)
            if should_post:
                bot.chat.post_message(chatroom, message)
            add_row(conn, row)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chatroom", help="Chatroom to post to", default="#valveapibotspam")
    parser.add_argument("--database", help="Override database", default="teamliquid.db")
    parser.add_argument("--api-key", help="Override SLACK_BOT_TOKEN env variable")
    parser.add_argument("--no-slack", help="Don't post to slack", action="store_true")
    parser.add_argument("--sleep-time", type=int, help="Time to sleep between runs", default=15)
    args = parser.parse_args()
    return args

def get_token(args):
    if args.api_key:
        return args.api_key
    else:
        return os.getenv("SLACK_BOT_TOKEN")

if __name__ == "__main__":
    args = parse_args()
    slack_token = get_token(args)
    should_post = not args.no_slack
    
    conn = sqlite3.connect(args.database)
    conn.execute("CREATE TABLE IF NOT EXISTS roster_status (nick text, full text, team text, teamid text, time text)")
    while True:
        log_print("scanning for new players...")
        do_loop(args.database, slack_token, args.chatroom, should_post)
        log_print("done scanning...")
        time.sleep(args.sleep_time)
