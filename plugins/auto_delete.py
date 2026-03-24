from pyrogram import Client, filters
import logging

logger = logging.getLogger(__name__)

# This handler catches all messages starting with '/'
# We put it in a high group number (e.g., 99) so it runs *after*
# the main command handlers (which are usually in group 0).
# This ensures that the command message is deleted *after* any replies
# are sent, preventing "MessageIdInvalid" errors when trying to quote it.
@Client.on_message(filters.regex(r"^(?:/|#)[a-zA-Z0-9_]+"), group=99)
async def auto_delete_commands(client, message):
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Failed to auto-delete command message: {e}")
