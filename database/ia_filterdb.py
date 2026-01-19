import logging
from struct import pack
import re
import base64
from pyrogram.file_id import FileId
from pymongo.errors import DuplicateKeyError
from umongo import Instance, Document, fields
from motor.motor_asyncio import AsyncIOMotorClient
from marshmallow.exceptions import ValidationError
from info import CAPTION_LANGUAGES, DATABASE_URI, DATABASE_URI2, DATABASE_NAME, COLLECTION_NAME, USE_CAPTION_FILTER, MAX_B_TN, DEENDAYAL_MOVIE_UPDATE_CHANNEL, OWNERID
from utils import get_settings, save_group_settings, temp, get_status
from database.users_chats_db import add_name
from .Imdbposter import get_movie_details, fetch_image
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
#---------------------------------------------------------
# Some basic variables needed
tempDict = {'indexDB': DATABASE_URI}

# Primary DB
client = AsyncIOMotorClient(DATABASE_URI)
db = client[DATABASE_NAME]
instance = Instance.from_db(db)

#secondary db
client2 = AsyncIOMotorClient(DATABASE_URI2)
db2 = client2[DATABASE_NAME]
instance2 = Instance.from_db(db2)


# Primary DB Model
@instance.register
class Media(Document):
    file_id = fields.StrField(attribute='_id')
    file_ref = fields.StrField(allow_none=True)
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    file_type = fields.StrField(allow_none=True)
    mime_type = fields.StrField(allow_none=True)
    caption = fields.StrField(allow_none=True)

    class Meta:
        indexes = ('$file_name', )
        collection_name = COLLECTION_NAME

@instance2.register
class Media2(Document):
    file_id = fields.StrField(attribute='_id')
    file_ref = fields.StrField(allow_none=True)
    file_name = fields.StrField(required=True)
    file_size = fields.IntField(required=True)
    file_type = fields.StrField(allow_none=True)
    mime_type = fields.StrField(allow_none=True)
    caption = fields.StrField(allow_none=True)

    class Meta:
        indexes = ('$file_name', )
        collection_name = COLLECTION_NAME

def get_ott_by_filename(filename):
    if not filename:
        return None
    filename = filename.lower()
    if "jiocinema" in filename or "jio" in filename or "jhs" in filename or "jiohotstar" in filename:
        return "Jio Hotstar"
    elif "amzn" in filename or "amazon" in filename:
        return "Amazon Prime Video"
    elif "nf" in filename or "netflix" in filename:
        return "Netflix"
    elif "dsnp" in filename or "disney" in filename or "hotstar" in filename:
        return "Disney+ Hotstar"
    elif "zee5" in filename:
        return "Zee5"
    elif "sonyliv" in filename or "sl" in filename:
        return "SonyLIV"
    elif "hbo" in filename:
        return "HBO Max"
    elif "apple" in filename or "atvp" in filename:
        return "Apple TV+"
    elif "hulu" in filename:
        return "Hulu"
    elif "mubi" in filename:
        return "Mubi"
    elif "lionsgate" in filename:
        return "Lionsgate Play"
    elif "aha" in filename:
        return "Aha"
    return None

async def choose_mediaDB():
    """This Function chooses which database to use based on the value of indexDB key in the dict tempDict."""
    global saveMedia
    if tempDict['indexDB'] == DATABASE_URI:
        logger.info("Using first db (Media)")
        saveMedia = Media
    else:
        logger.info("Using second db (Media2)")
        saveMedia = Media2

