from functools import wraps
from telegram import User, Chat, ChatMember

from Shoko import DEL_CMDS, SUDO_USERS, WHITELIST_USERS, REDIS
from Shoko.mwt import MWT


def can_delete(chat: Chat, bot_id: int) -> bool:
    return chat.get_member(bot_id).can_delete_messages


def is_user_ban_protected(chat: Chat, user_id: int, member: ChatMember = None) -> bool:
    if (
        chat.type == "private"
        or user_id in SUDO_USERS
        or user_id in WHITELIST_USERS
        or chat.all_members_are_administrators
    ):
        return True

    if not member:
        member = chat.get_member(user_id)
    return member.status in ("administrator", "creator")


@MWT(timeout=60 * 5)  # Cache admin status for 5 mins to avoid extra requests.
def is_user_admin(chat: Chat, user_id: int, member: ChatMember = None) -> bool:
    if (
        chat.type == "private"
        or user_id in SUDO_USERS
        or user_id == 777000
        or chat.all_members_are_administrators
    ):
        return True

    if not member:
        member = chat.get_member(user_id)
    return member.status in ("administrator", "creator")


def is_bot_admin(chat: Chat, bot_id: int, bot_member: ChatMember = None) -> bool:
    if chat.type == "private" or chat.all_members_are_administrators:
        return True

    if not bot_member:
        bot_member = chat.get_member(bot_id)
    return bot_member.status in ("administrator", "creator")


def is_user_in_chat(chat: Chat, user_id: int) -> bool:
    member = chat.get_member(user_id)
    return member.status not in ("left", "kicked")


def bot_can_delete(func):
    @wraps(func)
    def delete_rights(update, context, *args, **kwargs):
        if can_delete(update.effective_chat, context.bot.id):
            return func(update, context, *args, **kwargs)
        else:
            update.effective_message.reply_text(
                "I can't delete messages here! "
                "Make sure I'm admin and can delete other user's messages."
            )

    return delete_rights


def can_pin(func):
    @wraps(func)
    def pin_rights(update, context, *args, **kwargs):
        if update.effective_chat.get_member(context.bot.id).can_pin_messages:
            return func(update, context, *args, **kwargs)
        else:
            update.effective_message.reply_text(
                "I can't pin messages here! "
                "Make sure I'm admin and can pin messages."
            )

    return pin_rights


def can_promote(func):
    @wraps(func)
    def promote_rights(update, context, *args, **kwargs):
        if update.effective_chat.get_member(context.bot.id).can_promote_members:
            return func(update, context, *args, **kwargs)
        else:
            update.effective_message.reply_text(
                "I can't promote/demote people here! "
                "Make sure I'm admin and can appoint new admins."
            )

    return promote_rights


def can_restrict(func):
    @wraps(func)
    def promote_rights(update, context, *args, **kwargs):
        if update.effective_chat.get_member(context.bot.id).can_restrict_members:
            return func(update, context, *args, **kwargs)
        else:
            update.effective_message.reply_text(
                "I can't restrict people here! "
                "Make sure I'm admin and can appoint new admins."
            )

    return promote_rights


def bot_admin(func):
    @wraps(func)
    def is_admin(update, context, *args, **kwargs):
        if is_bot_admin(update.effective_chat, context.bot.id):
            return func(update, context, *args, **kwargs)
        else:
            update.effective_message.reply_text("I'm not admin!")

    return is_admin


def user_admin(func):
    @wraps(func)
    def is_admin(update, context, *args, **kwargs):
        user = update.effective_user  # type: Optional[User]
        if user and is_user_admin(update.effective_chat, user.id):
            return func(update, context, *args, **kwargs)

        elif not user:
            pass

        elif DEL_CMDS and " " not in update.effective_message.text:
            update.effective_message.delete()

        else:
            update.effective_message.reply_text(
                "You're missing admin rights for using this command!"
            )

    return is_admin


def user_admin_no_reply(func):
    @wraps(func)
    def is_admin(update, context, *args, **kwargs):
        user = update.effective_user  # type: Optional[User]
        if user and is_user_admin(update.effective_chat, user.id):
            return func(update, context, *args, **kwargs)

        elif not user:
            pass

        elif DEL_CMDS and " " not in update.effective_message.text:
            update.effective_message.delete()

    return is_admin


def user_not_admin(func):
    @wraps(func)
    def is_not_admin(update, context, *args, **kwargs):
        user = update.effective_user  # type: Optional[User]
        if user and not is_user_admin(update.effective_chat, user.id):
            return func(update, context, *args, **kwargs)

    return is_not_admin
