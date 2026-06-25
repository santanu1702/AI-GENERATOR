"""
handlers/user_handlers.py – /start, /help, /ratings, mode selection,
generation flow, and CAPTCHA callback handling.
"""

import asyncio
import logging
import uuid
import time

from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, CallbackQuery

import config
import database as db
import captcha as cap
from ai_api import generate_logo, generate_image, generate_video, edit_image, edit_video
from keyboards import (
    main_menu_keyboard, after_generation_keyboard,
    back_to_menu_keyboard, captcha_keyboard,
)
from middlewares import (
    check_private, check_not_banned, check_force_join,
    check_force_join_callback, check_limit, is_admin,
)

logger = logging.getLogger(__name__)

# ─── in-memory session state ──────────────────────────────────────────────────
user_sessions: dict = {}

MODE_LABELS = {
    "logo":       "🎨 Logo",
    "image":      "🖼️ Image",
    "video":      "🎬 Video",
    "edit_image": "✏️ Image Edit",
    "edit_video": "🎞️ Video Edit",
}
WAITING_PROMPT_MODES = {"logo", "image", "video"}
WAITING_MEDIA_MODES  = {"edit_image", "edit_video"}


# ─── CAPTCHA helpers ─────────────────────────────────────────────────────────

async def _send_captcha(message: Message, uid: int) -> bool:
    """
    Sends a fresh CAPTCHA challenge.
    Returns False if user is in cooldown (message already sent).
    Returns True if captcha was sent and caller should halt.
    """
    in_cd, remaining = cap.in_cooldown(uid)
    if in_cd:
        mins, secs = divmod(remaining, 60)
        await message.reply_text(
            "❌ <b>Captcha verification failed.</b>\n\n"
            f"⏳ Try again in <b>{mins}m {secs}s</b>.",
            parse_mode=ParseMode.HTML,
        )
        return True

    correct, options = cap.build_captcha_challenge()
    cap.set_pending_captcha(uid, correct)

    emoji, label = cap.color_display(correct)
    state = cap.get_state(uid)
    attempts_left = state["attempts"]

    sent = await message.reply_text(
        "🔐 <b>Captcha Verification Required</b>\n\n"
        f"Please select the correct color: <b>{emoji} {label}</b>\n\n"
        f"🎯 Attempts remaining: <b>{attempts_left} / {cap.MAX_ATTEMPTS}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=captcha_keyboard(options),
    )
    cap.set_pending_captcha(uid, correct, sent.id)
    return True   # halt – waiting for callback


async def _needs_captcha_guard(client: Client, message: Message) -> bool:
    """
    Returns True (and sends captcha or cooldown msg) if user must verify.
    Returns False if user may proceed.
    """
    uid       = message.from_user.id
    privileged = await is_admin(uid)

    if not cap.needs_captcha(uid, privileged):
        return False

    await _send_captcha(message, uid)
    return True


# ─── /start ──────────────────────────────────────────────────────────────────

async def cmd_start(client: Client, message: Message):
    if not await check_private(client, message):
        return
    if not await check_not_banned(message):
        return

    uid  = message.from_user.id
    name = message.from_user.first_name or "there"

    # CAPTCHA first — before force-join
    if await _needs_captcha_guard(client, message):
        return

    # Force-join after captcha
    if not await check_force_join(client, message):
        return

    await db.upsert_mongo_user(uid, message.from_user.username or "", name)

    await message.reply_text(
        f"👋 Hello, <b>{name}</b>!\n\n"
        "Welcome to the <b>AI Media Generator Bot</b>.\n"
        "Choose what you want to create below 👇",
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )


# ─── /help ───────────────────────────────────────────────────────────────────

