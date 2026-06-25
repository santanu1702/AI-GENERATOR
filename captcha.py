"""
captcha.py – Color-selection CAPTCHA engine.

State is kept entirely in memory (dict keyed by user_id).
Structure per user:
{
    "verified":     bool,        # passed captcha this session
    "attempts":     int,         # remaining attempts (starts at 3)
    "cooldown_until": float,     # epoch – blocked until this time
    "correct_color":  str,       # key of correct color for pending captcha
    "captcha_msg_id": int|None,  # message id of the sent captcha (for editing)
    "verified_at":    float,     # epoch when last verified (for re-verify interval)
}
"""

import random
import time
import logging
from typing import Optional

import config

logger = logging.getLogger(__name__)

# ─── Colour palette ──────────────────────────────────────────────────────────
# key → (display emoji, human label)
COLORS: dict[str, tuple[str, str]] = {
    "red":      ("🔴", "Red"),
    "blue":     ("🔵", "Blue"),
    "green":    ("🟢", "Green"),
    "yellow":   ("🟡", "Yellow"),
    "orange":   ("🟠", "Orange"),
    "purple":   ("🟣", "Purple"),
    "white":    ("⚪", "White"),
    "black":    ("⚫", "Black"),
    "brown":    ("🟤", "Brown"),
}

MAX_ATTEMPTS   = 3
OPTION_COUNT   = 4      # how many colour buttons to show (1 correct + 3 wrong)

# ─── In-memory state store ────────────────────────────────────────────────────
_state: dict[int, dict] = {}


def _default_state() -> dict:
    return {
        "verified":       False,
        "attempts":       MAX_ATTEMPTS,
        "cooldown_until": 0.0,
        "correct_color":  "",
        "captcha_msg_id": None,
        "verified_at":    0.0,
    }


def get_state(uid: int) -> dict:
    if uid not in _state:
        _state[uid] = _default_state()
    return _state[uid]


def reset_state(uid: int) -> None:
    _state[uid] = _default_state()


# ─── Config helpers ───────────────────────────────────────────────────────────

def is_captcha_enabled() -> bool:
    return config.get_config("captcha_enabled", False)


def get_cooldown_seconds() -> int:
    """Failure cooldown in seconds (default 30 min)."""
    return config.get_config("captcha_cooldown_seconds", 1800)


def get_reverify_interval() -> int:
    """
    How often (seconds) a verified user must re-verify.
    0 = never re-verify after first pass.
    Configurable via /setcaptchatime.
    """
    return config.get_config("captcha_reverify_interval", 0)


# ─── Public API ──────────────────────────────────────────────────────────────

def needs_captcha(uid: int, is_privileged: bool) -> bool:
    """
    Returns True if this user must complete a CAPTCHA before proceeding.
    Admins/owner always return False.
    """
    if not is_captcha_enabled():
        return False
    if is_privileged:
        return False

    s = get_state(uid)

    # Still in cooldown (failed all attempts)
    if time.time() < s["cooldown_until"]:
        return True

    # Not yet verified
    if not s["verified"]:
        return True

    # Re-verify interval expired
    interval = get_reverify_interval()
    if interval > 0 and (time.time() - s["verified_at"]) >= interval:
        s["verified"] = False   # force re-verification
        s["attempts"] = MAX_ATTEMPTS
        return True

    return False


def in_cooldown(uid: int) -> tuple[bool, int]:
    """Returns (in_cooldown: bool, seconds_remaining: int)."""
    s = get_state(uid)
    remaining = s["cooldown_until"] - time.time()
    if remaining > 0:
        return True, int(remaining)
    return False, 0


def build_captcha_challenge() -> tuple[str, list[str]]:
    """
    Returns (correct_color_key, [option_key, ...]) — options are randomised.
    """
    color_keys   = list(COLORS.keys())
    correct      = random.choice(color_keys)
    wrong_pool   = [k for k in color_keys if k != correct]
    wrong        = random.sample(wrong_pool, min(OPTION_COUNT - 1, len(wrong_pool)))
    options      = [correct] + wrong
    random.shuffle(options)
    return correct, options


def set_pending_captcha(uid: int, correct: str, msg_id: Optional[int] = None) -> None:
    s = get_state(uid)
    s["correct_color"]  = correct
    s["captcha_msg_id"] = msg_id


def submit_answer(uid: int, chosen: str) -> str:
    """
    Process a user's colour choice.
    Returns: "correct" | "wrong_N_left" | "failed" | "cooldown"
    """
    s = get_state(uid)

    # Already in cooldown?
    if time.time() < s["cooldown_until"]:
        return "cooldown"

    if chosen == s["correct_color"]:
        s["verified"]    = True
        s["verified_at"] = time.time()
        s["attempts"]    = MAX_ATTEMPTS   # reset for next time
        s["correct_color"] = ""
        return "correct"

    # Wrong answer
    s["attempts"] -= 1
    if s["attempts"] <= 0:
        s["cooldown_until"] = time.time() + get_cooldown_seconds()
        s["attempts"] = MAX_ATTEMPTS      # reset for after cooldown
        s["verified"] = False
        return "failed"

    return f"wrong_{s['attempts']}_left"


def mark_verified(uid: int) -> None:
    """Force-mark a user as verified (used after successful captcha before force-join)."""
    s = get_state(uid)
    s["verified"]    = True
    s["verified_at"] = time.time()


def color_display(key: str) -> tuple[str, str]:
    """Returns (emoji, label) for a colour key."""
    return COLORS.get(key, ("❓", key.title()))
