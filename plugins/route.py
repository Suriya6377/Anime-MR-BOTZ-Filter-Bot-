from aiohttp import web
import aiohttp
import asyncio
import re
import math
import logging
import secrets
import time
import mimetypes
import json
from urllib.parse import parse_qs, urlparse, quote_plus
from pyrogram import enums
from pyrogram.errors import FloodWait
from aiohttp.http_exceptions import BadStatusLine
from Deendayal_botz.Bot import multi_clients, work_loads, DeendayalBot
from Deendayal_botz.server.exceptions import FIleNotFound, InvalidHash
from Deendayal_botz.zzint import StartTime, __version__
from Deendayal_botz.util.custom_dl import ByteStreamer
from Deendayal_botz.util.time_format import get_readable_time
import os
from info import *


routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.json_response("Deendayal_Botz")


from urllib.parse import quote, urlparse

def build_player_intent(stream_url: str, package: str, title: str = None) -> str:
    parsed = urlparse(stream_url)
    host_and_path = parsed.netloc + parsed.path
    if parsed.query:
        host_and_path += f"?{parsed.query}"
    fallback = quote(f"https://play.google.com/store/apps/details?id={package}", safe="")
    extras = f"scheme={parsed.scheme};package={package};type=video/*;"
    if title:
        extras += f"S.title={quote(title)};"
    extras += f"S.browser_fallback_url={fallback};"
    return f"intent://{host_and_path}#Intent;{extras}end"

@routes.get(r"/watch/{path:\S+}", allow_head=True)
async def watch_handler(request: web.Request):
    try:
        path = request.match_info["path"]
        match = re.search(r"^([a-zA-Z0-9_-]{6})(\d+)$", path)
        if match:
            secure_hash = match.group(1)
            id = int(match.group(2))
        else:
            id = int(re.search(r"(\d+)(?:\/\S+)?", path).group(1))
            secure_hash = request.rel_url.query.get("hash")

        from Deendayal_botz.util.file_properties import get_file_ids
        from Deendayal_botz.Bot import DeendayalBot
        import urllib.parse

        file_data = await get_file_ids(DeendayalBot, int(LOG_CHANNEL), int(id))
        if file_data.unique_id[:6] != secure_hash:
            raise InvalidHash

        stream_url = urllib.parse.urljoin(URL, f"{id}/{urllib.parse.quote_plus(file_data.file_name)}?hash={secure_hash}")

        # VLC Player intent
        vlc_url = build_player_intent(stream_url, "org.videolan.vlc", file_data.file_name)

        # MX Player intent
        mx_url = build_player_intent(stream_url, "com.mxtech.videoplayer.ad", file_data.file_name)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Watch Video</title>
    <style>
        body {{
            background-color: #000;
            color: #fff;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            font-family: sans-serif;
        }}
        .container {{
            width: 100%;
            max-width: 500px;
            display: flex;
            flex-direction: column;
            gap: 15px;
            padding: 10px;
            box-sizing: border-box;
        }}
        .video-wrapper {{
            width: 100%;
            aspect-ratio: 16/9;
            background: #000;
        }}
        video {{
            width: 100%;
            height: 100%;
            object-fit: contain;
        }}
        .buttons {{
            display: flex;
            gap: 10px;
            width: 100%;
        }}
        .btn {{
            flex: 1;
            padding: 12px;
            text-align: center;
            text-decoration: none;
            color: white;
            font-weight: bold;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            font-size: 14px;
        }}
        .btn-vlc {{ background-color: #FF8C00; }}
        .btn-mx {{ background-color: #F84C4C; }}
        .icon {{
            width: 20px;
            height: 20px;
            fill: currentColor;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="video-wrapper">
            <video controls autoplay playsinline>
                <source src="{stream_url}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
        </div>
        <div class="buttons">
            <a href="{vlc_url}" class="btn btn-vlc">
                <svg class="icon" viewBox="0 0 24 24"><path d="M12 2L3 20h18L12 2zm0 3.8l5.8 12.2H6.2L12 5.8z"/></svg>
                Open in VLC
            </a>
            <a href="{mx_url}" class="btn btn-mx">
                <svg class="icon" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                Open in MX Player
            </a>
        </div>
    </div>
</body>
</html>"""
        return web.Response(text=html, content_type='text/html')
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        pass
    except Exception as e:
        logging.critical(e.with_traceback(None))
        raise web.HTTPInternalServerError(text=str(e))


@routes.get("/tmdb", allow_head=True)
async def tmdb_handler(request):
    try:
        file_path = os.path.join(os.getcwd(), 'tmdb.html')
        loop = asyncio.get_running_loop()
        content = await loop.run_in_executor(None, lambda: open(file_path, 'r').read())
        return web.Response(text=content, content_type='text/html')
    except Exception as e:
        return web.Response(text=f"Error loading tmdb.html: {e}", status=500)


@routes.get("/api/tmdb/search", allow_head=True)
async def api_tmdb_search(request):
    query = request.rel_url.query.get("query")
    if not query:
        return web.json_response({"results": []})

    try:
        url = "https://api.themoviedb.org/3/search/multi"
        params = {
            "api_key": TMDB_API_KEY,
            "query": query,
            "include_adult": "false",
            "language": "en-US",
            "page": "1"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return web.json_response(data)
                else:
                    return web.json_response({"error": f"TMDB Error: {resp.status}"}, status=resp.status)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

@routes.get("/api/tmdb/discover", allow_head=True)
async def api_tmdb_discover(request):
    try:
        provider_id = request.rel_url.query.get("with_watch_providers")
        watch_region = request.rel_url.query.get("watch_region", "IN")
        page = request.rel_url.query.get("page", "1")
        media_type = request.rel_url.query.get("type", "movie") # movie or tv

        url = f"https://api.themoviedb.org/3/discover/{media_type}"
        params = {
            "api_key": TMDB_API_KEY,
            "watch_region": watch_region,
            "page": page,
            "sort_by": "popularity.desc",
            "include_adult": "false",
            "language": "en-US"
        }

        if provider_id and provider_id != "null":
             params["with_watch_providers"] = provider_id

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return web.json_response(data)
                else:
                    return web.json_response({"error": f"TMDB Error: {resp.status}"}, status=resp.status)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

@routes.get("/api/poster/search", allow_head=True)
async def api_poster_search(request):
    query = request.rel_url.query.get("query")
    if not query:
        return web.json_response({"error": "No query provided"}, status=400)

    try:
        # 1. Search
        search_url = "https://api.themoviedb.org/3/search/multi"
        params = {
            "api_key": TMDB_API_KEY,
            "query": query,
            "include_adult": "false",
            "language": "en-US",
            "page": "1"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url, params=params) as resp:
                if resp.status != 200:
                    return web.json_response({"error": "TMDB Search Failed"}, status=resp.status)
                data = await resp.json()


            # 2. Get Best Match
            results = data.get("results", [])
            # Filter for movie or tv only
            results = [r for r in results if r.get("media_type") in ["movie", "tv"]]

            if not results:
                match = re.search(r"^(.*)\s(\d{4})$", query)
                if match:
                    clean_query = match.group(1).strip()
                    year = match.group(2)

                    if clean_query:
                        params["query"] = clean_query
                        async with session.get(search_url, params=params) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                new_results = data.get("results", [])
                                new_results = [r for r in new_results if r.get("media_type") in ["movie", "tv"]]

                                if new_results:
                                    year_matches = []
                                    for r in new_results:
                                        date = r.get("release_date") or r.get("first_air_date")
                                        if date and date.startswith(year):
                                            year_matches.append(r)

                                    if year_matches:
                                        results = year_matches
                                    else:
                                        results = new_results

            if not results:
                 return web.json_response({"error": "No movie/tv results found"}, status=404)

            item = results[0]
            media_type = item.get("media_type")
            tmdb_id = item.get("id")

            title = item.get("title") or item.get("name")
            release_date = item.get("release_date") or item.get("first_air_date")
            year = release_date.split("-")[0] if release_date else ""
            rating = str(round(item.get("vote_average", 0), 1))

            # 3. Get Extra Details (Genres, Runtime, Vote Count, URL, OTT)
            details_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
            details_params = {
                "api_key": TMDB_API_KEY,
                "append_to_response": "watch/providers"
            }
            genres = []
            runtime = ""
            vote_count = ""
            homepage_url = ""
            ott_platforms = []

            async with session.get(details_url, params=details_params) as details_resp:
                if details_resp.status == 200:
                    details_data = await details_resp.json()
                    genres = [g.get("name") for g in details_data.get("genres", [])]

                    if media_type == "movie":
                        r = details_data.get("runtime")
                        if r:
                            h = r // 60
                            m = r % 60
                            runtime = f"{h}h {m}m" if h > 0 else f"{m}m"
                    else:
                        r = details_data.get("episode_run_time")
                        if r and len(r) > 0:
                            runtime = f"{r[0]}m/ep"

                    vote_count = details_data.get("vote_count", "")
                    homepage_url = f"https://www.themoviedb.org/{media_type}/{tmdb_id}"

                    providers = details_data.get("watch/providers", {}).get("results", {}).get("IN", {})
                    ott_platforms = [p.get("provider_name") for p in providers.get("flatrate", [])]

            # 4. Get Images
            img_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/images"

            # Empty include_image_language parameter fetches all available languages from TMDB
            img_params = {
                "api_key": TMDB_API_KEY,
                "include_image_language": ""
            }

            async with session.get(img_url, params=img_params) as img_resp:
                if img_resp.status != 200:
                     return web.json_response({"error": "TMDB Images Failed"}, status=img_resp.status)
                img_data = await img_resp.json()

            # 5. Process Images
            base_url = "https://image.tmdb.org/t/p/original"

            raw_posters = {"all": []}
            raw_backdrops = {"all": []}
            raw_logos = {"all": []}

            def process_list(source_list, target_dict):
                for img in source_list:
                    path = img.get("file_path")
                    if not path: continue
                    full_url = base_url + path
                    iso = img.get("iso_639_1")

                    # Add to 'all'
                    target_dict["all"].append(full_url)

                    # Add to specific lang
                    key = "null" if iso is None else iso
                    if key not in target_dict:
                        target_dict[key] = []
                    target_dict[key].append(full_url)

            process_list(img_data.get("posters", []), raw_posters)
            process_list(img_data.get("backdrops", []), raw_backdrops)
            process_list(img_data.get("logos", []), raw_logos)

            return web.json_response({
                "title": title,
                "year": year,
                "release_date": release_date,
                "rating": rating,
                "tmdb_id": tmdb_id,
                "genres": genres,
                "runtime": runtime,
                "vote_count": vote_count,
                "url": homepage_url,
                "ott": ott_platforms,
                "raw_posters": raw_posters,
                "raw_backdrops": raw_backdrops,
                "raw_logos": raw_logos
            })

    except Exception as e:
        logging.error(f"Search Error: {e}")
        return web.json_response({"error": str(e)}, status=500)

@routes.get("/api/img", allow_head=True)
async def api_img_proxy(request):
    path = request.rel_url.query.get("path")
    size = request.rel_url.query.get("size", "w342")
    if not path:
        return web.Response(status=404)

    url = f"https://image.tmdb.org/t/p/{size}{path}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    response = web.StreamResponse(status=200, headers=resp.headers)
                    await response.prepare(request)
                    async for chunk in resp.content.iter_chunked(1024):
                        await response.write(chunk)
                    await response.write_eof()
                    return response
                else:
                    return web.Response(status=resp.status)
    except Exception as e:
        return web.Response(status=500, text=str(e))

@routes.get("/api/tmdb/images", allow_head=True)
async def api_tmdb_images(request):
    id = request.rel_url.query.get("id")
    type = request.rel_url.query.get("type", "movie") # movie or tv
    if not id:
        return web.json_response({"posters": [], "backdrops": []})

    try:
        url = f"https://api.themoviedb.org/3/{type}/{id}/images"
        language = request.rel_url.query.get("language", "en")

        # Logic to handle different language selections
        if language == "all":
             include_image_language = "" # Empty string fetches all languages
        elif language == "null":
             include_image_language = "null"
        else:
             include_image_language = f"{language},null"

        params = {
            "api_key": TMDB_API_KEY,
            "include_image_language": include_image_language
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return web.json_response(data)
                else:
                    return web.json_response({"error": f"TMDB Error: {resp.status}"}, status=resp.status)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


@routes.get("/api/tmdb/browse")
async def api_tmdb_browse(request):
    category = request.rel_url.query.get("category")
    page = request.rel_url.query.get("page", "1")
    country = request.rel_url.query.get("country", "")

    url = ""
    params = {"api_key": TMDB_API_KEY, "page": page, "language": "en-US"}

    if country == "IN":
        params["with_origin_country"] = "IN"
        params["watch_region"] = "IN"

    if category == "trending":
        url = "https://api.themoviedb.org/3/trending/all/day"
    elif category == "popular":
        url = "https://api.themoviedb.org/3/discover/movie" if country == "IN" else "https://api.themoviedb.org/3/movie/popular"
        if country == "IN":
            params["sort_by"] = "popularity.desc"
    elif category == "top_rated":
        url = "https://api.themoviedb.org/3/discover/movie" if country == "IN" else "https://api.themoviedb.org/3/movie/top_rated"
        if country == "IN":
            params["sort_by"] = "vote_average.desc"
            params["vote_count.gte"] = 50
    elif category == "now_playing":
        url = "https://api.themoviedb.org/3/discover/movie" if country == "IN" else "https://api.themoviedb.org/3/movie/now_playing"
        if country == "IN":
            params["with_release_type"] = "2|3" # Theatrical
    elif category == "in_theaters":
        url = "https://api.themoviedb.org/3/discover/movie"
        params["with_release_type"] = "2|3" # Theatrical
        # TMDB's "now_playing" does not always match exactly to what is currently in theaters depending on region,
        # but release type 2|3 is the most standard way to check for theatrical releases.
    elif category == "upcoming":
        url = "https://api.themoviedb.org/3/discover/movie" if country == "IN" else "https://api.themoviedb.org/3/movie/upcoming"
        if country == "IN":
            import datetime
            today = datetime.date.today().strftime("%Y-%m-%d")
            params["primary_release_date.gte"] = today
            params["sort_by"] = "popularity.desc"
    elif category == "movies":
        url = "https://api.themoviedb.org/3/discover/movie"
        params["sort_by"] = "popularity.desc"
    elif category == "tv":
        url = "https://api.themoviedb.org/3/discover/tv"
        params["sort_by"] = "popularity.desc"
    elif category == "anime":
        url = "https://api.themoviedb.org/3/discover/tv"
        params["with_genres"] = "16"
        params["with_original_language"] = "ja"
    elif category == "web_series":
        url = "https://api.themoviedb.org/3/discover/tv"
        params["with_networks"] = "213|1024|2739|453"
    else:
        return web.json_response({"error": "Invalid category"}, status=400)

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for item in data.get("results", []):
                        if item.get("poster_path"):
                            results.append({
                                "id": item.get("id"),
                                "title": item.get("title") or item.get("name"),
                                "poster_path": item.get("poster_path"),
                                "media_type": item.get("media_type") or ("tv" if category in ["tv", "anime", "web_series"] else "movie"),
                                "year": (item.get("release_date") or item.get("first_air_date") or "")[:4],
                                "rating": round(item.get("vote_average", 0), 1)
                            })
                    return web.json_response({"results": results})
                else:
                    return web.json_response({"error": f"TMDB Error: {resp.status}"}, status=resp.status)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

@routes.get("/api/tmdb/details")
async def api_tmdb_details(request):
    tmdb_id = request.rel_url.query.get("id")
    media_type = request.rel_url.query.get("type", "movie")

    if not tmdb_id:
        return web.json_response({"error": "Missing ID"}, status=400)

    try:
        details_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
        images_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/images"

        params = {
            "api_key": TMDB_API_KEY,
            "append_to_response": "watch/providers"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(details_url, params=params) as resp:
                if resp.status == 200:
                    details = await resp.json()
                else:
                    return web.json_response({"error": "Details fetch failed"}, status=resp.status)

            img_params = {"api_key": TMDB_API_KEY, "include_image_language": ""} # Empty string fetches all languages
            async with session.get(images_url, params=img_params) as resp:
                if resp.status == 200:
                    images = await resp.json()
                else:
                    images = {"posters": [], "backdrops": [], "logos": []}

        genres = [g['name'] for g in details.get('genres', [])]

        raw_posters = {"all": []}
        raw_backdrops = {"all": []}
        raw_logos = {"all": []}

        for img in images.get("posters", []):
            lang = img.get("iso_639_1") or "null"
            if lang not in raw_posters:
                raw_posters[lang] = []
            url = f"/api/img?path={img['file_path']}&size=original"
            raw_posters[lang].append(url)
            raw_posters["all"].append(url)

        for img in images.get("backdrops", []):
            lang = img.get("iso_639_1") or "null"
            if lang not in raw_backdrops:
                raw_backdrops[lang] = []
            url = f"/api/img?path={img['file_path']}&size=original"
            raw_backdrops[lang].append(url)
            raw_backdrops["all"].append(url)

        for img in images.get("logos", []):
            lang = img.get("iso_639_1") or "null"
            if lang not in raw_logos:
                raw_logos[lang] = []
            url = f"/api/img?path={img['file_path']}&size=original"
            raw_logos[lang].append(url)
            raw_logos["all"].append(url)

        year = ""
        if media_type == "movie" and details.get("release_date"):
            year = details["release_date"][:4]
        elif media_type == "tv" and details.get("first_air_date"):
            year = details["first_air_date"][:4]

        runtime = ""
        if media_type == "movie" and details.get("runtime"):
            h = details["runtime"] // 60
            m = details["runtime"] % 60
            runtime = f"{h}h {m}m"
        elif media_type == "tv" and details.get("episode_run_time") and len(details["episode_run_time"]) > 0:
            runtime = f"{details['episode_run_time'][0]} min/ep"

        # Get OTT info using TMDB's watch/providers
        ott_platforms = []
        providers = details.get("watch/providers", {}).get("results", {}).get("IN", {})
        if providers:
            ott_platforms = [p.get("provider_name") for p in providers.get("flatrate", [])]

        return web.json_response({
            "title": details.get("title") or details.get("name"),
            "year": year,
            "release_date": details.get("release_date") or details.get("first_air_date"),
            "rating": round(details.get("vote_average", 0), 1),
            "vote_count": details.get("vote_count", 0),
            "genres": genres,
            "runtime": runtime,
            "url": f"https://www.themoviedb.org/{media_type}/{tmdb_id}",
            "tmdb_id": tmdb_id,
            "ott": ott_platforms,
            "raw_posters": raw_posters,
            "raw_backdrops": raw_backdrops,
            "raw_logos": raw_logos
        })

    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)

@routes.post("/api/tmdb/send_image")
async def send_image_handler(request):
    try:
        data = await request.json()
        init_data = data.get('initData')
        image_url = data.get('url')
        title = data.get('title')

        if not init_data or not image_url:
            return web.json_response({"error": "Missing data"}, status=400)

        # Reconstruct TMDB URL if using proxy
        if "/api/img" in image_url:
            parsed = urlparse(image_url)
            params = parse_qs(parsed.query)
            path = params.get('path', [''])[0]
            size = params.get('size', ['w342'])[0]
            if path:
                image_url = f"https://image.tmdb.org/t/p/{size}{path}"

        # Parse initData to get user ID
        parsed_init_data = parse_qs(init_data)
        user_json = parsed_init_data.get('user', [''])[0]
        if not user_json:
             return web.json_response({"error": "Invalid user data"}, status=400)

        user_data = json.loads(user_json)
        user_id = user_data.get('id')

        if not user_id:
             return web.json_response({"error": "User ID not found"}, status=400)

        # Send image
        client = multi_clients[0]
        caption = f"🎬 <b>{title}</b>"

        await client.send_photo(has_spoiler=True,
            chat_id=user_id,
            photo=image_url,
            caption=caption,
            parse_mode=enums.ParseMode.HTML
        )

        return web.json_response({"success": True})
    except Exception as e:
        logging.error(f"Error sending image: {e}")
        return web.json_response({"error": str(e)}, status=500)


@routes.get("/1dm")
async def one_dm_handler(request):
    try:
        download_url = request.rel_url.query.get("url")
        filename = request.rel_url.query.get("filename")
        if not download_url or not filename:
            return web.Response(text="Missing parameters", status=400)

        encoded_filename = quote_plus(filename)
        intent_url = f"intent:{download_url}#Intent;package=idm.internet.download.manager;S.title={encoded_filename};end"
        intent_url_js = json.dumps(intent_url)

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Opening 1DM...</title>
            <script>
                window.onload = function() {{
                    var intentUrl = {intent_url_js};
                    window.location.href = intentUrl;
                    setTimeout(function() {{
                        var link = document.createElement('a');
                        link.href = intentUrl;
                        link.innerText = "click here";
                        document.body.innerHTML = "If 1DM didn't open, ";
                        document.body.appendChild(link);
                        document.body.appendChild(document.createTextNode("."));
                    }}, 1000);
                }};
            </script>
        </head>
        <body>
            <p>Opening 1DM...</p>
        </body>
        </html>
        """
        return web.Response(text=html_content, content_type='text/html')
    except Exception as e:
        return web.Response(text=f"Error: {e}", status=500)


@routes.get(r"/{path:\S+}", allow_head=True)
async def stream_handler(request: web.Request):
    try:
        path = request.match_info["path"]
        match = re.search(r"^([a-zA-Z0-9_-]{6})(\d+)$", path)
        if match:
            secure_hash = match.group(1)
            id = int(match.group(2))
        else:
            id = int(re.search(r"(\d+)(?:\/\S+)?", path).group(1))
            secure_hash = request.rel_url.query.get("hash")
        return await media_streamer(request, id, secure_hash)
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FIleNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        pass
    except Exception as e:
        logging.critical(e.with_traceback(None))
        raise web.HTTPInternalServerError(text=str(e))

class_cache = {}

async def media_streamer(request: web.Request, id: int, secure_hash: str):
    range_header = request.headers.get("Range", 0)
    
    index = min(work_loads, key=work_loads.get)
    faster_client = multi_clients[index]
    
    if MULTI_CLIENT:
        logging.info(f"Client {index} is now serving {request.remote}")

    while True:
        if faster_client in class_cache:
            tg_connect = class_cache[faster_client]
            logging.debug(f"Using cached ByteStreamer object for client {index}")
        else:
            logging.debug(f"Creating new ByteStreamer object for client {index}")
            tg_connect = ByteStreamer(faster_client)
            class_cache[faster_client] = tg_connect
        logging.debug("before calling get_file_properties")
        try:
            file_id = await tg_connect.get_file_properties(id)
            break
        except FloodWait as e:
            logging.warning(f"Client {index} got FloodWait. Falling back to another client.")
            work_loads[index] += e.value

            async def decrease_workload(idx, val):
                await asyncio.sleep(val)
                work_loads[idx] -= val
            asyncio.create_task(decrease_workload(index, e.value))

            old_index = index
            index = min(work_loads, key=work_loads.get)

            if index == old_index or work_loads[index] >= e.value:
                # All clients are rate-limited
                logging.warning("All clients are rate-limited. Sleeping.")
                await asyncio.sleep(e.value)

            faster_client = multi_clients[index]
    logging.debug("after calling get_file_properties")
    
    if file_id.unique_id[:6] != secure_hash:
        logging.debug(f"Invalid hash for message with ID {id}")
        raise InvalidHash
    
    file_size = file_id.file_size
    mime_type = file_id.mime_type or "video/mp4"
    file_name = file_id.file_name

    if not file_name:
        try:
            file_name = f"{secrets.token_hex(2)}.{mime_type.split('/')[1]}"
        except (IndexError, AttributeError):
            file_name = f"{secrets.token_hex(2)}.unknown"

    from_bytes = 0
    until_bytes = file_size - 1

    if range_header:
        range_match = re.search(r"bytes=(\d*)-(\d*)", range_header)
        if range_match:
            start_str = range_match.group(1)
            end_str = range_match.group(2)

            if start_str and end_str:
                from_bytes = int(start_str)
                until_bytes = int(end_str)
            elif start_str:
                from_bytes = int(start_str)
                until_bytes = file_size - 1
            elif end_str:
                length = int(end_str)
                from_bytes = file_size - length
                until_bytes = file_size - 1

    if from_bytes >= file_size or from_bytes < 0:
        return web.Response(
            status=416,
            body="416: Range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )
    if until_bytes >= file_size:
        until_bytes = file_size - 1
    if until_bytes < from_bytes:
        until_bytes = from_bytes

    until_bytes = min(until_bytes, file_size - 1)
    req_length = until_bytes - from_bytes + 1

    async def byte_stream_generator(client, msg_id):
        chunk_size = 1024 * 1024
        offset_chunk = from_bytes // chunk_size
        limit_chunk = math.ceil((until_bytes + 1) / chunk_size) - offset_chunk

        message = await client.get_messages(int(LOG_CHANNEL), msg_id)

        current_byte = offset_chunk * chunk_size
        async for chunk in client.stream_media(message, limit=limit_chunk, offset=offset_chunk):
            chunk_start = current_byte
            chunk_end = current_byte + len(chunk)

            # Calculate relative slice indices safely
            slice_start = max(0, from_bytes - chunk_start)
            slice_end = min(len(chunk), until_bytes + 1 - chunk_start)

            yield chunk[slice_start:slice_end]
            current_byte = chunk_end
            if current_byte > until_bytes:
                break

    body = byte_stream_generator(faster_client, id)

    headers = {
        "Content-Type": mime_type,
        "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
        "Content-Length": str(req_length),
        "Content-Disposition": f'attachment; filename="{file_name}"',
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-cache",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Expose-Headers": "Content-Range, Accept-Ranges, Content-Length",
        "Connection": "keep-alive"
    }


    response = web.StreamResponse(
        status=206 if range_header else 200,
        headers=headers
    )
    await response.prepare(request)

    async for chunk in body:
        await response.write(chunk)


    return response
