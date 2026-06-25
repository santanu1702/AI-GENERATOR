"""
handlers/admin_handlers.py – Owner/admin commands.
Old verify system removed. New CAPTCHA commands added:
  /captchaon  /captchaoff  /setcaptchatime <seconds>
"""

import asyncio
import logging
import time

from pyrogram import Client
from pyrogram.enums import ParseMode
from pyrogram.types import Message

import config
import database as db
import captcha as cap
from middlewares import is_admin

logger = logging.getLogger(__name__)
_bot_start_time = time.time()


def _owner_only(uid: int) -> bool:
    return uid == config.OWNER_ID


# ─── /addadmin ───────────────────────────────────────────────────────────────
async def cmd_addadmin(client: Client, message: Message):
    if not _owner_only(message.from_user.id):
        return await message.reply_text("🚫 Owner only.", parse_mode=ParseMode.HTML)
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply_text("Usage: /addadmin <user_id>", parse_mode=ParseMode.HTML)
    try:
        target = int(parts[1])
    except ValueError:
        return await message.reply_text("❗ Invalid user ID.", parse_mode=ParseMode.HTML)
    admins = config.get_config("admins", [])
    if target not in admins:
        admins.append(target)
        config.set_config("admins", admins)
    await message.reply_text(
        f"✅ User <code>{target}</code> added as admin.",
        parse_mode=ParseMode.HTML,
    )


# ─── /removeadmin ────────────────────────────────────────────────────────────
async def cmd_removeadmin(client: Client, message: Message):
    if not _owner_only(message.from_user.id):
        return await message.reply_text("🚫 Owner only.", parse_mode=ParseMode.HTML)
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply_text("Usage: /removeadmin <user_id>", parse_mode=ParseMode.HTML)
    try:
        target = int(parts[1])
    except ValueError:
        return await message.reply_text("❗ Invalid user ID.", parse_mode=ParseMode.HTML)
    admins = [a for a in config.get_config("admins", []) if a != target]
    config.set_config("admins", admins)
    await message.reply_text(
        f"✅ User <code>{target}</code> removed from admins.",
        parse_mode=ParseMode.HTML,
    )