async def save_file(bot, media):
  """Save file in database"""
  global saveMedia
  file_id, file_ref = unpack_new_file_id(media.file_id)
  file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
  try:
    if saveMedia == Media2: 
        if await Media.count_documents({'file_id': file_id}, limit=1):
            logger.warning(f'{file_name} is already saved in primary database!')
            if await get_status(bot.me.id):
                await send_msg(bot, file_name, media.caption.html if media.caption else "")
            return False, 0
    file = saveMedia(
        file_id=file_id,
        file_ref=file_ref,
        file_name=file_name,
        file_size=media.file_size,
        file_type=media.file_type,
        mime_type=media.mime_type,
        caption=media.caption.html if media.caption else None,
    )
  except ValidationError:
    logger.exception('Error occurred while saving file in database')
    return False, 2
  else:
    try:
      await file.commit()
    except DuplicateKeyError:
      logger.warning(f'{getattr(media, "file_name", "NO_FILE")} is already saved in database')
      if await get_status(bot.me.id):
        await send_msg(bot, file.file_name, file.caption)
      return False, 0
    else:
        logger.info(f'{getattr(media, "file_name", "NO_FILE")} is saved to database')
        if await get_status(bot.me.id):
            await send_msg(bot, file.file_name, file.caption)
        return True, 1

async def get_search_results(chat_id, query, file_type=None, max_results=10, offset=0, filter=False):
    """For given query return (results, next_offset)"""
    if chat_id is not None:
        settings = await get_settings(int(chat_id))
        try:
            if settings['max_btn']:
                max_results = 10
            else:
                max_results = int(MAX_B_TN)
        except KeyError:
            await save_group_settings(int(chat_id), 'max_btn', False)
            settings = await get_settings(int(chat_id))
            if settings['max_btn']:
                max_results = 10
            else:
                max_results = int(MAX_B_TN)
    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_()]')
    
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except:
        return []

    if USE_CAPTION_FILTER:
        filter = {'$or': [{'file_name': regex}, {'caption': regex}]}
    else:
        filter = {'file_name': regex}

    if file_type:
        filter['file_type'] = file_type

    total_results = ((await Media.count_documents(filter))+(await Media2.count_documents(filter)))

    #verifies max_results is an even number or not
    if max_results%2 != 0: 
        logger.info(f"Since max_results is an odd number ({max_results}), bot will use {max_results+1} as max_results to make it even.")
        max_results += 1

    cursor = Media.find(filter)
    cursor2 = Media2.find(filter)

    cursor.sort('$natural', -1)
    cursor2.sort('$natural', -1)

    cursor2.skip(offset).limit(max_results)

    fileList2 = await cursor2.to_list(length=max_results)
    if len(fileList2)<max_results:
        next_offset = offset+len(fileList2)
        cursorSkipper = (next_offset-(await Media2.count_documents(filter)))
        cursor.skip(cursorSkipper if cursorSkipper>=0 else 0).limit(max_results-len(fileList2))
        fileList1 = await cursor.to_list(length=(max_results-len(fileList2)))
        files = fileList2+fileList1
        next_offset = next_offset + len(fileList1)
    else:
        files = fileList2
        next_offset = offset + max_results
    if next_offset >= total_results:
        next_offset = ''
    return files, next_offset, total_results


async def get_bad_files(query, file_type=None, filter=False):
    """For given query return (results, next_offset)"""
    query = query.strip()
    if not query:
        raw_pattern = '.'
    elif ' ' not in query:
        raw_pattern = r'(\b|[\.\+\-_])' + query + r'(\b|[\.\+\-_])'
    else:
        raw_pattern = query.replace(' ', r'.*[\s\.\+\-_()]')
    
    try:
        regex = re.compile(raw_pattern, flags=re.IGNORECASE)
    except:
        return []

    if USE_CAPTION_FILTER:
        filter = {'$or': [{'file_name': regex}, {'caption': regex}]}
    else:
        filter = {'file_name': regex}

    if file_type:
        filter['file_type'] = file_type

    cursor = Media.find(filter)
    cursor2 = Media2.find(filter)

    cursor.sort('$natural', -1)
    cursor2.sort('$natural', -1)

    files = ((await cursor2.to_list(length=(await Media2.count_documents(filter))))+(await cursor.to_list(length=(await Media.count_documents(filter)))))

    total_results = len(files)

    return files, total_results

async def get_file_details(query):
    filter = {'file_id': query}
    cursor = Media.find(filter)
    filedetails = await cursor.to_list(length=1)
    if not filedetails:
        cursor2 = Media2.find(filter)
        filedetails = await cursor2.to_list(length=1)
    return filedetails


