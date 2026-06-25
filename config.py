import os
import json
from pathlib import Path

# ─── Load .env FIRST (before any os.environ.get calls) ──────────────────────
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent / ".env"
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path, override=False)
except ImportError:
    pass

# ─── Telegram ────────────────────────────────────────────────────────────────
API_ID       = int(os.environ.get("API_ID", "0"))
API_HASH     = os.environ.get("API_HASH",     "your_api_hash_here")
BOT_TOKEN    = os.environ.get("BOT_TOKEN",    "your_bot_token_here")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "YourBot")

# ─── Owner ───────────────────────────────────────────────────────────────────
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))

# ─── MongoDB ─────────────────────────────────────────────────────────────────
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.environ.get("DB_NAME",   "telegram_ai_bot")

# ─── AI APIs ─────────────────────────────────────────────────────────────────
OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY",    "your_openai_key_here")
STABILITY_API_KEY = os.environ.get("STABILITY_API_KEY", "your_stability_key_here")
RUNWAY_API_KEY    = os.environ.get("RUNWAY_API_KEY",    "your_runway_key_here")

# ─── Flask / Server ──────────────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", "8080"))

# ─── Feature defaults ────────────────────────────────────────────────────────
DEFAULT_GENERATION_LIMIT = 3
AUTO_DELETE_SECONDS      = 600   # 10 minutes

# ─── config.json helpers ─────────────────────────────────────────────────────
CONFIG_FILE = "config.json"

def _load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_config(data: dict) -> None:
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_config(key: str, default=None):
    return _load_config().get(key, default)

def set_config(key: str, value) -> None:
    data = _load_config()
    data[key] = value
    _save_config(data)

def del_config(key: str) -> None:
    data = _load_config()
    data.pop(key, None)
    _save_config(data)

# ─── Dynamic helpers ─────────────────────────────────────────────────────────
def get_admins() -> list:
    admins = get_config("admins", [])
    if OWNER_ID and OWNER_ID not in admins:
        admins.append(OWNER_ID)
    return admins

def get_force_join_channels() -> list:
    return get_config("force_join_channels", [])

def get_generation_limit() -> int:
    return get_config("generation_limit", DEFAULT_GENERATION_LIMIT)

# ── CAPTCHA config helpers ────────────────────────────────────────────────────
def is_captcha_enabled() -> bool:
    return get_config("captcha_enabled", False)

def get_captcha_cooldown() -> int:
    """Seconds a user is blocked after failing all attempts (default 30 min)."""
    return get_config("captcha_cooldown_seconds", 1800)

def get_captcha_reverify_interval() -> int:
    """
    Seconds between mandatory re-verifications.
    0 = verify once per session only.
    Set via /setcaptchatime <seconds>.
    """
    return get_config("captcha_reverify_interval", 0)
