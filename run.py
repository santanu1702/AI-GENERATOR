"""
run.py – Single entry point.
1. Starts Flask health-check server in a background thread.
2. Runs the Pyrogram bot in the main thread (blocking).
"""

import logging
from server import start_server
from main import main

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    logger.info("Starting Flask health-check server…")
    start_server()

    logger.info("Starting Pyrogram bot…")
    app = main()
    app.run()
