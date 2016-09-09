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

URL = "http://www.dota2.com/majorsregistration/list"
MY_TOKEN = os.getenv("SLACK_BOT_TOKEN") # get ur own xd
TABLE = "roster_status"

def log_print(message):
    now = arrow.now()
    now = now.strftime("%Y-%m-%d %H:%M:%S")
    print "[{}] {}".format(now, message)

def get_rows():
    response = requests.get(URL)
    soup = bs4.BeautifulSoup(response.text)
    rows = soup.find_all("div", **{"class": "ConfirmationRow"})
    return rows

def parse_row(row):
    divs = row.find_all("div")
    row = [d.text.strip() for d in divs]
    row = [r.encode("ascii", "ignore") for r in row]
    date, time, _, player, team, action = row
    player = re.sub(" \([^)]*\)$", "", player)
    team = re.sub("\(ID: \d+\)", "", team)
    return (date, time, player, team, action)

def post_to_slack(bot, chatroom, message, no_slack):
    if not no_slack:
        bot.chat.post_message(chatroom, message)

def get_existing_rows(conn):
    cursor = conn.cursor()
    rows = cursor.execute("SELECT * FROM {}".format(TABLE))
    rows = set([(date, time, player, team) for date, time, player, team, action in rows])
    return rows

def add_row(conn, row):
    cursor = conn.cursor()
    cursor.execute("INSERT INTO {} VALUES (?, ?, ?, ?, ?)".format(TABLE), row)

def do_loop(database, slack_token, chatroom, no_slack):
    bot = Slacker(slack_token)
    conn = sqlite3.connect(database)
    existing_rows = get_existing_rows(conn)
    rows = get_rows()
    rows = map(parse_row, rows)
    rows = {(date, time, player, team): (date, time, player, team, action) for (date, time, player, team, action) in rows}
    all_row_keys = set(rows.keys())
    new_row_keys = all_row_keys - existing_rows
    new_row_keys = sorted(new_row_keys)

    for row in new_row_keys:
        row = rows[row]
        date, time, player, team, action = row
        message = "{} {} {} at {} {}".format(player, action, team, date, time)
        log_print(message)
        post_to_slack(bot, chatroom, message, no_slack)
        add_row(conn, row)
    conn.commit()
    conn.close()

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chatroom", help="Chatroom to post to", default="#valveapibotspam")
    parser.add_argument("--database", help="Override database", default="teamliquid.db")
    parser.add_argument("--api-key", help="Override SLACK_BOT_TOKEN env variable")
    parser.add_argument("--no-slack", help="Don't post to slack", action="store_true")
    parser.add_argument("--sleep-time", type=int, help="Time to sleep between runs")
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
    
    conn = sqlite3.connect(args.database)
    conn.execute("CREATE TABLE IF NOT EXISTS roster_status (date text, time text, player_name text, team text, action text)")
    while True:
        log_print("scanning for new players...")
        do_loop(args.database, slack_token, args.chatroom, args.no_slack)
        log_print("done scanning...")
        time.sleep(15)
