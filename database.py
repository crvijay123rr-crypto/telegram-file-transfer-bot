from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DB_NAME

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

users_collection = db["users"]
sessions_collection = db["sessions"]
tasks_collection = db["tasks"]

async def get_user(user_id: int):
    return await users_collection.find_one({"user_id": user_id})

async def save_user(user_id: int, data: dict):
    await users_collection.update_one(
        {"user_id": user_id}, {"$set": data}, upsert=True
    )

async def get_user_session(user_id: int):
    res = await sessions_collection.find_one({"user_id": user_id})
    return res["session_string"] if res else None

async def save_user_session(user_id: int, session_string: str):
    await sessions_collection.update_one(
        {"user_id": user_id}, {"$set": {"session_string": session_string}}, upsert=True
    )

async def remove_user_session(user_id: int):
    await sessions_collection.delete_one({"user_id": user_id})
  
