"""
middlewares.py – Reusable guard functions used by handlers.
"""

import logging
from pyrogram import Client
from pyrogram.types import Message, CallbackQuery
from pyrogram.errors import UserNotParticipant, ChannelInvalid, ChatAdminRequired

import config
import database as db
from keyboards import force_join_keyboard, private_only_keyboard

logger = logging.getLogger(__name__)


async def is_admin(user_id: int) -> bool:
    return user_id in config.get_admins()


# ─── group guard ─────────────────────────────────────────────────────────────

async def check_private(client: Client, message: Message) -> bool:
    if message.chat.type.value != "private":
        await message.reply_text(
            "⚠️ This bot works only in private chat.",
            reply_markup=private_only_keyboard(),
            parse_mode=None,
        )
        return False
    return True


# ─── ban guard ───────────────────────────────────────────────────────────────

async def check_not_banned(message: Message) -> bool:
    uid = message.from_user.id
    if db.is_banned(uid):
        await message.reply_text(
            "🚫 You have been banned from using this bot.",
            parse_mode=None,
        )
        return False
    return True


# ─── force join guard ────────────────────────────────────────────────────────

async def check_force_join(client: Client, message: Message) -> bool:
    channels = config.get_force_join_channels()
    if not channels:
        return True

    uid = message.from_user.id
    not_joined = []

    for ch in channels:
        try:
            member = await client.get_chat_member(ch, uid)
            if member.status.value in ("kicked", "banned"):
                not_joined.append(ch)
        except UserNotParticipant:
            not_joined.append(ch)
        except (ChannelInvalid, ChatAdminRequired, Exception) as e:
            logger.warning(f"Force-join check failed for {ch}: {e}")

    if not_joined:
        await message.reply_text(
            "📢 <b>You must join our channel(s) to use this bot!</b>\n\n"
            "Please join and then tap <b>✅ I've Joined</b>.",
            reply_markup=force_join_keyboard(not_joined),
            parse_mode="html",
        )
        return False
    return True


async def check_force_join_callback(client: Client, query: CallbackQuery) -> bool:
    channels = config.get_force_join_channels()
    if not channels:
        return True

    uid = query.from_user.id
    not_joined = []

    for ch in channels:
        try:
            member = await client.get_chat_member(ch, uid)
            if member.status.value in ("kicked", "banned"):
                not_joined.append(ch)
        except UserNotParticipant:
            not_joined.append(ch)
        except Exception as e:
            logger.warning(f"Force-join callback check failed: {e}")

    if not_joined:
        await query.answer("❗ Please join the required channel(s) first!", show_alert=True)
        return False
    return True


# ─── generation limit guard ──────────────────────────────────────────────────

async def check_limit(message: Message) -> bool:
    uid = message.from_user.id
    if await is_admin(uid):
        return True

    limit = config.get_generation_limit()
    user_data = db.get_user_data(uid)
    used = user_data.get("generations", 0)

    if used >= limit:
        await message.reply_text(
            f"⚠️ You have reached your generation limit of <b>{limit}</b>.\n"
            "Contact an admin to get more generations.",
            parse_mode="html",
        )
        return False
    return True
