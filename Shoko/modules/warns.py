import html
import re
from typing import Optional

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode, User
from telegram import Message, Chat
from telegram.error import BadRequest
from telegram.ext import (
    CommandHandler,
    run_async,
    DispatcherHandlerStop,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
)
from telegram.utils.helpers import mention_html

from Shoko import dispatcher 
from Shoko.modules.disable import DisableAbleCommandHandler
import Shoko.modules.sql.rules_sql as rules_sql
from Shoko.modules.helper_funcs.chat_status import (
    is_user_admin,
    bot_admin,
    user_admin_no_reply,
    user_admin,
    can_restrict,
)
from Shoko.modules.helper_funcs.extraction import (
    extract_text,
    extract_user_and_text,
    extract_user,
)
from Shoko.modules.helper_funcs.filters import CustomFilters
from Shoko.modules.helper_funcs.misc import split_message
from Shoko.modules.helper_funcs.string_handling import split_quotes
from Shoko.modules.helper_funcs.alternate import typing_action
from Shoko.modules.rules import send_rules
from Shoko.modules.log_channel import loggable
from Shoko.modules.sql import warns_sql as sql

WARN_HANDLER_GROUP = 9
CURRENT_WARNING_FILTER_STRING = "<b>Current warning filters in this chat:</b>\n"


# Not async
def warn(
    user: User, chat: Chat, reason: str, message: Message, warner: User = None
) -> str:
    bot = dispatcher.bot
    if is_user_admin(chat, user.id):
        message.reply_text("Damn admins, can't even be warned!")
        return ""
    if not user.id or int(user.id) == 777000 or int(user.id) == 1087968824:
        message.reply_text("This is the Telegram Service Bot or the Group Anonymous Bot. Kinda pointless to warn it, don't you think?")
        return ""
    if warner:
        warner_tag = mention_html(warner.id, warner.first_name)
    else:
        warner_tag = "Automated warn filter."

    limit, soft_warn = sql.get_warn_setting(chat.id)
    num_warns, reasons = sql.warn_user(user.id, chat.id, reason)
    if num_warns >= limit:
        sql.reset_warns(user.id, chat.id)
        if soft_warn:  # kick
            chat.unban_member(user.id)
            reply = "That's {} warnings, {} has been kicked!".format(
                limit, mention_html(user.id, user.first_name)
            )

        else:  # ban
            chat.kick_member(user.id)
            reply = "That's{} warnings, {} has been banned!".format(
                limit, mention_html(user.id, user.first_name)
            )

        for warn_reason in reasons:
            reply += "\n - {}".format(html.escape(warn_reason))

        
        keyboard = None
        log_reason = (
            "<b>{}:</b>"
            "\n#WARN_BAN"
            "\n<b>Admin:</b> {}"
            "\n<b>User:</b> {} (<code>{}</code>)"
            "\n<b>Reason:</b> {}"
            "\n<b>Counts:</b> <code>{}/{}</code>".format(
                html.escape(chat.title),
                warner_tag,
                mention_html(user.id, user.first_name),
                user.id,
                reason,
                num_warns,
                limit,
            )
        )

    else:
        keyboard = [[
            InlineKeyboardButton("Remove warn",
                                 callback_data="rm_warn({})".format(user.id))
        ]]
        rules = rules_sql.get_rules(chat.id)

        if rules:
            keyboard[0].append(
                InlineKeyboardButton("Rules",
                                     url="t.me/{}?start={}".format(
                                         bot.username, chat.id)))

        reply = "User {} has {}/{} warnings... watch out!".format(
            mention_html(user.id, user.first_name), num_warns, limit
        )
        if reason:
            reply += "\nReason for last warn:\n{}".format(html.escape(reason))

        log_reason = (
            "<b>{}:</b>"
            "\n#WARN"
            "\n<b>Admin:</b> {}"
            "\n<b>User:</b> {} (<code>{}</code>)"
            "\n<b>Reason:</b> {}"
            "\n<b>Counts:</b> <code>{}/{}</code>".format(
                html.escape(chat.title),
                warner_tag,
                mention_html(user.id, user.first_name),
                user.id,
                reason,
                num_warns,
                limit,
            )
        )

    try:
        message.reply_text(reply, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)
    except BadRequest as excp:
        if excp.message == "Reply message not found":
            # Do not reply
            message.reply_text(
                reply, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML, quote=False
            )
        else:
            raise
    return log_reason


