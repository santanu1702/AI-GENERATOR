"""
main.py – Pyrogram bot entry point. Registers all handlers.
Old verify commands removed. New CAPTCHA commands added.
"""

import logging
from pyrogram import Client, filters

import config
import database as db
from handlers.user_handlers import (
    cmd_start, cmd_help, cmd_ratings,
    cb_captcha_answer,
    cb_main_menu, cb_show_ratings, cb_mode_select,
    cb_check_join, cb_vote, cb_regen,
    on_text_prompt, on_media,
)
from handlers.admin_handlers import (
    cmd_addadmin, cmd_removeadmin,
    cmd_setlimit, cmd_removelimit,
    cmd_addforcejoin, cmd_removeforcejoin,
    cmd_captchaon, cmd_captchaoff, cmd_setcaptchatime,
    cmd_stats, cmd_broadcast, cmd_ban, cmd_unban, cmd_ping,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

ALL_COMMANDS = [
    "start", "help", "ratings",
    "addadmin", "removeadmin",
    "setlimit", "removelimit",
    "addforcejoin", "removeforcejoin",
    "captchaon", "captchaoff", "setcaptchatime",
    "stats", "broadcast", "ban", "unban", "ping",
]


def create_bot() -> Client:
    return Client(
        name="ai_media_bot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
    )


def register_handlers(app: Client):

    # ── User commands ────────────────────────────────────────────────────────
    app.on_message(filters.command("start")   & filters.incoming)(cmd_start)
    app.on_message(filters.command("help")    & filters.incoming)(cmd_help)
    app.on_message(filters.command("ratings") & filters.incoming)(cmd_ratings)

    # ── Admin / owner commands ────────────────────────────────────────────────
    app.on_message(filters.command("addadmin")        & filters.incoming)(cmd_addadmin)
    app.on_message(filters.command("removeadmin")     & filters.incoming)(cmd_removeadmin)
    app.on_message(filters.command("setlimit")        & filters.incoming)(cmd_setlimit)
    app.on_message(filters.command("removelimit")     & filters.incoming)(cmd_removelimit)
    app.on_message(filters.command("addforcejoin")    & filters.incoming)(cmd_addforcejoin)
    app.on_message(filters.command("removeforcejoin") & filters.incoming)(cmd_removeforcejoin)

    # ── CAPTCHA commands (replaces old verify system) ─────────────────────────
    app.on_message(filters.command("captchaon")      & filters.incoming)(cmd_captchaon)
    app.on_message(filters.command("captchaoff")     & filters.incoming)(cmd_captchaoff)
    app.on_message(filters.command("setcaptchatime") & filters.incoming)(cmd_setcaptchatime)

    # ── Other admin commands ──────────────────────────────────────────────────
    app.on_message(filters.command("stats")     & filters.incoming)(cmd_stats)
    app.on_message(filters.command("broadcast") & filters.incoming)(cmd_broadcast)
    app.on_message(filters.command("ban")       & filters.incoming)(cmd_ban)
    app.on_message(filters.command("unban")     & filters.incoming)(cmd_unban)
    app.on_message(filters.command("ping")      & filters.incoming)(cmd_ping)

    # ── Callback queries — CAPTCHA must be registered BEFORE generic ones ─────
    app.on_callback_query(filters.regex(r"^captcha_"))(cb_captcha_answer)
    app.on_callback_query(filters.regex(r"^main_menu$"))(cb_main_menu)
    app.on_callback_query(filters.regex(r"^show_ratings$"))(cb_show_ratings)
    app.on_callback_query(filters.regex(r"^mode_"))(cb_mode_select)
    app.on_callback_query(filters.regex(r"^check_join$"))(cb_check_join)
    app.on_callback_query(filters.regex(r"^(like|dislike)_"))(cb_vote)
    app.on_callback_query(filters.regex(r"^regen_"))(cb_regen)

    # ── Media messages ────────────────────────────────────────────────────────
    app.on_message(
        (filters.photo | filters.video | filters.document)
        & filters.incoming
        & filters.private
    )(on_media)

    # ── Text / prompt messages (catch-all — must be last) ─────────────────────
    app.on_message(
        filters.text
        & filters.incoming
        & filters.private
        & ~filters.command(ALL_COMMANDS)
    )(on_text_prompt)


async def post_init(app: Client):
    try:
        await db.ensure_indexes()
        logger.info("MongoDB indexes ensured.")
    except Exception as e:
        logger.warning(f"MongoDB init warning: {e}")
    me = await app.get_me()
    logger.info(f"Bot started as @{me.username} (id={me.id})")


def main():
    app = create_bot()
    register_handlers(app)

    original_start = app.start

    async def patched_start(*args, **kwargs):
        result = await original_start(*args, **kwargs)
        await post_init(app)
        return result

    app.start = patched_start
    return app
