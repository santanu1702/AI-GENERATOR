"""
run.py – Single entry point (FIXED VERSION)

- Python 3.10+ compatible
- No event loop closed error
- Clean Pyrogram run system
"""

import asyncio
import logging
import sys

# ── FIX: create event loop BEFORE importing pyrogram ────────────────────────
if sys.platform == "win32":
    loop = asyncio.ProactorEventLoop()
else:
    loop = asyncio.new_event_loop()

asyncio.set_event_loop(loop)

# ── Safe imports after loop setup ───────────────────────────────────────────
from server import start_server
from main import main, post_init

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


async def run_bot():
    app = main()

    await app.start()
    await post_init(app)

    logger.info("Bot is running...")

    from pyrogram import idle
    await idle()

    await app.stop()


if __name__ == "__main__":
    logger.info("Starting Flask health-check server...")
    start_server()

    logger.info("Starting Pyrogram bot...")

    try:
        loop.run_until_complete(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")

    # ❌ IMPORTANT: loop.close() REMOVED 
