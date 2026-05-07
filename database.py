import motor.motor_asyncio
from config import DB_URI, DB_NAME

client = motor.motor_asyncio.AsyncIOMotorClient(DB_URI)
db = client[DB_NAME]
channels_col = db["channels"]

async def add_channel(channel_id):
    await channels_col.update_one({"id": "target_channels"}, {"$addToSet": {"list": channel_id}}, upsert=True)

async def remove_channel(channel_id):
    await channels_col.update_one({"id": "target_channels"}, {"$pull": {"list": channel_id}})

async def get_channels():
    doc = await channels_col.find_one({"id": "target_channels"})
    return doc.get("list", []) if doc else []