async def get_series_episodes_info(series_title):
    if not series_title:
        return None
    regex_str = r"^" + re.escape(series_title) + r".*"
    try:
        db_regex = re.compile(regex_str, re.IGNORECASE)
    except:
        return None

    filter_dict = {'file_name': db_regex}
    found_seasons = {}

    for db_cursor in [Media.find(filter_dict, {'file_name': 1}), Media2.find(filter_dict, {'file_name': 1})]:
        async for doc in db_cursor:
            file_name = doc['file_name']
            season_match = re.search(r"(?i)(?:s|season)\s*0*(\d{1,2})", file_name)
            episode_match = re.search(r"(?i)(?:e|episode)\s*0*(\d{1,3}(?:-\d{1,3})?)", file_name)

            if season_match and episode_match:
                try:
                    season = int(season_match.group(1))
                    val = episode_match.group(1)

                    if season not in found_seasons:
                        found_seasons[season] = set()

                    if '-' in val:
                        s, e = val.split('-')
                        found_seasons[season].add(int(s))
                        found_seasons[season].add(int(e))
                    else:
                        found_seasons[season].add(int(val))
                except: pass

    return found_seasons


def encode_file_id(s: bytes) -> str:
    r = b""
    n = 0

    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0

            r += bytes([i])

    return base64.urlsafe_b64encode(r).decode().rstrip("=")

def encode_file_ref(file_ref: bytes) -> str:
    return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")

def unpack_new_file_id(new_file_id):
    """Return file_id, file_ref"""
    decoded = FileId.decode(new_file_id)
    file_id = encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash
        )
    )
    file_ref = encode_file_ref(decoded.file_reference)
    return file_id, file_ref


