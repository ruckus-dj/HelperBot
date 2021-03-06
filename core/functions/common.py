from telegram import Update, Bot, ParseMode, TelegramError
import logging
from core.functions.triggers import trigger_decorator
from core.types import AdminType, Admin, Stock, admin, Session, Group
from core.utils import send_async, add_user
from core.functions.reply_markup import generate_admin_markup
from enum import Enum
from datetime import datetime
from core.texts import *

logger = logging.getLogger(__name__)


class StockType(Enum):
    Stock = 0
    TradeBot = 1


def error(bot: Bot, update, error, **kwargs):
    """ Error handling """
    logger.error("An error (%s) occurred: %s"
                 % (type(error), error.message))


def start(bot: Bot, update: Update):
    add_user(update.message.from_user)
    if update.message.chat.type == 'private':
        send_async(bot, chat_id=update.message.chat.id, text=MSG_START_WELCOME)


@admin(adm_type=AdminType.GROUP)
def admin_panel(bot: Bot, update: Update):
    if update.message.chat.type == 'private':
        session = Session()
        admin = session.query(Admin).filter_by(user_id=update.message.from_user.id).all()
        full_adm = False
        grp_adm = False
        for adm in admin:
            if adm.admin_type <= AdminType.FULL.value:
                full_adm = True
            else:
                grp_adm = True
        send_async(bot, chat_id=update.message.chat.id, text=MSG_ADMIN_WELCOME,
                   reply_markup=generate_admin_markup(full_adm, grp_adm))


def check_bot_in_chats(bot: Bot, update: Update):
    session = Session()
    groups = session.query(Group).filter_by(bot_in_group=True).all()
    for group in groups:
        try:
            bot.getChatMember(group.id, bot.id)
        except TelegramError as e:
            group.bot_in_group = False
            session.add(group)
    session.commit()


@admin()
def kick(bot: Bot, update: Update):
    bot.leave_chat(update.message.chat.id)


@trigger_decorator
def help_msg(bot: Bot, update):
    session = Session()
    admin_user = session.query(Admin).filter_by(user_id=update.message.from_user.id).all()
    global_adm = False
    for adm in admin_user:
        if adm.admin_type <= AdminType.FULL.value:
            global_adm = True
            break
    if global_adm:
        send_async(bot, chat_id=update.message.chat.id, text=MSG_HELP_GLOBAL_ADMIN)
    elif len(admin_user) != 0:
        send_async(bot, chat_id=update.message.chat.id, text=MSG_HELP_GROUP_ADMIN)
    else:
        send_async(bot, chat_id=update.message.chat.id, text=MSG_HELP_USER)


@admin(adm_type=AdminType.GROUP)
def ping(bot: Bot, update: Update):
    send_async(bot, chat_id=update.message.chat.id, text=MSG_PING.format(update.message.from_user.username))


def get_diff(dict_one, dict_two):
    resource_diff_add = {}
    resource_diff_del = {}
    for key, val in dict_one.items():
        if key in dict_two:
            diff_count = dict_one[key] - dict_two[key]
            if diff_count > 0:
                resource_diff_add[key] = diff_count
            elif diff_count < 0:
                resource_diff_del[key] = diff_count
        else:
            resource_diff_add[key] = val
    for key, val in dict_two.items():
        if key not in dict_one:
            resource_diff_del[key] = -val
    resource_diff_add = sorted(resource_diff_add.items(), key=lambda x: x[0])
    resource_diff_del = sorted(resource_diff_del.items(), key=lambda x: x[0])
    return resource_diff_add, resource_diff_del


