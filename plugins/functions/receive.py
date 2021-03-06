# SCP-079-TIP - Here's a tip
# Copyright (C) 2019 SCP-079 <https://scp-079.org>
#
# This file is part of SCP-079-TIP.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging
import pickle
from copy import deepcopy
from json import loads
from typing import Any

from pyrogram import Client, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .. import glovar
from .channel import get_debug_text, share_data
from .etc import code, crypt_str, general_link, get_int, get_text, lang, mention_id, thread
from .file import crypt_file, data_to_file, delete_file, get_new_path, get_downloaded_path, save
from .group import get_config_text, get_member, leave_group
from .ids import init_group_id, init_user_id
from .telegram import send_message, send_report_message
from .timers import update_admins
from .tip import tip_welcome

# Enable logging
logger = logging.getLogger(__name__)


def receive_add_bad(data: dict) -> bool:
    # Receive bad users or channels that other bots shared
    try:
        # Basic data
        the_id = data["id"]
        the_type = data["type"]

        # Receive bad user
        if the_type == "user":
            glovar.bad_ids["users"].add(the_id)

        save("bad_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive add bad error: {e}", exc_info=True)

    return False


def receive_help_welcome(client: Client, data: dict) -> bool:
    # Receive help welcome
    glovar.locks["message"].acquire()
    try:
        # Basic data
        user_id = data["user_id"]
        group_ids = data["group_ids"]
        message_id = data["message_id"]

        # Proceed
        for group_id in group_ids:
            if group_id not in glovar.admin_ids:
                continue

            if not init_group_id(group_id):
                continue

            if not glovar.configs[group_id].get("captcha"):
                continue

            if user_id in glovar.welcomed_ids[group_id]:
                continue

            member = get_member(client, group_id, user_id, False)
            tip_welcome(client, None, member, group_id, message_id)
    except Exception as e:
        logger.warning(f"Receive help welcome error: {e}", exc_info=True)
    finally:
        glovar.locks["message"].release()

    return False


def receive_clear_data(client: Client, data_type: str, data: dict) -> bool:
    # Receive clear data command
    glovar.locks["message"].acquire()
    try:
        # Basic data
        aid = data["admin_id"]
        the_type = data["type"]

        # Clear bad data
        if data_type == "bad":
            if the_type == "users":
                glovar.bad_ids["users"] = set()

            save("bad_ids")

        # Clear user data
        if data_type == "user":
            if the_type == "all":
                glovar.user_ids = {}

            save("user_ids")

        # Send debug message
        text = (f"{lang('project')}{lang('colon')}{general_link(glovar.project_name, glovar.project_link)}\n"
                f"{lang('admin_project')}{lang('colon')}{mention_id(aid)}\n"
                f"{lang('action')}{lang('colon')}{code(lang('clear'))}\n"
                f"{lang('more')}{lang('colon')}{code(f'{data_type} {the_type}')}\n")
        thread(send_message, (client, glovar.debug_channel_id, text))
    except Exception as e:
        logger.warning(f"Receive clear data: {e}", exc_info=True)
    finally:
        glovar.locks["message"].release()

    return False


def receive_config_commit(data: dict) -> bool:
    # Receive config commit
    try:
        # Basic data
        gid = data["group_id"]
        config = data["config"]

        # Channel
        if config["channel"]:
            config["channel"] = glovar.configs[gid]["channel"]
        else:
            config["channel"] = 0

        config["channel_text"] = glovar.configs[gid]["channel_text"]
        config["channel_button"] = glovar.configs[gid]["channel_button"]
        config["channel_link"] = glovar.configs[gid]["channel_link"]

        # Others
        for the_type in ["keyword", "ot", "rm", "welcome"]:
            config[f"{the_type}_button"] = glovar.configs[gid][f"{the_type}_button"]
            config[f"{the_type}_link"] = glovar.configs[gid][f"{the_type}_link"]

            if config[the_type]:
                config[the_type] = glovar.configs[gid][the_type]
            else:
                config[the_type] = ""

        # Default
        if config["default"]:
            config = deepcopy(glovar.default_config)

        glovar.configs[gid] = config
        save("configs")

        return True
    except Exception as e:
        logger.warning(f"Receive config commit error: {e}", exc_info=True)

    return False


def receive_config_reply(client: Client, data: dict) -> bool:
    # Receive config reply
    try:
        # Basic data
        gid = data["group_id"]
        uid = data["user_id"]
        link = data["config_link"]

        text = (f"{lang('admin')}{lang('colon')}{code(uid)}\n"
                f"{lang('action')}{lang('colon')}{code(lang('config_change'))}\n"
                f"{lang('description')}{lang('colon')}{code(lang('config_button'))}\n")
        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=lang("config_go"),
                        url=link
                    )
                ]
            ]
        )
        thread(send_report_message, (180, client, gid, text, None, markup))

        return True
    except Exception as e:
        logger.warning(f"Receive config reply error: {e}", exc_info=True)

    return False