async def cmd_help(client: Client, message: Message):
    if not await check_private(client, message):
        return
    if not await check_not_banned(message):
        return
    if await _needs_captcha_guard(client, message):
        return

    await message.reply_text(
        "<b>📖 How to use this bot</b>\n\n"
        "1️⃣ Tap a generation mode from the menu.\n"
        "2️⃣ For <b>Generate</b> modes – send your text prompt.\n"
        "3️⃣ For <b>Edit</b> modes – send your image/video first, then describe the changes.\n\n"
        "<b>Modes available:</b>\n"
        "• 🎨 <b>Generate Logo</b> – AI-designed logos\n"
        "• 🖼️ <b>Generate Image</b> – any image from a prompt\n"
        "• 🎬 <b>Generate Video</b> – short AI video clip\n"
        "• ✏️ <b>Edit Image</b> – modify an existing image\n"
        "• 🎞️ <b>Edit Video</b> – modify an existing video\n\n"
        "<b>Commands:</b>\n"
        "/start – Main menu\n"
        "/help – This guide\n"
        "/ratings – Bot rating statistics\n\n"
        f"⚡ Free generations per user: <b>{config.get_generation_limit()}</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=back_to_menu_keyboard(),
    )


# ─── /ratings ────────────────────────────────────────────────────────────────

async def cmd_ratings(client: Client, message: Message):
    if not await check_not_banned(message):
        return
    if await _needs_captcha_guard(client, message):
        return

    stats       = await db.get_global_ratings()
    total_users = db.get_total_users()
    likes       = stats["likes"]
    dislikes    = stats["dislikes"]
    total_votes = likes + dislikes
    score       = round((likes / total_votes) * 10, 1) if total_votes else 0.0

    await message.reply_text(
        "📊 <b>Bot Overall Ratings</b>\n\n"
        f"👥 Total Users: <b>{total_users}</b>\n"
        f"👍 Total Likes: <b>{likes}</b>\n"
        f"👎 Total Dislikes: <b>{dislikes}</b>\n"
        f"⭐ Overall Rating: <b>{score} / 10</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=back_to_menu_keyboard(),
    )


# ─── Callback: CAPTCHA answer ────────────────────────────────────────────────

async def cb_captcha_answer(client: Client, query: CallbackQuery):
    uid    = query.from_user.id
    chosen = query.data.replace("captcha_", "")  # e.g. "red"

    result = cap.submit_answer(uid, chosen)

    if result == "correct":
        await query.answer("✅ Correct! Verified.", show_alert=False)
        name = query.from_user.first_name or "there"

        # Now check force-join before showing main menu
        channels = config.get_force_join_channels()
        not_joined = []
        if channels:
            from pyrogram.errors import UserNotParticipant
            from keyboards import force_join_keyboard
            for ch in channels:
                try:
                    member = await client.get_chat_member(ch, uid)
                    if member.status.value in ("kicked", "banned"):
                        not_joined.append(ch)
                except UserNotParticipant:
                    not_joined.append(ch)
                except Exception:
                    pass

        if not_joined:
            from keyboards import force_join_keyboard
            await query.message.edit_text(
                "✅ <b>Captcha passed!</b>\n\n"
                "📢 Now please join our channel(s) to continue.",
                parse_mode=ParseMode.HTML,
                reply_markup=force_join_keyboard(not_joined),
            )
        else:
            await db.upsert_mongo_user(uid, query.from_user.username or "", name)
            await query.message.edit_text(
                f"✅ <b>Verified!</b> Welcome, <b>{name}</b>!\n\n"
                "Choose what you want to create below 👇",
                parse_mode=ParseMode.HTML,
                reply_markup=main_menu_keyboard(),
            )

    elif result == "cooldown":
        in_cd, remaining = cap.in_cooldown(uid)
        mins, secs = divmod(remaining, 60)
        await query.answer(
            f"⏳ Still in cooldown. Try again in {mins}m {secs}s.",
            show_alert=True,
        )

    elif result == "failed":
        cooldown_secs = config.get_captcha_cooldown()
        mins, secs    = divmod(cooldown_secs, 60)
        await query.answer("❌ All attempts used up!", show_alert=True)
        await query.message.edit_text(
            "❌ <b>Captcha verification failed.</b>\n\n"
            f"⏳ You can try again in <b>{mins}m {secs}s</b>.\n\n"
            "A real-time countdown will appear when you send /start again.",
            parse_mode=ParseMode.HTML,
        )

    else:
        # wrong_N_left
        try:
            n = int(result.split("_")[1])
        except Exception:
            n = 0
        emoji_chosen, label_chosen = cap.color_display(chosen)
        await query.answer(
            f"❌ Wrong! {n} attempt(s) remaining.",
            show_alert=True,
        )
        # Rebuild challenge with same correct answer but new shuffled options
        state = cap.get_state(uid)
        correct = state["correct_color"]
        _, options = cap.build_captcha_challenge()
        # make sure correct is always in options
        if correct not in options:
            options[0] = correct
        import random; random.shuffle(options)

        cap.set_pending_captcha(uid, correct)
        emoji_c, label_c = cap.color_display(correct)
        await query.message.edit_text(
            "🔐 <b>Captcha Verification Required</b>\n\n"
            f"Please select the correct color: <b>{emoji_c} {label_c}</b>\n\n"
            f"🎯 Attempts remaining: <b>{n} / {cap.MAX_ATTEMPTS}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=captcha_keyboard(options),
        )