def stock_compare(bot: Bot, update: Update, chat_data: dict):
    session = Session()
    old_stock = session.query(Stock).filter_by(user_id=update.message.from_user.id,
                                               stock_type=StockType.Stock.value).order_by(Stock.date.desc()).first()
    new_stock = Stock()
    new_stock.stock = update.message.text
    new_stock.stock_type = StockType.Stock.value
    new_stock.user_id = update.message.from_user.id
    new_stock.date = datetime.now()
    session.add(new_stock)
    session.commit()
    if old_stock is not None:
        resources_old = {}
        resources_new = {}
        strings = old_stock.stock.splitlines()
        for string in strings[1:]:
            resource = string.split(' (')
            resource[1] = resource[1][:-1]
            resources_old[resource[0]] = int(resource[1])
        strings = new_stock.stock.splitlines()
        for string in strings[1:]:
            resource = string.split(' (')
            resource[1] = resource[1][:-1]
            resources_new[resource[0]] = int(resource[1])
        resource_diff_add, resource_diff_del = get_diff(resources_new, resources_old)
        msg = MSG_STOCK_COMPARE_HARVESTED
        if len(resource_diff_add):
            for key, val in resource_diff_add:
                msg += MSG_STOCK_COMPARE_FORMAT.format(key, val)
        else:
            msg += MSG_EMPTY
        msg += MSG_STOCK_COMPARE_LOST
        if len(resource_diff_del):
            for key, val in resource_diff_del:
                msg += MSG_STOCK_COMPARE_FORMAT.format(key, val)
        else:
            msg += MSG_EMPTY
        send_async(bot, chat_id=update.message.chat.id, text=msg, parse_mode=ParseMode.HTML)
    else:
        send_async(bot, chat_id=update.message.chat.id, text=MSG_STOCK_COMPARE_WAIT)


@admin(adm_type=AdminType.GROUP)
def delete_msg(bot: Bot, update: Update):
    bot.delete_message(update.message.reply_to_message.chat_id, update.message.reply_to_message.message_id)
    bot.delete_message(update.message.reply_to_message.chat_id, update.message.message_id)


@admin()
def delete_user(bot: Bot, update: Update):
    bot.kickChatMember(update.message.reply_to_message.chat_id, update.message.reply_to_message.from_user.id)
    bot.unbanChatMember(update.message.reply_to_message.chat_id, update.message.reply_to_message.from_user.id)


def trade_compare(bot: Bot, update: Update, chat_data: dict):
    session = Session()
    old_stock = session.query(Stock).filter_by(user_id=update.message.from_user.id,
                                               stock_type=StockType.TradeBot.value).order_by(Stock.date.desc()).first()
    new_stock = Stock()
    new_stock.stock = update.message.text
    new_stock.stock_type = StockType.TradeBot.value
    new_stock.user_id = update.message.from_user.id
    new_stock.date = datetime.now()
    session.add(new_stock)
    session.commit()
    if old_stock is not None:
        items_old = {}
        items_new = {}
        strings = old_stock.stock.splitlines()
        for string in strings:
            if string.startswith('/add_'):
                item = string.split('   ')[1]
                item = item.split(' x ')
                items_old[item[0]] = int(item[1])
        strings = new_stock.stock.splitlines()
        for string in strings:
            if string.startswith('/add_'):
                item = string.split('   ')[1]
                item = item.split(' x ')
                items_new[item[0]] = int(item[1])
        resource_diff_add, resource_diff_del = get_diff(items_new, items_old)
        msg = MSG_STOCK_COMPARE_HARVESTED
        if len(resource_diff_add):
            for key, val in resource_diff_add:
                msg += MSG_STOCK_COMPARE_FORMAT.format(key, val)
        else:
            msg += MSG_EMPTY
        msg += MSG_STOCK_COMPARE_LOST
        if len(resource_diff_del):
            for key, val in resource_diff_del:
                msg += MSG_STOCK_COMPARE_FORMAT.format(key, val)
        else:
            msg += MSG_EMPTY
        send_async(bot, chat_id=update.message.chat.id, text=msg, parse_mode=ParseMode.HTML)
    else:
        send_async(bot, chat_id=update.message.chat.id, text=MSG_STOCK_COMPARE_WAIT)
