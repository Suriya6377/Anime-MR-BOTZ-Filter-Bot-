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

# Initialize the db object
stream_db = StreamDB(STREAM_DATABASE, DATABASE_NAME)
