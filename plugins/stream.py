import asyncio
import logging
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from urllib.parse import quote_plus

from info import LOG_CHANNEL, URL, ADMINS
from Deendayal_botz.util.file_properties import get_name, get_hash
from database.stream_db import stream_db
from database.users_chats_db import db
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
        if file_name:
            file_name = file_name.replace('_', ' ')
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
        file_name_str = file_name if file_name else ""
        lazy_stream = f"{URL}watch/{str(log_msg.id)}/{quote_plus(file_name_str)}?hash={file_hash}"
        lazy_download = f"{URL}{str(log_msg.id)}/{quote_plus(file_name_str)}?hash={file_hash}"
        one_dm_link = f"{URL}1dm?url={quote_plus(lazy_download)}&filename={quote_plus(file_name_str)}"

        log_text = (
            f"**Stream Link Generated**\n\n"
            f"👤 **ᴜsᴇʀ ɴᴀᴍᴇ** : {message.from_user.mention}\n"
            f"🆔 **ᴜsᴇʀ ɪᴅ** : `{message.from_user.id}`\n\n"
            f"📕 **ꜰɪʟᴇɴᴀᴍᴇ** : `{file_name_str}`\n"
            f"🖥️ **sᴛʀᴇᴀᴍ ᴜʀʟ** : {lazy_stream}"
        )
        await client.send_message(chat_id=LOG_CHANNEL, text=log_text, reply_to_message_id=log_msg.id, disable_web_page_preview=True)

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
                 InlineKeyboardButton('🖥️ Watch online 🖥️', url=lazy_stream)]
            ])
        )

        # Schedule deletion after 10 minutes (600 seconds)
        asyncio.create_task(delete_message_later(reply_msg, message, 600))

    except Exception as e:
        logger.error(f"Error in stream_command_handler: {e}")
        await message.reply_text(f"⚠️ SOMETHING WENT WRONG \n\n{e}", quote=True)


@Client.on_message(filters.command(['set_stream_chnl']) & filters.private)
async def set_stream_channel_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /set_stream_chnl <channel_id>\n\nExample: /set_stream_chnl -1001234567890")
    
    try:
        channel_id = int(message.command[1])
        added = await db.add_stream_channel_status(client.me.id, channel_id)
        if added:
            await message.reply_text(f"Stream target channel successfully added: `{channel_id}`")
        else:
            await message.reply_text(f"Channel `{channel_id}` is already in the stream channels list.")
    except ValueError:
        await message.reply_text("Invalid channel ID format. Please provide a valid integer.")
    except Exception as e:
        await message.reply_text(f"Error setting stream channel: {e}")

@Client.on_message(filters.command(['del_stream_chnl']) & filters.user(ADMINS))
async def del_stream_channel_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /del_stream_chnl <channel_id>\n\nExample: /del_stream_chnl -1001234567890")
    
    try:
        channel_id = int(message.command[1])
        removed = await db.remove_stream_channel_status(client.me.id, channel_id)
        if removed:
            await message.reply_text(f"Stream target channel successfully removed: `{channel_id}`")
        else:
            await message.reply_text(f"Channel `{channel_id}` is not in the stream channels list.")
    except ValueError:
        await message.reply_text("Invalid channel ID format. Please provide a valid integer.")
    except Exception as e:
        await message.reply_text(f"Error removing stream channel: {e}")

@Client.on_message(filters.command(['stream_channels']) & filters.user(ADMINS))
async def list_stream_channels_cmd(client: Client, message: Message):
    try:
        channels = await db.stream_channel_status(client.me.id)
        if not channels:
            return await message.reply_text("No stream channels are currently configured.")
        
        text = "**Configured Stream Channels:**\n\n"
        for ch in channels:
            try:
                chat = await client.get_chat(ch)
                title = chat.title or "Unknown Channel"
                link = chat.invite_link
                if not link and chat.username:
                    link = f"https://t.me/{chat.username}"
                
                if link:
                    text += f"• [{title}]({link}) (`{ch}`)\n"
                else:
                    text += f"• **{title}** (`{ch}`)\n"
            except Exception as e:
                text += f"• Unknown Channel (`{ch}`) - _Error: {e}_\n"
                
        await message.reply_text(text, disable_web_page_preview=True)
    except Exception as e:
        await message.reply_text(f"Error listing stream channels: {e}")

@Client.on_message(filters.channel & MEDIA_FILTER, group=1)
async def channel_stream_handler(client: Client, message: Message):
    try:
        stream_channels = await db.stream_channel_status(client.me.id)
        if not stream_channels or message.chat.id not in stream_channels:
            return

        # Copy the message to the LOG_CHANNEL to get a streamable message ID
        log_msg = await message.copy(chat_id=LOG_CHANNEL)

        file_name = get_name(log_msg)
        if file_name:
            file_name = file_name.replace('_', ' ')
        file_hash = get_hash(log_msg)

        media_type = log_msg.media.value
        media = getattr(log_msg, media_type)
        file_size = getattr(media, "file_size", 0)
        file_id = getattr(media, "file_id", "")

        # Save to STREAM_DATABASE
        # We can use the chat id as user_id or a generic channel user id
        await stream_db.save_stream_data(
            user_id=message.chat.id,
            file_id=file_id,
            file_name=file_name,
            file_size=file_size,
            message_id=log_msg.id
        )

        # Generate Stream and Download Links
        file_name_str = file_name if file_name else ""
        lazy_stream = f"{URL}watch/{str(log_msg.id)}/{quote_plus(file_name_str)}?hash={file_hash}"
        lazy_download = f"{URL}{str(log_msg.id)}/{quote_plus(file_name_str)}?hash={file_hash}"

        log_text = (
            f"**Stream Link Generated (Channel)**\n\n"
            f"📢 **ᴄʜᴀɴɴᴇʟ ɴᴀᴍᴇ** : {message.chat.title}\n"
            f"🆔 **ᴄʜᴀɴɴᴇʟ ɪᴅ** : `{message.chat.id}`\n\n"
            f"📕 **ꜰɪʟᴇɴᴀᴍᴇ** : `{file_name_str}`\n"
            f"🖥️ **sᴛʀᴇᴀᴍ ᴜʀʟ** : {lazy_stream}"
        )
        await client.send_message(chat_id=LOG_CHANNEL, text=log_text, reply_to_message_id=log_msg.id, disable_web_page_preview=True)

        # Try to edit the existing message to add buttons, keeping existing ones if any
        current_markup = message.reply_markup
        new_buttons = [
            [InlineKeyboardButton("🚀 Fast Download 🚀", url=lazy_download),
             InlineKeyboardButton('🖥️ Watch online 🖥️', url=lazy_stream)]
        ]

        if current_markup and current_markup.inline_keyboard:
            current_markup.inline_keyboard.extend(new_buttons)
            await message.edit_reply_markup(reply_markup=current_markup)
        else:
            await message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(new_buttons))

    except Exception as e:
        logger.error(f"Error in channel_stream_handler: {e}")
