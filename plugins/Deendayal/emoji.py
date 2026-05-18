from pyrogram import Client, filters
from pyrogram.enums import MessageEntityType
from utils import temp

def get_emoji_id(message):
    if message.entities:
        for entity in message.entities:
            if entity.type == MessageEntityType.CUSTOM_EMOJI:
                return entity.custom_emoji_id
    return None

@Client.on_message(filters.command(["emojiid"]))
async def emojiid_command(bot, message):
    if message.reply_to_message:
        emoji_id = get_emoji_id(message.reply_to_message)
        if emoji_id:
            await message.reply(f"**Custom Emoji ID is** \n\n`{emoji_id}`", quote=True)
            return

    emoji_id = get_emoji_id(message)
    if emoji_id:
        await message.reply(f"**Custom Emoji ID is** \n\n`{emoji_id}`", quote=True)
    else:
        await message.reply("Oops !! No custom emoji found in the message.", quote=True)

@Client.on_message(filters.private, group=1)
async def emoji_state_handler(bot, message):
    if temp.EMOJI_ID.get(message.from_user.id):
        emoji_id = get_emoji_id(message)
        if emoji_id:
            await message.reply(f"**Custom Emoji ID is** \n\n`{emoji_id}`", quote=True)
        else:
            await message.reply("Oops !! No custom emoji found in the message.", quote=True)
        del temp.EMOJI_ID[message.from_user.id]
