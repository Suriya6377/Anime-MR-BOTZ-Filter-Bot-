import logging
from motor.motor_asyncio import AsyncIOMotorClient
from info import STREAM_DATABASE, DATABASE_NAME

logger = logging.getLogger(__name__)

class StreamDB:
    def __init__(self, uri, database_name):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[database_name]
        self.collection = self.db.stream_data
        self.settings = self.db.stream_settings

    async def save_stream_data(self, user_id, file_id, file_name, file_size, message_id):
        try:
            document = {
                "user_id": user_id,
                "file_id": file_id,
                "file_name": file_name,
                "file_size": file_size,
                "message_id": message_id
            }
            await self.collection.insert_one(document)
            logger.info(f"Saved stream data for user {user_id}: {file_name}")
            return True
        except Exception as e:
            logger.error(f"Error saving stream data: {e}")
            return False

    async def increment_view_count(self, file_id):
        try:
            document = await self.db.stream_views.find_one_and_update(
                {"file_id": file_id},
                {"$inc": {"views": 1}},
                upsert=True,
                return_document=True
            )
            return document.get("views", 1)
        except Exception as e:
            logger.error(f"Error incrementing view count: {e}")
            return 1


    async def get_top_trending(self, limit=10):
        try:
            pipeline = [
                {
                    "$lookup": {
                        "from": "stream_data",
                        "localField": "file_id",
                        "foreignField": "file_id",
                        "as": "file_info"
                    }
                },
                {"$unwind": "$file_info"},
                {"$sort": {"views": -1}},
                {"$limit": limit},
                {
                    "$project": {
                        "_id": 0,
                        "file_id": 1,
                        "views": 1,
                        "file_name": "$file_info.file_name"
                    }
                }
            ]
            cursor = self.db.stream_views.aggregate(pipeline)
            trending = await cursor.to_list(length=limit)
            return trending
        except Exception as e:
            logger.error(f"Error getting top trending: {e}")
            return []

# Initialize the db object
stream_db = StreamDB(STREAM_DATABASE, DATABASE_NAME)