# ─── Callback: main menu ──────────────────────────────────────────────────────

async def cb_main_menu(client: Client, query: CallbackQuery):
    await query.answer()
    name = query.from_user.first_name or "there"
    await query.message.edit_text(
        f"👋 Hello, <b>{name}</b>!\n\n"
        "Welcome to the <b>AI Media Generator Bot</b>.\n"
        "Choose what you want to create below 👇",
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )


# ─── Callback: show ratings ───────────────────────────────────────────────────

async def cb_show_ratings(client: Client, query: CallbackQuery):
    await query.answer()
    stats       = await db.get_global_ratings()
    total_users = db.get_total_users()
    likes, dislikes = stats["likes"], stats["dislikes"]
    total_votes = likes + dislikes
    score = round((likes / total_votes) * 10, 1) if total_votes else 0.0
    await query.message.edit_text(
        "📊 <b>Bot Overall Ratings</b>\n\n"
        f"👥 Total Users: <b>{total_users}</b>\n"
        f"👍 Total Likes: <b>{likes}</b>\n"
        f"👎 Total Dislikes: <b>{dislikes}</b>\n"
        f"⭐ Overall Rating: <b>{score} / 10</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=back_to_menu_keyboard(),
    )


# ─── Callback: mode selection ─────────────────────────────────────────────────

