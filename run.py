"""
run.py – Single entry point.

Fixes for Python 3.12+ / 3.14 compatibility:
1. Create and set an explicit event loop BEFORE importing Pyrogram
   (asyncio.get_event_loop() no longer auto-creates a loop in 3.10+)
2. Start Flask health-check server in a background daemon thread
3. Run the Pyrogram bot inside the explicit event loop
"""

import asyncio
import logging
import sys

# ── CRITICAL: create event loop before ANY pyrogram import ──────────────────
# Python 3.10+ no longer auto-creates a loop; Pyrogram 2.x calls
# asyncio.get_event_loop() at import time via sync.py, which raises
# RuntimeError on 3.12+ / 3.14 if no loop exists yet.
if sys.platform == "win32":
    _loop = asyncio.ProactorEventLoop()
else:
    _loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)

# ── Now it is safe to import Pyrogram ────────────────────────────────────────
from server import start_server   # noqa: E402
from main import main, post_init  # noqa: E402

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

    logger.info("Bot is running. Press Ctrl+C to stop.")
    from pyrogram.idle import idle
    await idle()

    await app.stop()


if __name__ == "__main__":
    logger.info("Starting Flask health-check server…")
    start_server()

    logger.info("Starting Pyrogram bot…")
    try:
        _loop.run_until_complete(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        _loop.close()
