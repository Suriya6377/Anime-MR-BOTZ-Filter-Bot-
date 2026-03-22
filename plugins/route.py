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
from aiohttp.http_exceptions import BadStatusLine
from Deendayal_botz.Bot import multi_clients, work_loads, DeendayalBot
from Deendayal_botz.server.exceptions import FIleNotFound, InvalidHash
from Deendayal_botz.zzint import StartTime, __version__
from Deendayal_botz.util.custom_dl import ByteStreamer
from Deendayal_botz.util.time_format import get_readable_time
from Deendayal_botz.util.render_template import render_page
import os
from info import *


routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.json_response("Deendayal_Botz")


@routes.get(r"/watch/{path:\S+}", allow_head=True)
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
        return web.Response(text=await render_page(id, secure_hash), content_type='text/html')
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

            # 3. Get Images
            img_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/images"

            # Broad list of languages to support the frontend filters
            langs = "en,null,hi,kn,te,ta,ml,bn,gu,mr,pa,fr,es,de,ru,ja,ko,zh"
            img_params = {
                "api_key": TMDB_API_KEY,
                "include_image_language": langs
            }

            async with session.get(img_url, params=img_params) as img_resp:
                if img_resp.status != 200:
                     return web.json_response({"error": "TMDB Images Failed"}, status=img_resp.status)
                img_data = await img_resp.json()

            # 4. Process Images
            base_url = "https://image.tmdb.org/t/p/original"

            raw_posters = {"all": []}
            raw_backdrops = {"all": []}

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

            return web.json_response({
                "title": title,
                "year": year,
                "release_date": release_date,
                "rating": rating,
                "tmdb_id": tmdb_id,
                "raw_posters": raw_posters,
                "raw_backdrops": raw_backdrops
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
             include_image_language = "en,hi,kn,te,ta,ml,bn,gu,mr,pa,null"
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

    if faster_client in class_cache:
        tg_connect = class_cache[faster_client]
        logging.debug(f"Using cached ByteStreamer object for client {index}")
    else:
        logging.debug(f"Creating new ByteStreamer object for client {index}")
        tg_connect = ByteStreamer(faster_client)
        class_cache[faster_client] = tg_connect
    logging.debug("before calling get_file_properties")
    file_id = await tg_connect.get_file_properties(id)
    logging.debug("after calling get_file_properties")
    
    if file_id.unique_id[:6] != secure_hash:
        logging.debug(f"Invalid hash for message with ID {id}")
        raise InvalidHash
    
    file_size = file_id.file_size

    if range_header:
        from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
        from_bytes = int(from_bytes)
        until_bytes = int(until_bytes) if until_bytes else file_size - 1
    else:
        from_bytes = request.http_range.start or 0
        until_bytes = (request.http_range.stop or file_size) - 1

    if (until_bytes > file_size) or (from_bytes < 0) or (until_bytes < from_bytes):
        return web.Response(
            status=416,
            body="416: Range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    chunk_size = 1024 * 1024
    until_bytes = min(until_bytes, file_size - 1)

    offset = from_bytes - (from_bytes % chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = until_bytes % chunk_size + 1

    req_length = until_bytes - from_bytes + 1
    part_count = math.ceil(until_bytes / chunk_size) - math.floor(offset / chunk_size)
    body = tg_connect.yield_file(
        file_id, index, offset, first_part_cut, last_part_cut, part_count, chunk_size
    )

    mime_type = file_id.mime_type
    file_name = file_id.file_name
    disposition = "attachment"

    if mime_type:
        if not file_name:
            try:
                file_name = f"{secrets.token_hex(2)}.{mime_type.split('/')[1]}"
            except (IndexError, AttributeError):
                file_name = f"{secrets.token_hex(2)}.unknown"
    else:
        if file_name:
            mime_type = mimetypes.guess_type(file_id.file_name)
        else:
            mime_type = "application/octet-stream"
            file_name = f"{secrets.token_hex(2)}.unknown"

    return web.Response(
        status=206 if range_header else 200,
        body=body,
        headers={
            "Content-Type": f"{mime_type}",
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Content-Length": str(req_length),
            "Content-Disposition": f'{disposition}; filename="{file_name}"',
            "Accept-Ranges": "bytes",
        },
    )
