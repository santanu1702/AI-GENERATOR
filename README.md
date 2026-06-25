# 🤖 AI Media Generator Telegram Bot

A full-featured Telegram bot with AI image/logo/video generation, color-selection CAPTCHA verification, force-join, rating system, and full owner/admin panel.

---

## 📁 Project Structure

```
telegram_bot/
├── .env                      ← Your secrets (NEVER commit!)
├── .env.example              ← Safe template to copy from
├── .gitignore                ← Excludes .env and junk
├── config.py                 ← Loads .env + runtime config helpers
├── config.json               ← Dynamic runtime settings
├── database.py               ← MongoDB (ratings) + users.json (limits/bans)
├── users.json                ← Per-user generation counts & ban status
├── captcha.py                ← Full CAPTCHA engine (colors, state, cooldown)
├── ai_api.py                 ← AI wrappers: OpenAI, Stability AI, Runway ML
├── keyboards.py              ← All InlineKeyboardMarkup builders
├── middlewares.py            ← Ban / force-join / limit guards
├── server.py                 ← Flask health-check (background thread)
├── main.py                   ← Pyrogram client + handler registration
├── run.py                    ← Single entry point (Flask + Bot)
├── requirements.txt
├── handlers/
│   ├── __init__.py
│   ├── user_handlers.py      ← /start /help /ratings + CAPTCHA flow + generation
│   └── admin_handlers.py     ← Owner/admin management commands
└── README.md
```

---

## ⚙️ Setup

### 1. Create your `.env`
```bash
cp .env.example .env
# Fill in all values in .env
```

| Variable | Where to get it |
|---|---|
| `API_ID` | https://my.telegram.org/apps |
| `API_HASH` | https://my.telegram.org/apps |
| `BOT_TOKEN` | @BotFather on Telegram |
| `BOT_USERNAME` | @BotFather on Telegram |
| `OWNER_ID` | @userinfobot on Telegram |
| `MONGO_URI` | https://cloud.mongodb.com → Connect |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| `STABILITY_API_KEY` | https://platform.stability.ai/account/keys |
| `RUNWAY_API_KEY` | https://app.runwayml.com/settings |

### 2. Install & run
```bash
pip install -r requirements.txt
python run.py
```

---

## 🔐 CAPTCHA System

### How it works

1. User sends `/start` (or any command)
2. If CAPTCHA is enabled → bot shows a color emoji and 4 color buttons
3. User must tap the **correct** color button
4. If correct → proceed to force-join check → main menu
5. If wrong → attempts decrease (3 total)
6. After 3 wrong attempts → user is blocked for the cooldown period

### CAPTCHA Commands (Admin/Owner)

| Command | Description |
|---|---|
| `/captchaon` | Enable CAPTCHA system |
| `/captchaoff` | Disable CAPTCHA system |
| `/setcaptchatime <seconds>` | Set re-verify interval (0 = once per session) |

### Example re-verify intervals
```
/setcaptchatime 0       → verify once per session
/setcaptchatime 3600    → re-verify every 1 hour
/setcaptchatime 86400   → re-verify every 24 hours
/setcaptchatime 604800  → re-verify every 7 days
```

### CAPTCHA Colors (9 total)
🔴 Red · 🔵 Blue · 🟢 Green · 🟡 Yellow · 🟠 Orange · 🟣 Purple  
⚪ White · ⚫ Black · 🟤 Brown

### Bypass rules
- **Owner** → always bypasses CAPTCHA
- **Admins** → always bypass CAPTCHA
- **Banned users** → blocked before CAPTCHA check

### Flow order
```
User sends /start
    ↓
Ban check
    ↓
CAPTCHA check (if enabled)
    ↓ (pass)
Force-join check
    ↓ (joined)
Main menu ✅
```

---

## 🧩 User Commands

| Command | Description |
|---|---|
| `/start` | Welcome + CAPTCHA + force-join + main menu |
| `/help` | Full usage guide |
| `/ratings` | Bot rating statistics |

## 🔧 Admin / Owner Commands

| Command | Description |
|---|---|
| `/addadmin <id>` | Add admin (owner only) |
| `/removeadmin <id>` | Remove admin (owner only) |
| `/setlimit <n>` | Set generation limit per user |
| `/removelimit` | Unlimited generations |
| `/addforcejoin <@ch>` | Add required join channel |
| `/removeforcejoin <@ch>` | Remove required channel |
| `/captchaon` | Enable CAPTCHA |
| `/captchaoff` | Disable CAPTCHA |
| `/setcaptchatime <s>` | Set re-verify interval in seconds |
| `/stats` | Total users + captcha status |
| `/broadcast {msg}` | Send message to all users |
| `/ban <id>` | Ban a user |
| `/unban <id>` | Unban a user |
| `/ping` | Bot health + latency + uptime |

---

## 🚀 Deploy on Render

1. Push to a **private** GitHub repo (`.env` is gitignored)
2. New **Web Service** on [render.com](https://render.com)
3. Start command: `python run.py`
4. Add all `.env` variables in Render's **Environment** tab
5. Deploy — Flask keeps the port open, bot runs in main thread

---

## 🔐 Security Notes

- `.env` is in `.gitignore` — never committed
- On Render, set vars in dashboard (no `.env` file needed)
- `override=False` in `load_dotenv()` — real env vars always win
- MongoDB URI only lives in `MONGO_URI` inside `.env`