async def send_msg(bot, filename, caption): 
    try:
        caption = caption or ""
        ott = get_ott_by_filename(filename) or get_ott_by_filename(caption) or "N/A"

        filename = re.sub(r'\(\@\S+\)|\[\@\S+\]|\b@\S+|\bwww\.\S+', '', filename).strip()
        caption = re.sub(r'\(\@\S+\)|\[\@\S+\]|\b@\S+|\bwww\.\S+', '', caption).strip()
        
        year_match = re.search(r"\b(19|20)\d{2}\b", caption)
        year = year_match.group(0) if year_match else None

        # Extract season and episode
        season_match = re.search(r"(?i)(?:s|season)\s*0*(\d{1,2})", filename) or re.search(r"(?i)(?:s|season)\s*0*(\d{1,2})", caption)
        episode_match = re.search(r"(?i)(?:e|episode)\s*0*(\d{1,3}(?:-\d{1,3})?)", filename) or re.search(r"(?i)(?:e|episode)\s*0*(\d{1,3}(?:-\d{1,3})?)", caption)

        season = season_match.group(1) if season_match else None
        episode = episode_match.group(1) if episode_match else None

        formatted_episodes = ""
        if season:
            search_title = filename
            match = re.search(r"(?i)(?:s|season)\s*0*(\d{1,2})", filename)
            if match:
                search_title = filename[:match.start()].strip()

            found_seasons_data = await get_series_episodes_info(search_title)

            if found_seasons_data:
                # Add current episode if valid to ensure it's included in range
                if episode:
                    try:
                        current_season = int(season)
                        if current_season not in found_seasons_data:
                            found_seasons_data[current_season] = set()

                        if '-' in episode:
                            s, e = episode.split('-')
                            found_seasons_data[current_season].add(int(s))
                            found_seasons_data[current_season].add(int(e))
                        else:
                            found_seasons_data[current_season].add(int(episode))
                    except: pass

                parts = []
                sorted_seasons = sorted(found_seasons_data.keys())
                for s_num in sorted_seasons:
                    eps = found_seasons_data[s_num]
                    if eps:
                        min_ep = min(eps)
                        max_ep = max(eps)
                        ep_str = f"{min_ep}-{max_ep}" if min_ep != max_ep else f"{min_ep}"
                        parts.append(f"S{s_num:02d}: E ≫ {ep_str}")

                formatted_episodes = " | ".join(parts)

        if year:
            filename = filename[: filename.find(year) + 4]  
        elif season and season in filename:
            # If season found, strip everything after season info for cleaner title
            match = re.search(r"(?i)(?:s|season)\s*0*(\d{1,2})", filename)
            if match:
                filename = filename[:match.start()].strip()

        qualities = ["ORG", "org", "hdcam", "HDCAM", "HQ", "hq", "HDRip", "hdrip", "camrip", "CAMRip", "hdtc", "predvd", "DVDscr", "dvdscr", "dvdrip", "dvdscr", "HDTC", "dvdscreen", "HDTS", "hdts"]
        quality = await get_qualities(caption.lower(), qualities) or "HDRip"

        language = ""
        possible_languages = CAPTION_LANGUAGES
        for lang in possible_languages:
            if lang.lower() in caption.lower():
                language += f"{lang}, "
        language = language[:-2] if language else "Not idea 😄"

        filename = re.sub(r"[\(\)\[\]\{\}:;'\-!]", "", filename)

        tz = pytz.timezone('Asia/Kolkata')
        now = datetime.now(tz)
        date_time = now.strftime("%d %b %Y | %I:%M:%S %p")

        if await add_name(OWNERID, filename):
            imdb = await get_movie_details(filename)  
            resized_poster = None

            title = filename
            rating = "N/A"
            genres = "N/A"
            final_year = year

            imdb_url = None
            if imdb:
                poster_url = imdb.get('poster_url')
                title = imdb.get('title') or filename
                rating = imdb.get('rating') or "N/A"
                genres = imdb.get('genres') or "N/A"
                imdb_url = imdb.get('url')
                if imdb.get('year'):
                    final_year = str(imdb.get('year'))
                if poster_url:
                    resized_poster = await fetch_image(poster_url)  

            display_title = title
            if final_year and str(final_year) not in title:
                display_title = f"{title} {final_year}"

            imdb_link = f"<a href='{imdb_url}'><b>IMDB INFO</b></a>" if imdb_url else "<b>IMDB INFO</b>"

            text = f" <blockquote><b>📥NEW FILE ADDED✅</b></blockquote> \n\n" \
                   f"😐 <b>{display_title}</b> ⧉ | ⭐ {imdb_link}\n\n" \
                   f"🎭 <b>ɢᴇɴʀᴇs :</b> {genres}\n" \
                   f"🌐 <b>ᴏᴛᴛ :</b> {ott}\n" \
                   f"🎥 <b>ǫᴜᴀʟɪᴛʏ :</b> {quality}\n" \
                   f"🔊 <b>ᴀᴜᴅɪᴏ :</b> {language}\n\n" \
                   f"🎞 <b>ʀᴀᴛɪɴɢ :</b> {rating}\n"

            if formatted_episodes:
                text += f"🎬 <b>ᴇᴘɪsᴏᴅᴇs :</b> {formatted_episodes}\n"

            text += f" <blockquote><b>〽️ Powered by <a href="https://t.me/Nobita_Files_Filter_bot">Deendayal Dhakad</a></b></blockquote> \n" \
                   f"🕒 {date_time}"

            filenames = filename.replace(" ", '-')
            btn = [[InlineKeyboardButton('🌲 Get Files 🌲', url=f"https://telegram.me/{temp.U_NAME}?start=getfile-{filenames}")]]
            
            if resized_poster:
                await bot.send_photo(chat_id=DEENDAYAL_MOVIE_UPDATE_CHANNEL, photo=resized_poster, caption=text, reply_markup=InlineKeyboardMarkup(btn))
            else:              
                await bot.send_message(chat_id=DEENDAYAL_MOVIE_UPDATE_CHANNEL, text=text, reply_markup=InlineKeyboardMarkup(btn))

    except:
        pass

async def get_qualities(text, qualities: list):
    """Get all Quality from text"""
    quality = []
    for q in qualities:
        if q in text:
            quality.append(q)
    quality = ", ".join(quality)
    return quality[:-2] if quality.endswith(", ") else quality






