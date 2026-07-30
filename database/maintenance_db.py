import logging
from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_URI, DATABASE_NAME
from datetime import datetime

class MaintenanceDB:
    def __init__(self, uri, db_name):
        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]
        self.col = self.db.maintenance

    async def get_maintenance_status(self, bot_id):
        try:
            config = await self.col.find_one({"bot_id": bot_id})
            if not config:
                return {"enabled": False, "reason": "", "end_time": None, "bot_id": bot_id}
            return config
        except Exception as e:
            logging.error(f"Error getting maintenance status: {e}")
            return {"enabled": False, "reason": "", "end_time": None, "bot_id": bot_id}

    async def update_maintenance(self, bot_id, enabled=None, reason=None, end_time=None):
        try:
            update_data = {}
            if enabled is not None:
                update_data["enabled"] = enabled
            if reason is not None:
                update_data["reason"] = reason
            if end_time is not None:
                update_data["end_time"] = end_time

            # Since end_time and reason could be explicitly cleared by setting them to "" or None
            # We must account for clearing. Let's provide a specific clear method instead for clarity.

            if update_data:
                await self.col.update_one(
                    {"bot_id": bot_id},
                    {"$set": update_data},
                    upsert=True
                )
        except Exception as e:
            logging.error(f"Error updating maintenance status: {e}")

    async def clear_maintenance_data(self, bot_id):
        try:
            await self.col.update_one(
                {"bot_id": bot_id},
                {"$set": {"reason": "", "end_time": None}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error clearing maintenance data: {e}")

main_db = MaintenanceDB(DATABASE_URI, DATABASE_NAME)