@run_async
@bot_admin
@loggable
def button(update, context):
    query = update.callback_query  # type: Optional[CallbackQuery]
    user = update.effective_user  # type: Optional[User]
    chat = update.effective_chat  # type: Optional[Chat]
    if match := re.match(r"rm_warn\((.+?)\)", query.data):
        user_id = match.group(1)
        if not is_user_admin(chat, int(user.id)):
                context.bot.answer_callback_query(query.id,
                                                  text="You don't have enough rights to remove users warn.",
                                                  show_alert=True)
                return ""
        res = sql.remove_warn(user_id, chat.id)
        if res:
            update.effective_message.edit_text(
                "Last warn removed by {}.".format(
                    mention_html(user.id, user.first_name)
                ),
                parse_mode=ParseMode.HTML,
            )
            user_member = chat.get_member(user_id)
            return (
                "<b>{}:</b>"
                "\n#UNWARN"
                "\n<b>Admin:</b> {}"
                "\n<b>User:</b> {} (<code>{}</code>)".format(
                    html.escape(chat.title),
                    mention_html(user.id, user.first_name),
                    mention_html(user_member.user.id, user_member.user.first_name),
                    user_member.user.id,
                )
            )
        else:
            update.effective_message.edit_text(
                "This user already has no warns.", parse_mode=ParseMode.HTML
            )

    return ""


@run_async
@user_admin
@can_restrict
@loggable
@typing_action
def warn_user(update, context):
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    warner = update.effective_user  # type: Optional[User]
    args = context.args
    user_id, reason = extract_user_and_text(message, args)

    if user_id:
        if (
            message.reply_to_message
            and message.reply_to_message.from_user.id == user_id
        ):
            return warn(
                message.reply_to_message.from_user,
                chat,
                reason,
                message.reply_to_message,
                warner,
            )
        else:
            return warn(chat.get_member(user_id).user, chat, reason, message, warner)
    else:
        message.reply_text("No user was designated!")
    return ""


@run_async
@user_admin
@bot_admin
@loggable
@typing_action
def reset_warns(update, context):
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    args = context.args
    if user_id := extract_user(message, args):
        sql.reset_warns(user_id, chat.id)
        message.reply_text("Warnings have been reset!")
        warned = chat.get_member(user_id).user
        return (
            "<b>{}:</b>"
            "\n#RESETWARNS"
            "\n<b>Admin:</b> {}"
            "\n<b>User:</b> {} (<code>{}</code>)".format(
                html.escape(chat.title),
                mention_html(user.id, user.first_name),
                mention_html(warned.id, warned.first_name),
                warned.id,
            )
        )
    else:
        message.reply_text("No user has been designated!")
    return ""

@run_async
@bot_admin
@loggable
def sendrules_handler(update, context) -> str:
    query = update.callback_query
    if match := re.match(r"send_rules\((.+?)\)", query.data):
        chat_id = match.group(1)
        send_rules(update, chat_id, True)

    return ""

@run_async
@user_admin
@bot_admin
@loggable
@typing_action
def remove_warns(update, context):
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    args = context.args
    if user_id := extract_user(message, args):
        sql.remove_warn(user_id, chat.id)
        message.reply_text("Last warn has been removed!")
        warned = chat.get_member(user_id).user
        return (
            "<b>{}:</b>"
            "\n#UNWARN"
            "\n<b>• Admin:</b> {}"
            "\n<b>• User:</b> {}"
            "\n<b>• ID:</b> <code>{}</code>".format(
                html.escape(chat.title),
                mention_html(user.id, user.first_name),
                mention_html(warned.id, warned.first_name),
                warned.id,
            )
        )
    else:
        message.reply_text("No user has been designated!")
    return ""