# ─── /setlimit ───────────────────────────────────────────────────────────────
async def cmd_setlimit(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply_text("Usage: /setlimit <count>", parse_mode=ParseMode.HTML)
    try:
        limit = int(parts[1])
    except ValueError:
        return await message.reply_text("❗ Invalid number.", parse_mode=ParseMode.HTML)
    config.set_config("generation_limit", limit)
    await message.reply_text(
        f"✅ Generation limit set to <b>{limit}</b>.",
        parse_mode=ParseMode.HTML,
    )


# ─── /removelimit ────────────────────────────────────────────────────────────
async def cmd_removelimit(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return
    config.set_config("generation_limit", 999999)
    await message.reply_text("✅ Generation limit removed (unlimited).", parse_mode=ParseMode.HTML)


# ─── /addforcejoin ───────────────────────────────────────────────────────────
async def cmd_addforcejoin(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply_text(
            "Usage: /addforcejoin <@channel or invite link>",
            parse_mode=ParseMode.HTML,
        )
    ch = parts[1]
    channels = config.get_force_join_channels()
    if ch not in channels:
        channels.append(ch)
        config.set_config("force_join_channels", channels)
    await message.reply_text(
        f"✅ Force-join channel added: <code>{ch}</code>",
        parse_mode=ParseMode.HTML,
    )


# ─── /removeforcejoin ────────────────────────────────────────────────────────
async def cmd_removeforcejoin(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply_text(
            "Usage: /removeforcejoin <@channel>",
            parse_mode=ParseMode.HTML,
        )
    ch = parts[1]
    channels = [c for c in config.get_force_join_channels() if c != ch]
    config.set_config("force_join_channels", channels)
    await message.reply_text(
        f"✅ Removed force-join channel: <code>{ch}</code>",
        parse_mode=ParseMode.HTML,
    )


# ─── /captchaon ──────────────────────────────────────────────────────────────
async def cmd_captchaon(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return
    config.set_config("captcha_enabled", True)
    cooldown = config.get_captcha_cooldown()
    interval = config.get_captcha_reverify_interval()
    mins_cd, secs_cd = divmod(cooldown, 60)
    interval_text = (
        f"{interval // 60}m {interval % 60}s" if interval > 0 else "once per session"
    )
    await message.reply_text(
        "✅ <b>CAPTCHA system enabled.</b>\n\n"
        f"🔐 Type: Color selection\n"
        f"🎯 Max attempts: <b>{cap.MAX_ATTEMPTS}</b>\n"
        f"⏳ Failure cooldown: <b>{mins_cd}m {secs_cd}s</b>\n"
        f"🔄 Re-verify interval: <b>{interval_text}</b>\n\n"
        "Use /captchaoff to disable.\n"
        "Use /setcaptchatime &lt;seconds&gt; to change re-verify interval.",
        parse_mode=ParseMode.HTML,
    )


# ─── /captchaoff ─────────────────────────────────────────────────────────────
async def cmd_captchaoff(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return
    config.set_config("captcha_enabled", False)
    await message.reply_text(
        "✅ <b>CAPTCHA system disabled.</b>\n\n"
        "Users can now access the bot without verification.",
        parse_mode=ParseMode.HTML,
    )


# ─── /setcaptchatime ─────────────────────────────────────────────────────────
async def cmd_setcaptchatime(client: Client, message: Message):
    """
    /setcaptchatime <seconds>
    Sets how often users must re-verify via CAPTCHA.
    0 = verify once per session.
    Example: /setcaptchatime 3600  → re-verify every hour
    """
    if not await is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply_text(
            "Usage: /setcaptchatime &lt;seconds&gt;\n\n"
            "Examples:\n"
            "• <code>/setcaptchatime 0</code> – verify once per session\n"
            "• <code>/setcaptchatime 3600</code> – re-verify every hour\n"
            "• <code>/setcaptchatime 86400</code> – re-verify every 24 hours",
            parse_mode=ParseMode.HTML,
        )
    try:
        seconds = int(parts[1])
        if seconds < 0:
            raise ValueError
    except ValueError:
        return await message.reply_text(
            "❗ Please provide a valid non-negative integer (seconds).",
            parse_mode=ParseMode.HTML,
        )
    config.set_config("captcha_reverify_interval", seconds)
    if seconds == 0:
        desc = "once per session (no forced re-verification)"
    else:
        h, rem = divmod(seconds, 3600)
        m, s   = divmod(rem, 60)
        parts_str = []
        if h: parts_str.append(f"{h}h")
        if m: parts_str.append(f"{m}m")
        if s: parts_str.append(f"{s}s")
        desc = " ".join(parts_str)
    await message.reply_text(
        f"✅ CAPTCHA re-verify interval set to: <b>{desc}</b>",
        parse_mode=ParseMode.HTML,
    )


# ─── /stats ──────────────────────────────────────────────────────────────────
async def cmd_stats(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return
    total = db.get_total_users()
    captcha_on = cap.is_captcha_enabled()
    await message.reply_text(
        f"📊 <b>Bot Stats</b>\n\n"
        f"👥 Total Users: <b>{total}</b>\n"
        f"🔐 CAPTCHA: <b>{'Enabled' if captcha_on else 'Disabled'}</b>",
        parse_mode=ParseMode.HTML,
    )


# ─── /broadcast ──────────────────────────────────────────────────────────────
async def cmd_broadcast(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return
    text = message.text.split(None, 1)
    if len(text) < 2:
        return await message.reply_text("Usage: /broadcast {message}", parse_mode=ParseMode.HTML)
    msg = text[1]
    user_ids = db.get_all_user_ids()
    sent, failed = 0, 0
    status = await message.reply_text(
        f"📤 Broadcasting to <b>{len(user_ids)}</b> users…",
        parse_mode=ParseMode.HTML,
    )
    for uid in user_ids:
        try:
            await client.send_message(uid, msg, parse_mode=ParseMode.HTML)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await status.edit_text(
        f"✅ Broadcast complete.\n"
        f"👍 Sent: <b>{sent}</b>\n"
        f"❌ Failed: <b>{failed}</b>",
        parse_mode=ParseMode.HTML,
    )


# ─── /ban ────────────────────────────────────────────────────────────────────
async def cmd_ban(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply_text("Usage: /ban <user_id>", parse_mode=ParseMode.HTML)
    try:
        target = int(parts[1])
    except ValueError:
        return await message.reply_text("❗ Invalid user ID.", parse_mode=ParseMode.HTML)
    db.ban_user(target)
    await message.reply_text(
        f"🚫 User <code>{target}</code> has been banned.",
        parse_mode=ParseMode.HTML,
    )


# ─── /unban ──────────────────────────────────────────────────────────────────
async def cmd_unban(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        return await message.reply_text("Usage: /unban <user_id>", parse_mode=ParseMode.HTML)
    try:
        target = int(parts[1])
    except ValueError:
        return await message.reply_text("❗ Invalid user ID.", parse_mode=ParseMode.HTML)
    db.unban_user(target)
    await message.reply_text(
        f"✅ User <code>{target}</code> has been unbanned.",
        parse_mode=ParseMode.HTML,
    )


# ─── /ping ───────────────────────────────────────────────────────────────────
async def cmd_ping(client: Client, message: Message):
    start = time.time()
    sent  = await message.reply_text("🏓 Pinging…", parse_mode=ParseMode.HTML)
    latency = round((time.time() - start) * 1000, 2)
    uptime_secs = int(time.time() - _bot_start_time)
    h, rem = divmod(uptime_secs, 3600)
    m, s   = divmod(rem, 60)
    await sent.edit_text(
        "🏓 <b>Pong!</b>\n\n"
        f"✅ Bot is <b>alive</b>\n"
        f"⚡ API Latency: <b>{latency} ms</b>\n"
        f"⏱️ Response Time: <b>{latency} ms</b>\n"
        f"🕐 Uptime: <b>{h}h {m}m {s}s</b>",
        parse_mode=ParseMode.HTML,
    )
