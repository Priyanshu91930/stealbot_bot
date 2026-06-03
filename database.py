import motor.motor_asyncio
from config import DB_URI, DB_NAME

client = motor.motor_asyncio.AsyncIOMotorClient(DB_URI)
db = client[DB_NAME]
channels_col = db["channels"]
settings_col = db["scheduler_settings"]
queue_col = db["scheduler_queue"]

async def add_channel(channel_id):
    await channels_col.update_one({"id": "target_channels"}, {"$addToSet": {"list": channel_id}}, upsert=True)

async def remove_channel(channel_id):
    await channels_col.update_one({"id": "target_channels"}, {"$pull": {"list": channel_id}})

async def get_channels():
    doc = await channels_col.find_one({"id": "target_channels"})
    return doc.get("list", []) if doc else []

async def get_scheduler_settings():
    doc = await settings_col.find_one({"id": "settings"})
    if not doc:
        default = {
            "id": "settings",
            "active": False,
            "batch_size": 10,
            "times": ["09:00", "18:00"],
            "days": [0, 1, 2, 3, 4, 5, 6], # 0-6 represent Monday-Sunday
            "target_channel": None,
            "last_run_date": None,
            "last_run_time": None
        }
        await settings_col.insert_one(default)
        return default
    return doc

async def update_scheduler_settings(settings):
    await settings_col.update_one({"id": "settings"}, {"$set": settings}, upsert=True)

async def add_to_queue(msg_id):
    await queue_col.insert_one({"msg_id": msg_id})

async def get_queue_count():
    return await queue_col.count_documents({})

async def pop_queue_batch(batch_size):
    cursor = queue_col.find().limit(batch_size)
    posts = await cursor.to_list(length=batch_size)
    if posts:
        ids = [p["_id"] for p in posts]
        await queue_col.delete_many({"_id": {"$in": ids}})
    return [p["msg_id"] for p in posts]