@run_async
@typing_action
def warns(update, context):
    message = update.effective_message  # type: Optional[Message]
    chat = update.effective_chat  # type: Optional[Chat]
    args = context.args
    user_id = extract_user(message, args) or update.effective_user.id
    result = sql.get_warns(user_id, chat.id)
    if result and result[0] != 0:
        num_warns, reasons = result
        limit, soft_warn = sql.get_warn_setting(chat.id)

        if reasons:
            text = "This user has {}/{} warnings, for the following reasons:".format(
                num_warns, limit
            )
            for num, reason in enumerate(reasons, start=1):
                text += "\n {}. {}".format(num, reason)
            msgs = split_message(text)
            for msg in msgs:
                update.effective_message.reply_text(msg)
        else:
            update.effective_message.reply_text(
                "User has {}/{} warnings, but no reasons for any of them.".format(
                    num_warns, limit
                )
            )
    else:
        update.effective_message.reply_text("This user hasn't got any warnings!")


# Dispatcher handler stop - do not async
@user_admin
def add_warn_filter(update, context):
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    args = msg.text.split(
        None, 1
    )  # use python's maxsplit to separate Cmd, keyword, and reply_text

    if len(args) < 2:
        return

    extracted = split_quotes(args[1])

    if len(extracted) < 2:
        return

    # set trigger -> lower, so as to avoid adding duplicate filters with different cases
    keyword = extracted[0].lower()
    content = extracted[1]

    # Note: perhaps handlers can be removed somehow using sql.get_chat_filters
    for handler in dispatcher.handlers.get(WARN_HANDLER_GROUP, []):
        if handler.filters == (keyword, chat.id):
            dispatcher.remove_handler(handler, WARN_HANDLER_GROUP)

    sql.add_warn_filter(chat.id, keyword, content)

    update.effective_message.reply_text("Warn filter added for '{}'!".format(keyword))
    raise DispatcherHandlerStop


@user_admin
def remove_warn_filter(update, context):
    chat = update.effective_chat  # type: Optional[Chat]
    msg = update.effective_message  # type: Optional[Message]

    args = msg.text.split(
        None, 1
    )  # use python's maxsplit to separate Cmd, keyword, and reply_text

    if len(args) < 2:
        return

    extracted = split_quotes(args[1])

    if len(extracted) < 1:
        return

    to_remove = extracted[0]

    chat_filters = sql.get_chat_warn_triggers(chat.id)

    if not chat_filters:
        msg.reply_text("No warning filters are active here!")
        return

    for filt in chat_filters:
        if filt == to_remove:
            sql.remove_warn_filter(chat.id, to_remove)
            msg.reply_text("Yep, I'll stop warning people for that.")
            raise DispatcherHandlerStop

    msg.reply_text(
        "That's not a current warning filter - click: /warnlist for all active warning filters."
    )


@run_async
def list_warn_filters(update, context):
    chat = update.effective_chat  # type: Optional[Chat]
    all_handlers = sql.get_chat_warn_triggers(chat.id)

    if not all_handlers:
        update.effective_message.reply_text("No warning filters are active here!")
        return

    filter_list = CURRENT_WARNING_FILTER_STRING
    for keyword in all_handlers:
        entry = " - {}\n".format(html.escape(keyword))
        if len(entry) + len(filter_list) > telegram.MAX_MESSAGE_LENGTH:
            update.effective_message.reply_text(filter_list, parse_mode=ParseMode.HTML)
            filter_list = entry
        else:
            filter_list += entry

    if filter_list != CURRENT_WARNING_FILTER_STRING:
        update.effective_message.reply_text(filter_list, parse_mode=ParseMode.HTML)


