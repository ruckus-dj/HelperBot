from sqlalchemy.orm import scoped_session
from telegram import Update, Bot

from core.template import fill_char_template
from core.types import User, AdminType, Admin, admin, Group, Squad, Session, SquadMember
from core.utils import send_async
from core.functions.inline_keyboard_handling import generate_squad_list, \
    generate_leave_squad, generate_squad_request, generate_squad_request_answer, generate_fire_up, \
    generate_squad_invite_answer
from core.texts import *


@admin()
def add_squad(bot: Bot, update: Update):
    if update.message.chat.type == 'supergroup':
        session = Session()
        squad = session.query(Squad).filter_by(chat_id=update.message.chat.id).first()
        if squad is None:
            squad = Squad()
            squad.chat_id = update.message.chat.id
            squad.thorns_enabled = False
            msg = update.message.text.split(' ', 1)
            if len(msg) == 2:
                squad.squad_name = msg[1]
            else:
                group = session.query(Group).filter_by(id=update.message.chat.id).first()
                squad.squad_name = group.title
            session.add(squad)
            session.commit()
            send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_NEW.format(squad.squad_name))


@admin()
def set_invite_link(bot: Bot, update: Update):
    session = Session()
    squad = session.query(Squad).filter_by(chat_id=update.message.chat.id).first()
    if update.message.chat.type == 'supergroup' and squad is not None:
        msg = update.message.text.split(' ', 1)
        if len(msg) == 2:
            squad.invite_link = msg[1]
            session.add(squad)
            session.commit()
            send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_LINK_SAVED)


@admin()
def set_squad_name(bot: Bot, update: Update):
    session = Session()
    squad = session.query(Squad).filter_by(chat_id=update.message.chat.id).first()
    if update.message.chat.type == 'supergroup' and squad is not None:
        msg = update.message.text.split(' ', 1)
        if len(msg) == 2:
            squad.squad_name = msg[1]
            session.add(squad)
            session.commit()
            send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_RENAMED.format(squad.squad_name))


@admin()
def del_squad(bot: Bot, update: Update):
    session = Session()
    squad = session.query(Squad).filter_by(chat_id=update.message.chat.id).first()
    if update.message.chat.type == 'supergroup' and squad is not None:
        for member in squad.members:
            session.delete(member)
        session.delete(squad)
        session.commit()
        send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_DELETE)


@admin(AdminType.GROUP)
def enable_thorns(bot: Bot, update: Update):
    session = Session()
    group = session.query(Group).filter_by(id=update.message.chat.id).first()
    if update.message.chat.type == 'supergroup' and group is not None and len(group.squad) == 1:
        group.squad[0].thorns_enabled = True
        session.add(group.squad[0])
        session.commit()
        send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_THORNS_ENABLED)


@admin(AdminType.GROUP)
def disable_thorns(bot: Bot, update: Update):
    session = Session()
    group = session.query(Group).filter_by(id=update.message.chat.id).first()
    if update.message.chat.type == 'supergroup' and group is not None and len(group.squad) == 1:
        group.squad[0].thorns_enabled = False
        session.add(group.squad[0])
        session.commit()
        send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_THORNS_DISABLED)


@admin(AdminType.GROUP)
def squad_list(bot: Bot, update: Update):
    session = scoped_session(Session)()
    admin = session.query(Admin).filter_by(user_id=update.message.from_user.id).all()
    global_adm = False
    for adm in admin:
        if adm.admin_type <= AdminType.FULL.value:
            global_adm = True
            break
    squads = []
    if global_adm:
        squads = session.query(Squad).all()
    else:
        for adm in admin:
            group = session.query(Group).filter_by(id=adm.admin_group).first()
            if len(group.squad) and group.squad[0]:
                squads.append(group.squad[0])
    markup = generate_squad_list(squads)
    send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_LIST, reply_markup=markup)


