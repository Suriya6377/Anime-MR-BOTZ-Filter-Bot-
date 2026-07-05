from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ForceReply, CallbackQuery
from info import MOVIE_GROUP, ADMINS
from utils import temp
import info
import datetime
from plugins.Deendayal.Imdbposter import get_movie_details

# Handle potential missing MOVIE_UPDATE_CHANNEL gracefully to avoid ImportError
MOVIE_UPDATE_CHANNEL = getattr(info, 'MOVIE_UPDATE_CHANNEL', None)

# In-memory dictionary to store ongoing post sessions.
# Format: {user_id: {"message_id": int, "data": {}, "chat_id": int, "waiting_for": str, "prompt_message_id": int}}
POST_SESSIONS = {}

# A prompt mapping for when a user clicks a button
PROMPTS = {
    "poster": "Send Poster (Photo or URL):",
    "movie_name": "Enter Movie Name (e.g., Sirens Kiss S01):",
    "imdb_link": "Enter IMDb Link:",
    "tmdb_link": "Enter TMDb Link:",
    "genres": "Enter Genres:",
    "ott": "Enter OTT Platform:",
    "quality": "Enter Quality:",
    "audio": "Enter Audio:",
    "rating": "Enter Rating:",
    "duration": "Enter Duration:",
    "episodes": "Enter Episodes:"
}


def generate_post_text(data):
    ist = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now = datetime.datetime.now(ist)
    date_str = now.strftime("%d %b %Y")
    time_str = now.strftime("%I:%M:%S %p")

    movie_name = data.get("movie_name", "Unknown")
    if movie_name == "N/A":
        movie_name = "Unknown"

    poster_url = data.get("poster_url")
    imdb_link = data.get("imdb_link", "#")
    tmdb_link = data.get("tmdb_link", "#")
    genres = data.get("genres", "N/A")
    ott = data.get("ott", "N/A")
    quality = data.get("quality", "N/A")
    audio = data.get("audio", "N/A")
    rating = data.get("rating", "N/A")
    duration = data.get("duration", "N/A")
    episodes = data.get("episodes", "N/A")

    text = f"<blockquote><b>📥 𝖭𝖤𝖶 𝖥𝖨𝖫𝖤 𝖠𝖣𝖣𝖤𝖣 ✅</b></blockquote>\n\n"

    # Dynamically add IMDb or TMDb links
    links_block = ""
    if imdb_link != "#":
        links_block += f"⭐ <b><a href='{imdb_link}'>ɪᴍᴅʙ ɪɴғᴏ</a></b> "
    if tmdb_link != "#":
        links_block += f"⭐ <b><a href='{tmdb_link}'>ᴛᴍᴅʙ ɪɴғᴏ</a></b> "

    # Default fallback if neither is provided
    if not links_block:
         links_block = f"⭐ <b><a href='#'>ɪᴍᴅʙ ɪɴғᴏ</a></b>"

    text += f"🫥  <b><code>{movie_name}</code> ⿻ </b> | <a href='{poster_url or '#'}'></a>{links_block.strip()}\n"

    if genres != "N/A":
        text += f"\n<b>🎭 ɢᴇɴʀᴇs : {genres}</b>\n"

    if ott != "N/A":
        text += f"<b>🌐 ᴏᴛᴛ    : {ott}</b>\n\n"

    text += f"<b>📽 ǫᴜᴀʟɪᴛʏ : {quality}</b>\n\n"
    text += f"<b>🔊 ᴀᴜᴅɪᴏ   : {audio}</b>\n\n"

    if rating != "N/A":
        text += f"<b>🎞 ʀᴀᴛɪɴɢ  : {rating}</b>"

    if duration != "N/A":
        text += f"\n<b>⏱ ᴅᴜʀᴀᴛɪᴏɴ : </b><b>{duration}</b>"

    if episodes != "N/A":
        text += f"\n<b>🎬 ᴇᴘɪsᴏᴅᴇs : <b>{episodes}</b></b>\n"
    else:
        text += "\n"

    text += "<blockquote><b>〽️ Powered by - <a href='https://t.me/Nobita_Files_Filter_bot'>D͜͡e͜͡e͜͡n͜͡d͜͡a͜͡y͜͡a͜͡l͜͡ d͜͡h͜͡a͜͡k͜͡a͜͡d͜͡</a></b></blockquote>\n"
    text += f"<b>🕒 {date_str} | {time_str}</b>\n"

    return text