@run_async
@loggable
def reply_filter(update, context) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    message = update.effective_message  # type: Optional[Message]

    chat_warn_filters = sql.get_chat_warn_triggers(chat.id)
    to_match = extract_text(message)
    if not to_match:
        return ""

    for keyword in chat_warn_filters:
        pattern = f"( |^|[^\\w]){re.escape(keyword)}( |$|[^\\w])"
        if re.search(pattern, to_match, flags=re.IGNORECASE):
            user = update.effective_user  # type: Optional[User]
            warn_filter = sql.get_warn_filter(chat.id, keyword)
            return warn(user, chat, warn_filter.reply, message)
    return ""


@run_async
@user_admin
@loggable
@typing_action
def set_warn_limit(update, context) -> str:
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]
    if args := context.args:
        if args[0].isdigit():
            if int(args[0]) < 3:
                msg.reply_text("The minimum warn limit is 3!")
            else:
                sql.set_warn_limit(chat.id, int(args[0]))
                msg.reply_text("Updated the warn limit to {}".format(args[0]))
                return (
                    "<b>{}:</b>"
                    "\n#SET_WARN_LIMIT"
                    "\n<b>Admin:</b> {}"
                    "\nSet the warn limit to <code>{}</code>".format(
                        html.escape(chat.title),
                        mention_html(user.id, user.first_name),
                        args[0],
                    )
                )
        else:
            msg.reply_text("Give me a number as an arg!")
    else:
        limit, soft_warn = sql.get_warn_setting(chat.id)

        msg.reply_text("The current warn limit is {}".format(limit))
    return ""


