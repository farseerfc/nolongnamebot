#!/usr/bin/env python3
# -*- coding: utf-8 -*-

token = "your_telegram_bot_api_token_here"
import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, JobQueue
from datetime import datetime, timedelta
from time import time
from telegram.error import TelegramError, BadRequest
from mwt import MWT

logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

updater = Updater(token)

# how long the interval is to use /admin command
at_admins_ratelimit = 10*60
last_at_admins_dict = dict()

# account name length longer than this is considered as "long name"
long_name_threshold = 100

blacklist_keywords = [ line.strip() for line in open("blacklist.txt") ]

@MWT(timeout=60*60)
def getAdminIds(bot, chat_id):
    admin_ids = list()
    for chat_member in bot.get_chat_administrators(chat_id):
        admin_ids.append(chat_member.user.id)
    return admin_ids

@MWT(timeout=60*60)
def getAdminUsernames(bot, chat_id):
    admins = list()
    for chat_member in bot.get_chat_administrators(chat_id):
        if chat_member.user.username != bot.username:
            admins.append(chat_member.user.username)
    return admins


def start(bot, update):
    update.message.reply_text('''Hello {}, this bot helps restricting spammer accounts with very long names that hits certain keywords. To make it work please invite it into your group and give it admin priviledges to delete messages and ban users.
Current name limit is {}.
The blacklist of keywords in names is {}.'''.format(update.message.from_user.first_name, long_name_threshold, blacklist_keywords))
    logger.debug("Start from {0}".format(update.message.from_user.id))


def source(bot, update):
    update.message.reply_text('Source code: https://github.com/farseerfc/nolongnamebot')
    logger.debug("Source from {0}".format(update.message.from_user.id))


def display_username(user, atuser=True, shorten=False):
    if user.first_name and user.last_name:
        name = "{} {}".format(user.first_name, user.last_name)
    else:
        name = user.first_name
    if shorten:
        return name
    if user.username:
        if atuser:
            name += " (@{})".format(user.username)
        else:
            name += " ({})".format(user.username)
    return name


def ban_user(bot, chat_id, user, update):
    try:
        # using restrict rather than kick
        # because kicking members will post a message
        # which defects the purpose
        if bot.restrict_chat_member(chat_id=chat_id, user_id=user.id):
            update.message.delete()
            logger.info("Banned {0} in the group {1}".format(user.id, chat_id))
        else:
            raise TelegramError
    except (TelegramError, BadRequest):
        bot.send_message(chat_id=chat_id,
                text="Non-admin bot cannot ban: {0}".format(display_username(user)))
        logger.info("Cannot ban {0} in the group {1}".format(user.id, chat_id))



def at_admins(bot, update):
    global last_at_admins_dict, at_admins_ratelimit
    chat_id = update.message.chat.id
    last_at_admins = 0
    if chat_id in last_at_admins_dict:
        last_at_admins = last_at_admins_dict[chat_id]
    job_queue = updater.job_queue
    if time() - last_at_admins < at_admins_ratelimit:
        notice = update.message.reply_text("Please wait for another {0} second(s).".format(at_admins_ratelimit - (time() - last_at_admins)))
        def delete_notice(bot, job):
            try:
                update.message.delete()
            except TelegramError:
                logger.info("Unable to delete at_admin spam message {0} from {1}".format(update.message.message_id, update.message.from_user.id))
            else:
                logger.info("Deleted at_admin spam messages {0} and {1} from {2}".format(update.message.message_id, notice.message_id, update.message.from_user.id))
            notice.delete()
        job_queue.run_once(delete_notice, 5)
        job_queue.start()
        return
    admins = getAdminUsernames(bot, chat_id)
    update.message.reply_text(" ".join("@"+a for a in admins))
    last_at_admins_dict[chat_id] = time()
    logger.info("At_admin sent from {0} {1}".format(update.message.from_user.id, chat_id))

def status_update(bot, update):
    chat_id = update.message.chat_id
    if update.message.new_chat_members:
        users = update.message.new_chat_members
        for user in users:
            username = display_username(user)
            if user.id == bot.id:
                logger.info("Myself joined the group {0}".format(chat_id))
            else:
                if len(username) >= long_name_threshold and any(keyword in username for keyword in blacklist_keywords if len(keyword) > 0):
                    ban_user(bot, chat_id, user, update)
                else:
                    logger.debug("{0} joined the group {1}".format(user.id, chat_id))


updater.dispatcher.add_handler(CommandHandler('start', start))
updater.dispatcher.add_handler(CommandHandler('source', source))
updater.dispatcher.add_handler(CommandHandler('admins', at_admins))
updater.dispatcher.add_handler(CommandHandler('admin', at_admins))
updater.dispatcher.add_handler(MessageHandler(Filters.status_update, status_update))
updater.start_polling()
updater.idle()