def receive_config_show(client: Client, data: dict) -> bool:
    # Receive config show request
    try:
        # Basic Data
        aid = data["admin_id"]
        mid = data["message_id"]
        gid = data["group_id"]

        # Generate report message's text
        result = (f"{lang('admin')}{lang('colon')}{mention_id(aid)}\n"
                  f"{lang('action')}{lang('colon')}{code(lang('config_show'))}\n"
                  f"{lang('group_id')}{lang('colon')}{code(gid)}\n")

        if glovar.configs.get(gid, {}):
            result += get_config_text(glovar.configs[gid])
        else:
            result += (f"{lang('status')}{lang('colon')}{code(lang('status_failed'))}\n"
                       f"{lang('reason')}{lang('colon')}{code(lang('reason_none'))}\n")

        # Send the text data
        file = data_to_file(result)
        share_data(
            client=client,
            receivers=["MANAGE"],
            action="config",
            action_type="show",
            data={
                "admin_id": aid,
                "message_id": mid,
                "group_id": gid
            },
            file=file
        )

        return True
    except Exception as e:
        logger.warning(f"Receive config show error: {e}", exc_info=True)

    return False


def receive_declared_message(data: dict) -> bool:
    # Update declared message's id
    try:
        # Basic data
        gid = data["group_id"]
        mid = data["message_id"]

        if not glovar.admin_ids.get(gid):
            return True

        if init_group_id(gid):
            glovar.declared_message_ids[gid].add(mid)

        return True
    except Exception as e:
        logger.warning(f"Receive declared message error: {e}", exc_info=True)

    return False


def receive_file_data(client: Client, message: Message, decrypt: bool = True) -> Any:
    # Receive file's data from exchange channel
    data = None
    try:
        if not message.document:
            return None

        file_id = message.document.file_id
        file_ref = message.document.file_ref
        path = get_downloaded_path(client, file_id, file_ref)

        if not path:
            return None

        if decrypt:
            # Decrypt the file, save to the tmp directory
            path_decrypted = get_new_path()
            crypt_file("decrypt", path, path_decrypted)
            path_final = path_decrypted
        else:
            # Read the file directly
            path_decrypted = ""
            path_final = path

        with open(path_final, "rb") as f:
            data = pickle.load(f)

        for f in {path, path_decrypted}:
            thread(delete_file, (f,))
    except Exception as e:
        logger.warning(f"Receive file error: {e}", exc_info=True)

    return data


def receive_leave_approve(client: Client, data: dict) -> bool:
    # Receive leave approve
    try:
        # Basic data
        admin_id = data["admin_id"]
        the_id = data["group_id"]
        reason = data["reason"]

        if reason in {"permissions", "user"}:
            reason = lang(f"reason_{reason}")

        if not glovar.admin_ids.get(the_id):
            return True

        text = get_debug_text(client, the_id)
        text += (f"{lang('admin_project')}{lang('colon')}{mention_id(admin_id)}\n"
                 f"{lang('status')}{lang('colon')}{code(lang('leave_approve'))}\n")

        if reason:
            text += f"{lang('reason')}{lang('colon')}{code(reason)}\n"

        leave_group(client, the_id)
        thread(send_message, (client, glovar.debug_channel_id, text))

        return True
    except Exception as e:
        logger.warning(f"Receive leave approve error: {e}", exc_info=True)

    return False


def receive_refresh(client: Client, data: int) -> bool:
    # Receive refresh
    try:
        # Basic data
        aid = data

        # Update admins
        update_admins(client)

        # Send debug message
        text = (f"{lang('project')}{lang('colon')}{general_link(glovar.project_name, glovar.project_link)}\n"
                f"{lang('admin_project')}{lang('colon')}{mention_id(aid)}\n"
                f"{lang('action')}{lang('colon')}{code(lang('refresh'))}\n")
        thread(send_message, (client, glovar.debug_channel_id, text))

        return True
    except Exception as e:
        logger.warning(f"Receive refresh error: {e}", exc_info=True)

    return False