@run_async
@user_admin
@typing_action
def set_warn_strength(update, context):
    chat = update.effective_chat  # type: Optional[Chat]
    user = update.effective_user  # type: Optional[User]
    msg = update.effective_message  # type: Optional[Message]
    if args := context.args:
        if args[0].lower() in ("on", "yes"):
            sql.set_warn_strength(chat.id, False)
            msg.reply_text("Too many warns will now result in a ban!")
            return (
                "<b>{}:</b>\n"
                "<b>Admin:</b> {}\n"
                "Has enabled strong warns. Users will be banned.".format(
                    html.escape(chat.title), mention_html(user.id, user.first_name)
                )
            )

        elif args[0].lower() in ("off", "no"):
            sql.set_warn_strength(chat.id, True)
            msg.reply_text(
                "Too many warns will now result in a kick! Users will be able to join again after."
            )
            return (
                "<b>{}:</b>\n"
                "<b>Admin:</b> {}\n"
                "Has disabled strong warns. Users will only be kicked.".format(
                    html.escape(chat.title), mention_html(user.id, user.first_name)
                )
            )

        else:
            msg.reply_text("I only understand on/yes/no/off!")
    else:
        limit, soft_warn = sql.get_warn_setting(chat.id)
        if soft_warn:
            msg.reply_text(
                "Warns are currently set to *kick* users when they exceed the limits.",
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            msg.reply_text(
                "Warns are currently set to *ban* users when they exceed the limits.",
                parse_mode=ParseMode.MARKDOWN,
            )
    return ""


def __stats__():
    return (
        "• {} overall warns, across {} chats.\n"
        "• {} warn filters, across {} chats.".format(
            sql.num_warns(),
            sql.num_warn_chats(),
            sql.num_warn_filters(),
            sql.num_warn_filter_chats(),
        )
    )


def __import_data__(chat_id, data):
    for user_id, count in data.get("warns", {}).items():
        for _ in range(int(count)):
            sql.warn_user(user_id, chat_id)


def __migrate__(old_chat_id, new_chat_id):
    sql.migrate_chat(old_chat_id, new_chat_id)


def __chat_settings__(chat_id, user_id):
    num_warn_filters = sql.num_warn_chat_filters(chat_id)
    limit, soft_warn = sql.get_warn_setting(chat_id)
    return (
        "This chat has `{}` warn filters. It takes `{}` warns "
        "before the user gets *{}*.".format(
            num_warn_filters, limit, "kicked" if soft_warn else "banned"
        )
    )


__help__ = """
 If you're looking for a way to automatically warn users when they say certain things, use the /addwarn command.
 An example of setting multiword warns filter:
 - `/addwarn "very angry" This is an angry user`
 This will automatically warn a user that triggers "very angry", with reason of 'This is an angry user'.
 An example of how to set a new multiword warning:
`/warn @user Because warning is fun`

 - /warns <userhandle>: Gets a user's number, and reason, of warnings.
 - /warnlist: Lists all current warning filters

*Admin only:*
 - /warn <userhandle>: Warns a user. After 3 warns, the user will be banned from the group. Can also be used as a reply.
 - /resetwarn <userhandle>: Resets the warnings for a user. Can also be used as a reply.
 - /rmwarn <userhandle>: Removes latest warn for a user. It also can be used as reply.
 - /unwarn <userhandle>: Same as /rmwarn
 - /addwarn <keyword> <reply message>: Sets a warning filter on a certain keyword. If you want your keyword to \
be a sentence, encompass it with quotes, as such: `/addwarn "very angry" This is an angry user`. 
 - /nowarn <keyword>: Stops a warning filter
 - /warnlimit <num>: Sets the warning limit
 - /strongwarn <on/yes/off/no>: If set to on, exceeding the warn limit will result in a ban. Else, will just kick.
"""

__mod_name__ = "Warnings"

WARN_HANDLER = CommandHandler("warn", warn_user, pass_args=True, filters=Filters.group)
RESET_WARN_HANDLER = CommandHandler(
    ["resetwarn", "resetwarns"], reset_warns, pass_args=True, filters=Filters.group
)
REMOVE_WARNS_HANDLER = CommandHandler(
    ["rmwarn", "unwarn"], remove_warns, pass_args=True, filters=Filters.group
)
CALLBACK_QUERY_HANDLER = CallbackQueryHandler(button,
                                              pattern=r"rm_warn")
SENDRULES_QUERY_HANDLER = CallbackQueryHandler(sendrules_handler,
                                               pattern=r"send_rules")
MYWARNS_HANDLER = DisableAbleCommandHandler(
    "warns", warns, pass_args=True, filters=Filters.group
)
ADD_WARN_HANDLER = CommandHandler("addwarn", add_warn_filter, filters=Filters.group)
RM_WARN_HANDLER = CommandHandler(
    ["nowarn", "stopwarn"], remove_warn_filter, filters=Filters.group
)
LIST_WARN_HANDLER = DisableAbleCommandHandler(
    ["warnlist", "warnfilters"], list_warn_filters, filters=Filters.group, admin_ok=True
)
WARN_FILTER_HANDLER = MessageHandler(
    CustomFilters.has_text & Filters.group, reply_filter
)
WARN_LIMIT_HANDLER = CommandHandler(
    "warnlimit", set_warn_limit, pass_args=True, filters=Filters.group
)
WARN_STRENGTH_HANDLER = CommandHandler(
    "strongwarn", set_warn_strength, pass_args=True, filters=Filters.group
)

dispatcher.add_handler(WARN_HANDLER)
dispatcher.add_handler(CALLBACK_QUERY_HANDLER)
dispatcher.add_handler(SENDRULES_QUERY_HANDLER)
dispatcher.add_handler(RESET_WARN_HANDLER)
dispatcher.add_handler(REMOVE_WARNS_HANDLER)
dispatcher.add_handler(MYWARNS_HANDLER)
dispatcher.add_handler(ADD_WARN_HANDLER)
dispatcher.add_handler(RM_WARN_HANDLER)
dispatcher.add_handler(LIST_WARN_HANDLER)
dispatcher.add_handler(WARN_LIMIT_HANDLER)
dispatcher.add_handler(WARN_STRENGTH_HANDLER)
dispatcher.add_handler(WARN_FILTER_HANDLER, WARN_HANDLER_GROUP)
