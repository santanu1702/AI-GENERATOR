"""
database.py  –  MongoDB (ratings/users) + users.json (limit tracking)
"""

import json
import logging
import os
import time
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure

import config

logger = logging.getLogger(__name__)

# ─── MongoDB client (lazy) ────────────────────────────────────────────────────
_client: Optional[AsyncIOMotorClient] = None
_db = None

def get_db():
    global _client, _db
    if _client is None:
        _client = AsyncIOMotorClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
        _db = _client[config.DB_NAME]
    return _db


# ─── users.json helpers (generation limits) ──────────────────────────────────
USERS_FILE = "users.json"


def _load_users() -> dict:
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_users(data: dict) -> None:
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_user_data(user_id: int) -> dict:
    data = _load_users()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "generations": 0,
            "banned": False,
            "joined_at": time.time(),
        }
        _save_users(data)
    return data[uid]


def increment_generation(user_id: int) -> int:
    data = _load_users()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"generations": 0, "banned": False, "joined_at": time.time()}
    data[uid]["generations"] = data[uid].get("generations", 0) + 1
    _save_users(data)
    return data[uid]["generations"]


def reset_generation(user_id: int) -> None:
    data = _load_users()
    uid = str(user_id)
    if uid in data:
        data[uid]["generations"] = 0
    _save_users(data)


def is_banned(user_id: int) -> bool:
    data = _load_users()
    return data.get(str(user_id), {}).get("banned", False)


def ban_user(user_id: int) -> None:
    data = _load_users()
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"generations": 0, "banned": True, "joined_at": time.time()}
    else:
        data[uid]["banned"] = True
    _save_users(data)


def unban_user(user_id: int) -> None:
    data = _load_users()
    uid = str(user_id)
    if uid in data:
        data[uid]["banned"] = False
    _save_users(data)


def get_total_users() -> int:
    return len(_load_users())


def get_all_user_ids() -> list:
    return [int(k) for k in _load_users().keys()]


# ─── MongoDB rating helpers ───────────────────────────────────────────────────

async def ensure_indexes():
    try:
        db = get_db()
        await db.users.create_index("user_id", unique=True)
        await db.ratings.create_index("item_id", unique=True)
    except Exception as e:
        logger.warning(f"Index creation warning: {e}")


async def upsert_mongo_user(user_id: int, username: str = "", full_name: str = "") -> None:
    try:
        db = get_db()
        await db.users.update_one(
            {"user_id": user_id},
            {"$setOnInsert": {
                "user_id": user_id,
                "username": username,
                "full_name": full_name,
                "joined_at": time.time(),
                "total_likes": 0,
                "total_dislikes": 0,
            }},
            upsert=True,
        )
    except Exception as e:
        logger.error(f"upsert_mongo_user error: {e}")


async def vote_on_item(item_id: str, user_id: int, vote: str) -> str:
    """
    vote: 'like' | 'dislike'
    Returns: 'ok' | 'already_voted' | 'error'
    """
    try:
        db = get_db()
        doc = await db.ratings.find_one({"item_id": item_id})
        if doc:
            if user_id in doc.get("voters", []):
                return "already_voted"
            update = {
                "$addToSet": {"voters": user_id},
                "$inc": {"likes" if vote == "like" else "dislikes": 1},
            }
            await db.ratings.update_one({"item_id": item_id}, update)
        else:
            await db.ratings.insert_one({
                "item_id": item_id,
                "likes": 1 if vote == "like" else 0,
                "dislikes": 1 if vote == "dislike" else 0,
                "voters": [user_id],
            })
        # also update per-user totals
        field = "total_likes" if vote == "like" else "total_dislikes"
        await db.users.update_one(
            {"user_id": user_id},
            {"$inc": {field: 1}},
            upsert=True,
        )
        return "ok"
    except Exception as e:
        logger.error(f"vote_on_item error: {e}")
        return "error"


async def get_global_ratings() -> dict:
    try:
        db = get_db()
        pipeline = [
            {"$group": {"_id": None, "likes": {"$sum": "$likes"}, "dislikes": {"$sum": "$dislikes"}}},
        ]
        result = await db.ratings.aggregate(pipeline).to_list(1)
        if result:
            return {"likes": result[0]["likes"], "dislikes": result[0]["dislikes"]}
    except Exception as e:
        logger.error(f"get_global_ratings error: {e}")
    return {"likes": 0, "dislikes": 0}
