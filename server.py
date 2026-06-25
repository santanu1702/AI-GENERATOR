"""
server.py – Lightweight Flask health-check server.
Runs in a background daemon thread so Render detects an open port.
"""

import logging
import threading
from flask import Flask, jsonify
import config

logger = logging.getLogger(__name__)

app = Flask(__name__)
_start_time = None


@app.route("/", methods=["GET"])
def index():
    return jsonify({"status": "ok", "bot": config.BOT_USERNAME})


@app.route("/health", methods=["GET"])
def health():
    import time
    uptime = round(time.time() - _start_time, 2) if _start_time else 0
    return jsonify({"status": "healthy", "uptime_seconds": uptime})


def run_flask():
    import time
    global _start_time
    _start_time = time.time()
    # use_reloader=False is mandatory inside a thread
    app.run(host="0.0.0.0", port=config.PORT, use_reloader=False, debug=False)


def start_server():
    """Start Flask in a background daemon thread."""
    thread = threading.Thread(target=run_flask, name="flask-server", daemon=True)
    thread.start()
    logger.info(f"Flask health-check server started on port {config.PORT}")