def squad_request(bot: Bot, update: Update):
    session = Session()
    user = session.query(User).filter_by(id=update.message.from_user.id).first()
    if user is not None:
        if user.character:
            if user.member:
                markup = generate_leave_squad(user.id)
                send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_REQUEST_EXISTS, reply_markup=markup)
            else:
                markup = generate_squad_request()
                send_async(bot, chat_id=update.message.chat.id, text=MSG_SQUAD_REQUEST, reply_markup=markup)
        else:
            send_async(bot, chat_id=update.message.chat.id, text='Сначала дай мне профиль!')


@admin(AdminType.GROUP)
def list_squad_requests(bot: Bot, update: Update):
    session = Session()
    admin = session.query(Admin).filter_by(user_id=update.message.from_user.id).all()
    group_admin = []
    for adm in admin:
        if adm.admin_type == AdminType.GROUP.value and adm.admin_group != 0:
            group_admin.append(adm)
    count = 0
    for adm in group_admin:
        members = session.query(SquadMember).filter_by(squad_id=adm.admin_group, approved=False)
        for member in members:
            count += 1
            markup = generate_squad_request_answer(member.user_id)
            send_async(bot, chat_id=update.message.chat.id,
                       text=fill_char_template(MSG_PROFILE_SHOW_FORMAT, member.user, member.user.character, True),
                       reply_markup=markup)
    if count == 0:
        send_async(bot, chat_id=update.message.chat.id,
                   text=MSG_SQUAD_REQUEST_EMPTY)


@admin(AdminType.GROUP)
def open_hiring(bot: Bot, update: Update):
    session = Session()
    squad = session.query(Squad).filter_by(chat_id=update.message.chat.id).first()
    if squad is not None:
        squad.hiring = True
        session.add(squad)
        session.commit()
        send_async(bot, chat_id=update.message.chat.id, text='Набор открыт')


@admin(AdminType.GROUP)
def close_hiring(bot: Bot, update: Update):
    session = Session()
    squad = session.query(Squad).filter_by(chat_id=update.message.chat.id).first()
    if squad is not None:
        squad.hiring = False
        session.add(squad)
        session.commit()
        send_async(bot, chat_id=update.message.chat.id, text='Набор закрыт')


@admin(AdminType.GROUP)
def remove_from_squad(bot: Bot, update: Update):
    session = Session()
    admin = session.query(Admin).filter_by(user_id=update.message.from_user.id).all()
    group_admin = []
    for adm in admin:
        squad = session.query(Squad).filter_by(chat_id=adm.admin_group).first()
        if squad is not None:
            group_admin.append(adm)
    for adm in group_admin:
        members = session.query(SquadMember).filter_by(squad_id=adm.admin_group)
        markup = generate_fire_up(members)
        squad = session.query(Squad).filter_by(chat_id=adm.admin_group).first()
        send_async(bot, chat_id=update.message.chat.id,
                   text=MSG_SQUAD_CLEAN.format(squad.squad_name),
                   reply_markup=markup)


@admin(AdminType.GROUP)
def add_to_squad(bot: Bot, update: Update):
    session = Session()
    squad = session.query(Squad).filter_by(chat_id=update.message.chat.id).first()
    if squad is not None:
        username = update.message.text.split(' ', 1)
        if len(username) == 2:
            username = username[1].replace('@', '')
            user = session.query(User).filter_by(username=username).first()
            if user is not None and user.character is not None and user.member is None:
                markup = generate_squad_invite_answer(user.id)
                send_async(bot, chat_id=update.message.chat.id,
                           text=MSG_SQUAD_ADD.format('@' + username),
                           reply_markup=markup)
            elif user.member is not None:
                send_async(bot, chat_id=update.message.chat.id,
                           text=MSG_SQUAD_ADD_IN_SQUAD.format('@' + username))
            elif user.character is None:
                send_async(bot, chat_id=update.message.chat.id, text='Сначала пусть даст профиль!')