def get_post_keyboard(data):
    def get_text(key, label):
        val = data.get(key)
        if val and val != "N/A" and val != "#":
            if key == "poster":
                if data.get("poster_photo"):
                    return f"✅ {label} (Photo)"
                else:
                    return f"✅ {label} (URL)"
            return f"✅ {label}"
        return f"❌ {label}"

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_text("movie_name", "🫥 ᴍᴏᴠɪᴇ ɴᴀᴍᴇ"), callback_data="mp_movie_name"),
         InlineKeyboardButton(get_text("poster", "🖼️ ᴘᴏsᴛᴇʀ"), callback_data="mp_poster")],
        [InlineKeyboardButton(get_text("imdb_link", "⭐ Iᴍᴅʙ ɪɴғᴏ"), callback_data="mp_imdb_link"),
         InlineKeyboardButton(get_text("tmdb_link", "⭐ ᴛᴍᴅʙ ɪɴғᴏ"), callback_data="mp_tmdb_link")],
        [InlineKeyboardButton(get_text("genres", "🎭 ɢᴇɴʀᴇs"), callback_data="mp_genres"),
         InlineKeyboardButton(get_text("ott", "🌐 ᴏᴛᴛ"), callback_data="mp_ott")],
        [InlineKeyboardButton(get_text("quality", "📽 ǫᴜᴀʟɪᴛʏ"), callback_data="mp_quality"),
         InlineKeyboardButton(get_text("audio", "🔊 ᴀᴜᴅɪᴏ"), callback_data="mp_audio")],
        [InlineKeyboardButton(get_text("rating", "🎞 ʀᴀᴛɪɴɢ"), callback_data="mp_rating"),
         InlineKeyboardButton(get_text("duration", "⏱ ᴅᴜʀᴀᴛɪᴏɴ"), callback_data="mp_duration")],
        [InlineKeyboardButton(get_text("episodes", "🎬 ᴇᴘɪsᴏᴅᴇs"), callback_data="mp_episodes")],
        [InlineKeyboardButton(f"🔄 Aᴜᴛᴏ Fᴇᴛᴄʜ: {'Oɴ' if data.get('auto_fetch', False) else 'Oғғ'}", callback_data="mp_toggle_fetch")],
        [InlineKeyboardButton("✅ Pᴜʙʟɪsʜ Pᴏsᴛ", callback_data="mp_publish"),
         InlineKeyboardButton("🗑 Cᴀɴᴄᴇʟ", callback_data="mp_cancel")]
    ])


@Client.on_message(filters.command("post") & filters.user(ADMINS))
async def start_manual_post(client, message):
    if not MOVIE_UPDATE_CHANNEL:
        await message.reply_text("❌ MOVIE_UPDATE_CHANNEL is not set in info.py. Please set it before using this command.")
        return

    user_id = message.from_user.id
    if user_id in POST_SESSIONS:
        # Instead of blocking, we overwrite the previous session
        pass

    data = {k: "N/A" for k in PROMPTS.keys() if k != "poster"}
    data["poster"] = None
    data["imdb_link"] = "#"
    data["tmdb_link"] = "#"
    data["auto_fetch"] = False

    preview_text = "<b>Live Preview:</b>\n\n" + generate_post_text(data) + "\n\n<i>Click the buttons below to fill in the details. Once ready, click Publish.</i>"

    msg = await message.reply_text(
        preview_text,
        reply_markup=get_post_keyboard(data),
        parse_mode=enums.ParseMode.HTML,
        disable_web_page_preview=True
    )
    POST_SESSIONS[user_id] = {
        "message_id": msg.id,
        "data": data,
        "chat_id": message.chat.id,
        "waiting_for": None,
        "prompt_message_id": None
    }


@Client.on_callback_query(filters.regex(r"^mp_") & filters.user(ADMINS))
async def handle_post_callback(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in POST_SESSIONS:
        await callback_query.answer("No active post session.", show_alert=True)
        return

    session = POST_SESSIONS[user_id]

    if session["message_id"] != callback_query.message.id:
        await callback_query.answer("This is not your current active session. Send /post again.", show_alert=True)
        return

    action = callback_query.data.replace("mp_", "")

    if action == "cancel":
        del POST_SESSIONS[user_id]
        await callback_query.message.edit_text("Post session cancelled.")
        await callback_query.answer()
        return

    if action == "toggle_fetch":
        session["data"]["auto_fetch"] = not session["data"].get("auto_fetch", False)
        preview_text = "<b>Live Preview:</b>\n\n" + generate_post_text(session["data"]) + "\n\n<i>Click the buttons below to fill in the details. Once ready, click Publish.</i>"
        try:
            await callback_query.message.edit_text(
                text=preview_text,
                reply_markup=get_post_keyboard(session["data"]),
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception:
            pass
        await callback_query.answer("Auto Fetch toggled!")
        return

    if action == "publish":
        data = session["data"]
        # Basic validation
        if not data.get("movie_name") or data.get("movie_name") == "N/A":
            await callback_query.answer("Movie Name is required!", show_alert=True)
            return

        await callback_query.message.edit_text("Publishing post...")
        del POST_SESSIONS[user_id]
        await publish_post(client, callback_query.message.chat.id, data)
        await callback_query.answer()
        return

    # Set waiting state
    session["waiting_for"] = action

    prompt_text = PROMPTS.get(action, "Enter value:")

    # Show current value if it exists and isn't a placeholder
    current_val = session["data"].get(action)
    current_val_text = ""
    if current_val and current_val not in ["N/A", "#"]:
        if action == "poster" and session["data"].get("poster_photo"):
            current_val_text = "\n\n**Current Value:** `(Photo)`"
        elif action == "poster" and session["data"].get("poster_url"):
            current_val_text = f"\n\n**Current Value:** `{session['data']['poster_url']}`"
        else:
            current_val_text = f"\n\n**Current Value:** `{current_val}`"

    # Send a message to get the input
    try:
        prompt_msg = await client.send_message(
            chat_id=callback_query.message.chat.id,
            text=f"**{prompt_text}**{current_val_text}\n\n(Reply to this message with your input, or type 'skip')",
            reply_markup=ForceReply(selective=True)
        )
        session["prompt_message_id"] = prompt_msg.id
        await callback_query.answer()
    except Exception as e:
        await callback_query.answer(f"Error: {e}", show_alert=True)


import pyrogram

@Client.on_message(filters.reply & filters.user(ADMINS), group=-1)
async def process_manual_post_input(client, message):
    user_id = message.from_user.id
    if user_id not in POST_SESSIONS:
        return

    session = POST_SESSIONS[user_id]
    waiting_for = session.get("waiting_for")

    if not waiting_for:
        return

    # Check if the replied message is the prompt we actually sent
    if not message.reply_to_message or session.get("prompt_message_id") != message.reply_to_message.id:
        return

    key = waiting_for

    # Save user input to session data before deleting messages
    if key == "poster":
        if message.photo:
            session["data"]["poster_photo"] = message.photo.file_id
            session["data"]["poster"] = "photo" # just a marker
            session["data"]["poster_url"] = None
        else:
            session["data"]["poster_photo"] = None
            text = message.text.strip() if message.text else ""
            session["data"]["poster_url"] = text if text.lower() != 'skip' else None
            session["data"]["poster"] = "url" if text.lower() != 'skip' else None
    else:
        text = message.text.strip() if message.text else ""
        if text.lower() == 'skip':
            if key in ["imdb_link", "tmdb_link"]:
                session["data"][key] = "#"
            elif key == "movie_name":
                session["data"][key] = None # invalid state, but we handle it
            else:
                session["data"][key] = "N/A"
        else:
            session["data"][key] = text
            if key == "movie_name" and session["data"].get("auto_fetch"):
                try:
                    imdb_details = await get_movie_details(text)
                    if imdb_details:
                        if not session["data"].get("rating") or session["data"].get("rating") == "N/A":
                            raw_rating = imdb_details.get("rating", "N/A")
                            if raw_rating and raw_rating not in ["N/A", "None"]:
                                session["data"]["rating"] = f"{raw_rating}/10"
                            else:
                                session["data"]["rating"] = "N/A"
                        if not session["data"].get("genres") or session["data"].get("genres") == "N/A":
                            session["data"]["genres"] = imdb_details.get("genres", "N/A")
                        if not session["data"].get("duration") or session["data"].get("duration") == "N/A":
                            raw_runtime = imdb_details.get("runtime", "N/A")
                            if raw_runtime and raw_runtime not in ["N/A", "None"]:
                                import re
                                match = re.search(r'\d+', str(raw_runtime))
                                if match:
                                    minutes = int(match.group())
                                    kind = imdb_details.get("kind", "").lower()
                                    if "tv" in kind or "series" in kind:
                                        session["data"]["duration"] = f"{minutes} min/ep (Avg)"
                                    else:
                                        hours = minutes // 60
                                        mins = minutes % 60
                                        session["data"]["duration"] = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
                                else:
                                    session["data"]["duration"] = str(raw_runtime)
                            else:
                                session["data"]["duration"] = "N/A"
                        if not session["data"].get("imdb_link") or session["data"].get("imdb_link") == "#":
                            session["data"]["imdb_link"] = imdb_details.get("url", "#")
                        if not session["data"].get("poster_url") and not session["data"].get("poster_photo"):
                            if imdb_details.get("poster"):
                                session["data"]["poster_url"] = imdb_details.get("poster")
                                session["data"]["poster"] = "url"
                except Exception as e:
                    pass

    session["waiting_for"] = None
    session["prompt_message_id"] = None

    # Update the main message keyboard and preview text
    try:
        preview_text = "<b>Live Preview:</b>\n\n" + generate_post_text(session["data"]) + "\n\n<i>Click the buttons below to fill in the details. Once ready, click Publish.</i>"
        await client.edit_message_text(
            chat_id=session["chat_id"],
            message_id=session["message_id"],
            text=preview_text,
            reply_markup=get_post_keyboard(session["data"]),
            parse_mode=enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
    except Exception:
        pass # Ignore MessageNotModified or other errors

    # Delete user's input message and the bot's prompt message
    try:
        await message.delete()
        if message.reply_to_message:
            await message.reply_to_message.delete()
    except Exception:
        pass

    raise pyrogram.StopPropagation


async def publish_post(client, chat_id, data):
    try:
        movie_name = data.get("movie_name", "Unknown")
        if movie_name == "N/A":
            movie_name = "Unknown"

        text = generate_post_text(data)

        buttons = InlineKeyboardMarkup([
            #[
                #InlineKeyboardButton(
                    #'ɢᴇᴛ ғɪʟᴇs',
                    #url=f"https://t.me/{temp.U_NAME}?start=getfile-{movie_name.replace(' ', '-')}"
                #)
            #],
            [
                InlineKeyboardButton(
                    '♻️ 𝗠𝗼𝘃𝗶𝗲 𝗦𝗲𝗮𝗿𝗰𝗵 𝗚𝗿𝗼𝘂𝗽 ♻️',
                    url=MOVIE_GROUP
                )
            ]
        ])

        poster_photo = data.get("poster_photo")

        if poster_photo:
            await client.send_photo(
                chat_id=MOVIE_UPDATE_CHANNEL,
                photo=poster_photo,
                caption=text,
                reply_markup=buttons,
                parse_mode=enums.ParseMode.HTML,
                has_spoiler=True
            )
        else:
            await client.send_message(
                chat_id=MOVIE_UPDATE_CHANNEL,
                text=text,
                reply_markup=buttons,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=False
            )

        await client.send_message(chat_id, "✅ Post successfully sent to the update channel!")

    except Exception as e:
        await client.send_message(chat_id, f"❌ An error occurred while posting: {e}")
