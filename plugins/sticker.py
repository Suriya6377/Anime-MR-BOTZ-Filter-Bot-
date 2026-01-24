from pyrogram import Client, filters
from utils import temp

@Client.on_message(filters.command(["stickerid"]))
async def stickerid(bot, message):   
    if message.reply_to_message.sticker:
       await message.reply(f"**Sticker ID is**  \n `{message.reply_to_message.sticker.file_id}` \n \n ** Unique ID is ** \n\n`{message.reply_to_message.sticker.file_unique_id}`", quote=True)
    else: 
       await message.reply("Oops !! Not a sticker file")

@Client.on_message(filters.sticker & filters.private)
async def sticker_handler(bot, message):
    if temp.STICKER_ID.get(message.from_user.id):
        await message.reply(f"**Sticker ID is**  \n `{message.sticker.file_id}` \n \n ** Unique ID is ** \n\n`{message.sticker.file_unique_id}`", quote=True)
        del temp.STICKER_ID[message.from_user.id]