async def cb_mode_select(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    if db.is_banned(uid):
        await query.answer("🚫 You are banned.", show_alert=True)
        return
    if not await check_force_join_callback(client, query):
        return

    # CAPTCHA guard inside callback
    privileged = await is_admin(uid)
    if cap.needs_captcha(uid, privileged):
        await query.answer("🔐 Please complete captcha first.", show_alert=True)
        in_cd, remaining = cap.in_cooldown(uid)
        if in_cd:
            mins, secs = divmod(remaining, 60)
            await query.message.edit_text(
                "❌ <b>Captcha failed — cooldown active.</b>\n\n"
                f"⏳ Try again in <b>{mins}m {secs}s</b>.",
                parse_mode=ParseMode.HTML,
            )
        else:
            correct, options = cap.build_captcha_challenge()
            cap.set_pending_captcha(uid, correct)
            emoji, label = cap.color_display(correct)
            state = cap.get_state(uid)
            await query.message.edit_text(
                "🔐 <b>Captcha Verification Required</b>\n\n"
                f"Please select the correct color: <b>{emoji} {label}</b>\n\n"
                f"🎯 Attempts remaining: <b>{state['attempts']} / {cap.MAX_ATTEMPTS}</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=captcha_keyboard(options),
            )
        return

    mode = query.data.replace("mode_", "")
    user_sessions[uid] = {"mode": mode, "prompt": None, "item_id": None, "media_bytes": None}
    await query.answer()

    if mode in WAITING_PROMPT_MODES:
        await query.message.edit_text(
            f"<b>{MODE_LABELS[mode]}</b> mode selected.\n\n"
            "✏️ Send me your <b>prompt</b> (description, style, colors, theme…)",
            parse_mode=ParseMode.HTML,
            reply_markup=back_to_menu_keyboard(),
        )
    else:
        await query.message.edit_text(
            f"<b>{MODE_LABELS[mode]}</b> mode selected.\n\n"
            "📎 Send me the <b>image/video</b> you want to edit.",
            parse_mode=ParseMode.HTML,
            reply_markup=back_to_menu_keyboard(),
        )


# ─── Callback: check force join ──────────────────────────────────────────────

async def cb_check_join(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    if await check_force_join_callback(client, query):
        await query.answer("✅ Verified! You can now use the bot.", show_alert=True)
        name = query.from_user.first_name or "there"
        await query.message.edit_text(
            f"👋 Hello, <b>{name}</b>! Choose a mode below 👇",
            reply_markup=main_menu_keyboard(),
            parse_mode=ParseMode.HTML,
        )
    else:
        await query.answer("❗ You still haven't joined all channels.", show_alert=True)


# ─── Callback: like / dislike ────────────────────────────────────────────────

async def cb_vote(client: Client, query: CallbackQuery):
    uid   = query.from_user.id
    parts = query.data.split("_", 1)
    vote_type = parts[0]
    item_id   = parts[1]

    result = await db.vote_on_item(item_id, uid, vote_type)
    if result == "already_voted":
        await query.answer("⚠️ You already voted on this!", show_alert=True)
    elif result == "ok":
        emoji = "👍" if vote_type == "like" else "👎"
        await query.answer(f"{emoji} Thanks for your feedback!")
    else:
        await query.answer("❗ Error recording vote.", show_alert=True)


# ─── Callback: regenerate ────────────────────────────────────────────────────

async def cb_regen(client: Client, query: CallbackQuery):
    uid = query.from_user.id
    if db.is_banned(uid):
        await query.answer("🚫 You are banned.", show_alert=True)
        return
    if not await check_force_join_callback(client, query):
        return

    privileged = await is_admin(uid)
    if cap.needs_captcha(uid, privileged):
        await query.answer("🔐 Please complete captcha first via /start.", show_alert=True)
        return

    session = user_sessions.get(uid)
    if not session or not session.get("prompt"):
        await query.answer("❗ Session expired. Please start again.", show_alert=True)
        return

    if not privileged:
        limit = config.get_generation_limit()
        used  = db.get_user_data(uid).get("generations", 0)
        if used >= limit:
            await query.answer(f"⚠️ Generation limit ({limit}) reached.", show_alert=True)
            return

    await query.answer("🔁 Regenerating…")
    await _run_generation(client, query.message, uid, session, is_regen=True)


# ─── Message: receive prompt (text) ──────────────────────────────────────────

async def on_text_prompt(client: Client, message: Message):
    if not await check_private(client, message):
        return
    if not await check_not_banned(message):
        return
    if await _needs_captcha_guard(client, message):
        return

    uid     = message.from_user.id
    session = user_sessions.get(uid)

    if not session:
        await message.reply_text(
            "Please choose a mode first 👇",
            reply_markup=main_menu_keyboard(),
        )
        return

    mode = session["mode"]

    if mode in WAITING_MEDIA_MODES:
        if not session.get("media_bytes"):
            await message.reply_text(
                "📎 Please send your image/video <b>first</b>, then the prompt.",
                parse_mode=ParseMode.HTML,
            )
            return
        session["prompt"] = message.text.strip()
    elif mode in WAITING_PROMPT_MODES:
        session["prompt"] = message.text.strip()
    else:
        return

    if not await check_limit(message):
        return

    await _run_generation(client, message, uid, session)


# ─── Message: receive media (photo / video) ──────────────────────────────────

async def on_media(client: Client, message: Message):
    if not await check_private(client, message):
        return
    if not await check_not_banned(message):
        return
    if await _needs_captcha_guard(client, message):
        return

    uid     = message.from_user.id
    session = user_sessions.get(uid)

    if not session or session["mode"] not in WAITING_MEDIA_MODES:
        return

    status_msg = await message.reply_text("⬇️ Downloading your file…", parse_mode=ParseMode.HTML)
    try:
        file_path = await message.download()
        with open(file_path, "rb") as f:
            session["media_bytes"] = f.read()
        import os; os.remove(file_path)
    except Exception as e:
        logger.error(f"Media download error: {e}")
        await status_msg.edit_text("❗ Failed to download your file. Please try again.")
        return

    await status_msg.edit_text(
        "✅ File received!\n\n"
        "✏️ Now send your <b>prompt</b> describing the changes you want.",
        parse_mode=ParseMode.HTML,
    )


# ─── Core generation runner ──────────────────────────────────────────────────

async def _run_generation(
    client: Client,
    message: Message,
    uid: int,
    session: dict,
    is_regen: bool = False,
):
    mode   = session["mode"]
    prompt = session["prompt"]
    label  = MODE_LABELS.get(mode, mode)

    wait_emojis = {
        "logo":       "🎨",
        "image":      "🖼️",
        "video":      "🎬",
        "edit_image": "✏️",
        "edit_video": "🎞️",
    }
    emoji = wait_emojis.get(mode, "⏳")

    status_msg = await message.reply_text(
        f"{emoji} <b>Generating {label}… Please wait…</b>",
        parse_mode=ParseMode.HTML,
    )

    media_bytes = None
    error_text  = None

    try:
        if mode == "logo":
            media_bytes = await generate_logo(prompt)
        elif mode == "image":
            media_bytes = await generate_image(prompt)
        elif mode == "video":
            media_bytes = await generate_video(prompt)
        elif mode == "edit_image":
            media_bytes = await edit_image(session.get("media_bytes", b""), prompt)
        elif mode == "edit_video":
            media_bytes = await edit_video(session.get("media_bytes", b""), prompt)
    except Exception as e:
        logger.error(f"Generation error [{mode}]: {e}")
        error_text = str(e)

    if not media_bytes:
        await status_msg.edit_text(
            f"❗ <b>Generation failed.</b>\n"
            f"{'Error: ' + error_text if error_text else 'The AI API returned no result.'}\n\n"
            "Please try again or choose a different mode.",
            parse_mode=ParseMode.HTML,
            reply_markup=back_to_menu_keyboard(),
        )
        return

    db.increment_generation(uid)

    item_id = str(uuid.uuid4())[:8]
    session["item_id"] = item_id

    caption = (
        f"{emoji} <b>{label} Generated!</b>\n\n"
        f"📝 <b>Prompt:</b> <i>{prompt}</i>"
    )

    try:
        await status_msg.delete()
    except Exception:
        pass

    is_video = mode in ("video", "edit_video")
    try:
        if is_video:
            sent = await message.reply_video(
                video=media_bytes,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=after_generation_keyboard(item_id),
            )
        else:
            sent = await message.reply_photo(
                photo=media_bytes,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=after_generation_keyboard(item_id),
            )
    except Exception as e:
        logger.error(f"Send media error: {e}")
        await message.reply_text(
            "❗ Failed to send the generated media. Please try again.",
            parse_mode=ParseMode.HTML,
            reply_markup=back_to_menu_keyboard(),
        )
        return

    asyncio.create_task(_auto_delete(sent, config.AUTO_DELETE_SECONDS))


async def _auto_delete(message: Message, delay: int):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass
