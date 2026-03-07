#Thanks @dreamcinezone for helping in this journey 

import jinja2
import re
from info import *
from Deendayal_botz.Bot import DeendayalBot
from Deendayal_botz.util.human_readable import humanbytes
from Deendayal_botz.util.file_properties import get_file_ids
from Deendayal_botz.server.exceptions import InvalidHash
import urllib.parse
import logging
import aiohttp
from plugins.channel import extract_media_info

def parse_filename_for_template(file_name):
    details = {}

    # Season and Episode Extraction
    se_pattern = re.compile(r'(S\d+)(E\d+)', re.IGNORECASE)
    se_match = se_pattern.search(file_name)
    if se_match:
        details['season'] = se_match.group(1).upper()
        details['episode'] = se_match.group(2).upper()
    else:
        s_pattern = re.compile(r'(S\d+\s*COMBINED|S\d+|Season\s*\d+)', re.IGNORECASE)
        e_pattern = re.compile(r'(E\d+|Episode\s*\d+)', re.IGNORECASE)
        s_match = s_pattern.search(file_name)
        e_match = e_pattern.search(file_name)
        if s_match: details['season'] = s_match.group(1).upper()
        if e_match: details['episode'] = e_match.group(1).upper()

    # Year Extraction
    y_pattern = re.compile(r'\b(19\d{2}|20\d{2})\b')
    y_match = y_pattern.search(file_name)
    if y_match:
        details['year'] = y_match.group(1)

    # Language Extraction
    LANGUAGES = ["malayalam", "tamil", "english", "hindi", "telugu", "kannada", "gujarati", "marathi", "punjabi", "bhojpuri", "bengali", "bangla", "korean", "Indonesian", "japanese", "chinese", "spanish", "french"]
    langs = []
    for lang in LANGUAGES:
        if re.search(r'\b' + lang + r'\b', file_name, re.IGNORECASE):
            langs.append(lang.upper())
    if langs:
        details['language'] = "-".join(langs)

    # Quality Extraction
    qualities = [
        "WEB-DL", "WEBRip", "BluRay", "BDRip", "BRRip", "HDTC", "HC", "CAMRip",
        "Cam", "HDRip", "PreDVDRip", "DVDRip", "HDTS", "TS", "TeleSync", "PDVD", "VODRip", "VOD", "WEB DL", "WEB"
    ]
    for q in qualities:
        if re.search(r'\b' + q + r'\b', file_name, re.IGNORECASE):
            details['quality'] = q.upper()
            break

    # Name extraction using channel plugin logic for parity
    try:
        media_info = extract_media_info(file_name, "")
        details['name'] = media_info.get('base_name', file_name)
    except Exception as e:
        logging.error(f"Error extracting name via channel parser: {e}")
        details['name'] = file_name

    return details


async def render_page(id, secure_hash, src=None):
    file = await DeendayalBot.get_messages(int(LOG_CHANNEL), int(id))
    file_data = await get_file_ids(DeendayalBot, int(LOG_CHANNEL), int(id))
    if file_data.unique_id[:6] != secure_hash:
        logging.debug(f"link hash: {secure_hash} - {file_data.unique_id[:6]}")
        logging.debug(f"Invalid hash for message with - ID {id}")
        raise InvalidHash

    src = urllib.parse.urljoin(
        URL,
        f"{id}/{urllib.parse.quote_plus(file_data.file_name)}?hash={secure_hash}",
    )

    tag = file_data.mime_type.split("/")[0].strip()
    file_size = humanbytes(file_data.file_size)
    if tag in ["video", "audio"]:
        template_file = "Deendayal_botz/template/req.html"
    else:
        template_file = "Deendayal_botz/template/dl.html"
        async with aiohttp.ClientSession() as s:
            async with s.get(src) as u:
                file_size = humanbytes(int(u.headers.get("Content-Length")))

    with open(template_file) as f:
        template = jinja2.Template(f.read())

    file_name = file_data.file_name.replace("_", " ")
    file_name = re.sub(r"[\.\[\]\{\}\(\)\@]", " ", file_name)
    file_name = re.sub(r"\s+", " ", file_name).strip()

    parsed = parse_filename_for_template(file_name)

    return template.render(
        file_name=file_name,
        file_url=src,
        file_size=file_size,
        file_unique_id=file_data.unique_id,
        parsed_name=parsed.get('name', ''),
        parsed_season=parsed.get('season', ''),
        parsed_episode=parsed.get('episode', ''),
        parsed_year=parsed.get('year', ''),
        parsed_language=parsed.get('language', ''),
        parsed_quality=parsed.get('quality', '')
    )
