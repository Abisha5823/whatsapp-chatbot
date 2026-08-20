from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
import logging
from core.config import settings

logger = logging.getLogger(__name__)

class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None

db_instance = MongoDB()

async def connect_to_mongo():
    """Connect to MongoDB Atlas"""
    try:
        db_instance.client = AsyncIOMotorClient(settings.MONGODB_URI)
        db_instance.db = db_instance.client[settings.MONGODB_DB_NAME]
        
        # Test connection
        await db_instance.client.admin.command('ping')
        logger.info("Connected to MongoDB Atlas successfully!")
        return db_instance.db
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        raise

async def close_mongo_connection():
    """Close MongoDB connection"""
    if db_instance.client is not None:  # ✅ Use is not None
        db_instance.client.close()
        logger.info("MongoDB connection closed")

async def get_database() -> AsyncIOMotorDatabase:
    """Get database instance"""
    if db_instance.db is None:  # ✅ Use is None
        await connect_to_mongo()
    return db_instance.db

async def get_collection(collection_name: str):
    """Get a collection"""
    db = await get_database()
    return db[collection_name]