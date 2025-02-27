import re
import sre_constants

import telegram
from telegram.ext import Filters, run_async

from Shoko import dispatcher, LOGGER
from Shoko.modules.disable import DisableAbleMessageHandler

DELIMITERS = ("/", ":", "|", "_")


def infinite_checker(repl):
    regex = [
        r"\((.{1,}[\+\*]){1,}\)[\+\*].",
        r"[\(\[].{1,}\{\d(,)?\}[\)\]]\{\d(,)?\}",
        r"\(.{1,}\)\{.{1,}(,)?\}\(.*\)(\+|\* |\{.*\})",
    ]
    for match in regex:
        status = re.search(match, repl)
        return bool(status)


def separate_sed(sed_string):
    if (
        len(sed_string) < 3
        or sed_string[1] not in DELIMITERS
        or sed_string.count(sed_string[1]) < 2
    ):
        return
    delim = sed_string[1]
    start = counter = 2
    while counter < len(sed_string):
        if sed_string[counter] == "\\":
            counter += 1

        elif sed_string[counter] == delim:
            replace = sed_string[start:counter]
            counter += 1
            start = counter
            break

        counter += 1

    else:
        return None

    while counter < len(sed_string):
        if (
            sed_string[counter] == "\\"
            and counter + 1 < len(sed_string)
            and sed_string[counter + 1] == delim
        ):
            sed_string = sed_string[:counter] + sed_string[counter + 1 :]

        elif sed_string[counter] == delim:
            replace_with = sed_string[start:counter]
            counter += 1
            break

        counter += 1
    else:
        return replace, sed_string[start:], ""

    flags = sed_string[counter:] if counter < len(sed_string) else ""
    return replace, replace_with, flags.lower()


@run_async
def sed(update, context):
    sed_result = separate_sed(update.effective_message.text)
    if sed_result and update.effective_message.reply_to_message:
        if update.effective_message.reply_to_message.text:
            to_fix = update.effective_message.reply_to_message.text
        elif update.effective_message.reply_to_message.caption:
            to_fix = update.effective_message.reply_to_message.caption
        else:
            return

        repl, repl_with, flags = sed_result

        if not repl:
            update.effective_message.reply_to_message.reply_text(
                "You're trying to replace... " "nothing with something?"
            )
            return

        try:

            # Protects bot from retarded geys -_-
            if infinite_checker(repl) == True:
                return update.effective_message.reply_text("Nice try -_-")

            if "i" in flags and "g" in flags:
                text = re.sub(repl, repl_with, to_fix, flags=re.I).strip()
            elif "i" in flags:
                text = re.sub(repl, repl_with, to_fix, count=1, flags=re.I).strip()
            elif "g" in flags:
                text = re.sub(repl, repl_with, to_fix).strip()
            else:
                text = re.sub(repl, repl_with, to_fix, count=1).strip()
        except sre_constants.error:
            LOGGER.warning(update.effective_message.text)
            LOGGER.exception("SRE constant error")
            update.effective_message.reply_text("Do you even sed? Apparently not.")
            return

        # empty string errors -_-
        if len(text) >= telegram.MAX_MESSAGE_LENGTH:
            update.effective_message.reply_text(
                "The result of the sed command was too long for \
                                                 telegram!"
            )
        elif text:
            update.effective_message.reply_to_message.reply_text(text)


SED_HANDLER = DisableAbleMessageHandler(
    Filters.regex(r"s([{}]).*?\1.*".format("".join(DELIMITERS))), sed, friendly="sed"
)

dispatcher.add_handler(SED_HANDLER)
