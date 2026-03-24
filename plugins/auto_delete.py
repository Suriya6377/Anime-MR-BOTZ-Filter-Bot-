from pyrogram import Client, filters
import logging

logger = logging.getLogger(__name__)

# List of specific commands to auto-delete
AUTO_DELETE_COMMANDS = [
    "start", "post", "movie_update"
]

# This handler catches all messages starting with specific commands
# We put it in a high group number (e.g., 99) so it runs *after*
# the main command handlers (which are usually in group 0).
# This ensures that the command message is deleted *after* any replies
# are sent, preventing "MessageIdInvalid" errors when trying to quote it.
@Client.on_message(filters.command(AUTO_DELETE_COMMANDS, prefixes=["/", "#"]), group=99)
async def auto_delete_commands(client, message):
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Failed to auto-delete command message: {e}")
