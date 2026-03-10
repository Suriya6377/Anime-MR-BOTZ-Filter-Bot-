import asyncio
import logging
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from urllib.parse import quote_plus

from info import LOG_CHANNEL, URL, ADMINS
from Deendayal_botz.util.file_properties import get_name, get_hash
from database.stream_db import stream_db
from plugins.channel import extract_media_info

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

MEDIA_FILTER = filters.document | filters.video | filters.audio

async def delete_message_later(reply_msg: Message, command_msg: Message, delay: int):
    """Wait for 'delay' seconds, then delete the bot's reply and the user's command message."""
    await asyncio.sleep(delay)
    try:
        await reply_msg.delete()
        await command_msg.delete()
    except Exception as e:
        logger.error(f"Error deleting messages: {e}")

@Client.on_message(filters.command(['stream', 's']) & filters.private, group=1)
async def stream_command_handler(client: Client, message: Message):
    try:
        # Check if the message itself is a media file with the command as a caption,
        # OR if it's replying to a media file.
        if message.reply_to_message and getattr(message.reply_to_message, 'media', None) and message.reply_to_message.media.value in ["document", "video", "audio"]:
            media_msg = message.reply_to_message
        elif getattr(message, 'media', None) and message.media.value in ["document", "video", "audio"]:
            media_msg = message
        else:
            return await message.reply_text("Please reply to a valid media file, or send a media file with the command as caption, to generate a stream link.", quote=True)

        # Copy the message to the LOG_CHANNEL to get a streamable message ID
        log_msg = await media_msg.copy(chat_id=LOG_CHANNEL)

        file_name = get_name(log_msg)
        file_hash = get_hash(log_msg)

        media_type = log_msg.media.value
        media = getattr(log_msg, media_type)
        file_size = getattr(media, "file_size", 0)
        file_id = getattr(media, "file_id", "")

        # Save to STREAM_DATABASE
        await stream_db.save_stream_data(
            user_id=message.from_user.id,
            file_id=file_id,
            file_name=file_name,
            file_size=file_size,
            message_id=log_msg.id
        )

        # Extract media info (audio and quality)
        caption = log_msg.caption or ""
        media_info = extract_media_info(file_name, caption)
        audio = media_info.get("language", "N/A")
        quality = media_info.get("quality", "N/A")

        # Generate Stream and Download Links
        lazy_stream = f"{URL}watch/{str(log_msg.id)}/{quote_plus(file_name)}?hash={file_hash}"
        lazy_download = f"{URL}{str(log_msg.id)}/{quote_plus(file_name)}?hash={file_hash}"
        one_dm_link = f"{URL}1dm?url={quote_plus(lazy_download)}&filename={quote_plus(file_name)}"

        reply_text = (
            f"👤 **ᴜsᴇʀ ɴᴀᴍᴇ** : {message.from_user.mention}\n"
            f"🆔 **ᴜsᴇʀ ɪᴅ** : `{message.from_user.id}`\n\n"
            f"📕 **ꜰɪʟᴇɴᴀᴍᴇ** : **{file_name}**\n\n"
            f"🚀 **ᴅᴏᴡɴʟᴏᴀᴅ ᴜʀʟ**\n{lazy_download}\n\n"
            f"🖥️ **sᴛʀᴇᴀᴍ ᴜʀʟ**\n{lazy_stream}\n\n"
            f"**⚠️ Please forward this message to your Saved Messages. This message will be deleted in 10 minutes to protect your privacy.**\n\n"
            f"Powered by {client.me.mention}"
        )

        # Reply to the user
        reply_msg = await message.reply_text(
            text=reply_text,
            quote=True,
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Fast Download 🚀", url=lazy_download),
                 InlineKeyboardButton('🖥️ Watch online 🖥️', url=lazy_stream)],
                [InlineKeyboardButton("⚡ Ultra Fast Download", url=one_dm_link)]
            ])
        )

        # Schedule deletion after 10 minutes (600 seconds)
        asyncio.create_task(delete_message_later(reply_msg, message, 600))

    except Exception as e:
        logger.error(f"Error in stream_command_handler: {e}")
        await message.reply_text(f"⚠️ SOMETHING WENT WRONG \n\n{e}", quote=True)