def receive_regex(client: Client, message: Message, data: str) -> bool:
    # Receive regex
    glovar.locks["regex"].acquire()
    try:
        file_name = data
        word_type = file_name.split("_")[0]
        if word_type not in glovar.regex:
            return True

        words_data = receive_file_data(client, message)
        if not words_data:
            return True

        pop_set = set(eval(f"glovar.{file_name}")) - set(words_data)
        new_set = set(words_data) - set(eval(f"glovar.{file_name}"))
        for word in pop_set:
            eval(f"glovar.{file_name}").pop(word, 0)

        for word in new_set:
            eval(f"glovar.{file_name}")[word] = 0

        save(file_name)

        # Regenerate special characters dictionary if possible
        if file_name in {"spc_words", "spe_words"}:
            special = file_name.split("_")[0]
            exec(f"glovar.{special}_dict = {{}}")
            for rule in words_data:
                # Check keys
                if "[" not in rule:
                    continue

                # Check value
                if "?#" not in rule:
                    continue

                keys = rule.split("]")[0][1:]
                value = rule.split("?#")[1][1]
                for k in keys:
                    eval(f"glovar.{special}_dict")[k] = value

        return True
    except Exception as e:
        logger.warning(f"Receive regex error: {e}", exc_info=True)
    finally:
        glovar.locks["regex"].release()

    return False


def receive_remove_bad(data: dict) -> bool:
    # Receive removed bad objects
    try:
        # Basic data
        the_id = data["id"]
        the_type = data["type"]

        # Remove bad user
        if the_type == "user":
            glovar.bad_ids["users"].discard(the_id)
            glovar.watch_ids["ban"].pop(the_id, {})
            glovar.watch_ids["delete"].pop(the_id, {})
            save("watch_ids")
            glovar.user_ids[the_id] = deepcopy(glovar.default_user_status)
            save("user_ids")

        save("bad_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive remove bad error: {e}", exc_info=True)

    return False


def receive_remove_score(data: int) -> bool:
    # Receive remove user's score
    glovar.locks["message"].acquire()
    try:
        # Basic data
        uid = data

        if not glovar.user_ids.get(uid):
            return True

        glovar.user_ids[uid] = deepcopy(glovar.default_user_status)
        save("user_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive remove score error: {e}", exc_info=True)
    finally:
        glovar.locks["message"].release()

    return False


def receive_remove_watch(data: dict) -> bool:
    # Receive removed watching users
    try:
        # Basic data
        uid = data["id"]
        the_type = data["type"]

        if the_type == "all":
            glovar.watch_ids["ban"].pop(uid, 0)
            glovar.watch_ids["delete"].pop(uid, 0)

        save("watch_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive remove watch error: {e}", exc_info=True)

    return False


def receive_rollback(client: Client, message: Message, data: dict) -> bool:
    # Receive rollback data
    try:
        # Basic data
        aid = data["admin_id"]
        the_type = data["type"]
        the_data = receive_file_data(client, message)

        if not the_data:
            return True

        exec(f"glovar.{the_type} = the_data")
        save(the_type)

        # Send debug message
        text = (f"{lang('project')}{lang('colon')}{general_link(glovar.project_name, glovar.project_link)}\n"
                f"{lang('admin_project')}{lang('colon')}{mention_id(aid)}\n"
                f"{lang('action')}{lang('colon')}{code(lang('rollback'))}\n"
                f"{lang('more')}{lang('colon')}{code(the_type)}\n")
        thread(send_message, (client, glovar.debug_channel_id, text))
    except Exception as e:
        logger.warning(f"Receive rollback error: {e}", exc_info=True)

    return False


def receive_text_data(message: Message) -> dict:
    # Receive text's data from exchange channel
    data = {}
    try:
        text = get_text(message)

        if not text:
            return {}

        data = loads(text)
    except Exception as e:
        logger.warning(f"Receive text data error: {e}")

    return data


def receive_user_score(project: str, data: dict) -> bool:
    # Receive and update user's score
    glovar.locks["message"].acquire()
    try:
        # Basic data
        project = project.lower()
        uid = data["id"]

        if not init_user_id(uid):
            return True

        score = data["score"]
        glovar.user_ids[uid]["score"][project] = score
        save("user_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive user score error: {e}", exc_info=True)
    finally:
        glovar.locks["message"].release()

    return False


def receive_watch_user(data: dict) -> bool:
    # Receive watch users that other bots shared
    try:
        # Basic data
        the_type = data["type"]
        uid = data["id"]
        until = data["until"]

        # Decrypt the data
        until = crypt_str("decrypt", until, glovar.key)
        until = get_int(until)

        # Add to list
        if the_type == "ban":
            glovar.watch_ids["ban"][uid] = until
        elif the_type == "delete":
            glovar.watch_ids["delete"][uid] = until
        else:
            return False

        save("watch_ids")

        return True
    except Exception as e:
        logger.warning(f"Receive watch user error: {e}", exc_info=True)

    return False
