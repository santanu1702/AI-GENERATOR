"""
keyboards.py – All InlineKeyboardMarkup builders in one place.
"""

import random
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import config
from captcha import COLORS, color_display


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎨 Generate Logo",  callback_data="mode_logo"),
            InlineKeyboardButton("🖼️ Generate Image", callback_data="mode_image"),
        ],
        [
            InlineKeyboardButton("🎬 Generate Video", callback_data="mode_video"),
        ],
        [
            InlineKeyboardButton("✏️ Edit Image",  callback_data="mode_edit_image"),
            InlineKeyboardButton("🎞️ Edit Video",  callback_data="mode_edit_video"),
        ],
        [
            InlineKeyboardButton("📊 Ratings",  callback_data="show_ratings"),
            InlineKeyboardButton("📤 Share Bot", switch_inline_query=f"Check out @{config.BOT_USERNAME}!"),
        ],
    ])


def after_generation_keyboard(item_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 Generate Again", callback_data=f"regen_{item_id}")],
        [
            InlineKeyboardButton("👍 Like",    callback_data=f"like_{item_id}"),
            InlineKeyboardButton("👎 Dislike", callback_data=f"dislike_{item_id}"),
        ],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
    ])


def force_join_keyboard(channels: list) -> InlineKeyboardMarkup:
    buttons = []
    for ch in channels:
        link = ch if ch.startswith("http") else f"https://t.me/{ch.lstrip('@')}"
        buttons.append([InlineKeyboardButton("📢 Join Channel", url=link)])
    buttons.append([InlineKeyboardButton("✅ I've Joined", callback_data="check_join")])
    return InlineKeyboardMarkup(buttons)


def private_only_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "🚀 Use Personally",
            url=f"https://t.me/{config.BOT_USERNAME}?start=true",
        )
    ]])


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
    ]])


# ─── CAPTCHA keyboard ─────────────────────────────────────────────────────────

def captcha_keyboard(options: list[str]) -> InlineKeyboardMarkup:
    """
    Builds a 2-column grid of colour buttons.
    Each button callback: captcha_<color_key>
    """
    buttons = []
    row = []
    for key in options:
        emoji, label = color_display(key)
        row.append(InlineKeyboardButton(f"{emoji} {label}", callback_data=f"captcha_{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)
