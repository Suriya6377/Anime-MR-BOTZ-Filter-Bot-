import re
import asyncio
import aiohttp
import warnings
import logging
from io import BytesIO
from PIL import Image, ImageFilter
from info import DEENDAYAL_IMAGE_FETCH, TMDB_API_KEY
from imdbkit import IMDBKit
from utils import listx_to_str

logger = logging.getLogger(__name__)
ia = IMDBKit()
LONG_IMDB_DESCRIPTION = False

def list_to_str(lst):
    if lst:
        return ", ".join(map(str, lst))
    return ""

Image.MAX_IMAGE_PIXELS = None
warnings.simplefilter("ignore", Image.DecompressionBombWarning)

def process_image(data, size):
    img = Image.open(BytesIO(data))

    target_width, target_height = size
    target_ratio = target_width / target_height

    img_width, img_height = img.size
    img_ratio = img_width / img_height

    if abs(target_ratio - img_ratio) < 0.1:
        img = img.resize(size, Image.LANCZOS)
    else:
        # Create blurred background
        # Scale to cover
        scale_w = target_width / img_width
        scale_h = target_height / img_height
        scale = max(scale_w, scale_h)

        bg_width = int(img_width * scale)
        bg_height = int(img_height * scale)

        bg_img = img.resize((bg_width, bg_height), Image.LANCZOS)

        # Crop to center
        left = (bg_width - target_width) // 2
        top = (bg_height - target_height) // 2
        bg_img = bg_img.crop((left, top, left + target_width, top + target_height))

        bg_img = bg_img.filter(ImageFilter.GaussianBlur(radius=20))

        # Create foreground
        # Scale to fit
        scale_w = target_width / img_width
        scale_h = target_height / img_height
        scale = min(scale_w, scale_h)

        fg_width = int(img_width * scale)
        fg_height = int(img_height * scale)

        fg_img = img.resize((fg_width, fg_height), Image.LANCZOS)

        # Paste centered
        x = (target_width - fg_width) // 2
        y = (target_height - fg_height) // 2

        bg_img.paste(fg_img, (x, y))
        img = bg_img

    out = BytesIO()
    img.save(out, format="JPEG")
    out.seek(0)
    return out

async def fetch_image(url, size=(860, 1200)):
    if not DEENDAYAL_IMAGE_FETCH:
        logger.info("Image fetching is disabled.")
        return None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch image: {response.status}")
                    return None

                data = await response.read()
                return await asyncio.get_running_loop().run_in_executor(None, process_image, data, size)

    except aiohttp.ClientError as e:
        logger.error(f"HTTP request error in fetch_image: {e}")
    except IOError as e:
        logger.error(f"I/O error in fetch_image: {e}")
    except Exception as e:
        logger.error(f"Unexpected error in fetch_image: {e}")

    return None

async def get_movie_details(query, bulk=False, id=False, file=None):
    try:
        if not id:
            query = (query.strip()).lower()
            title = query
            year_val = None
            
            year_list = re.findall(r'[1-2]\d{3}$', query, re.IGNORECASE)
            if year_list:
                year_val = year_list[0]
                title = (query.replace(year_val, "")).strip()
            elif file is not None:
                year_list = re.findall(r'[1-2]\d{3}', file, re.IGNORECASE)
                if year_list:
                    year_val = year_list[0]
            
            search_result = await asyncio.to_thread(ia.search_movie, title.lower())
            if not search_result or not search_result.titles:
                return None
            
            movie_list = search_result.titles
            
            if year_val:
                filtered = [m for m in movie_list if m.year and str(m.year) == str(year_val)]
                if not filtered:
                    filtered = movie_list
            else:
                filtered = movie_list
                
            kind_filter = ['movie', 'tv series', 'tvSeries', 'tvMiniSeries', 'tvMovie']
            filtered_kind = [m for m in filtered if m.kind and m.kind in kind_filter]
            
            if not filtered_kind:
                filtered_kind = filtered
            
            if bulk:
                return filtered_kind
                
            movie_brief = filtered_kind[0]
            movieid_str = movie_brief.imdb_id 
        else:
            movieid_str = query

        movie = await asyncio.to_thread(ia.get_movie, movieid_str)
        if not movie:
            return None

        if movie.release_date:
            date = movie.release_date
        elif movie.year:
            date = str(movie.year)
        else:
            date = "N/A"
            
        plot = movie.plot or ""
        if plot and len(plot) > 800:
            plot = plot[0:800] + "..."
            
        return {
            'title': movie.title,
            'votes': movie.votes,
            "aka": listx_to_str(movie.title_akas),
            "seasons": (
                len(movie.info_series.display_seasons)
                if getattr(movie, "info_series", None)
                and getattr(movie.info_series, "display_seasons", None)
                else "N/A"
            ),
            "box_office": movie.worldwide_gross,
            'localized_title': movie.title_localized,
            'kind': movie.kind,
            "imdb_id": f"tt{movie.imdb_id}",
            "cast": listx_to_str(movie.stars),
            "runtime": listx_to_str(movie.duration),
            "countries": listx_to_str(movie.countries),
            "certificates": listx_to_str(movie.certificates),
            "languages": listx_to_str(movie.languages),
            "director": listx_to_str(movie.directors),
            "writer": listx_to_str([p.name for p in (movie.writers or [])]),
            "producer": listx_to_str([p.name for p in (movie.producers or [])]),
            "composer": listx_to_str([p.name for p in (movie.composers or [])]),
            "cinematographer": listx_to_str([p.name for p in (movie.cinematographers or [])]),
            "music_team": listx_to_str([p.name for p in (movie.music_team or [])]),
            "distributors": listx_to_str([c.name for c in (movie.distributors or [])]),
            'release_date': date,
            'year': movie.year,
            'genres': listx_to_str(movie.genres),
            'poster': movie.cover_url,
            'plot': plot,
            'rating': str(movie.rating),
            'url': movie.url or f'https://www.imdb.com/title/tt{movie.imdb_id}'
        }

    except Exception as e:
        print(f"[get_movie_details] Error fetching poster for query='{query}': {e}")
        return None


async def get_movie_detailsx(query, id=False, file=None):
    q = str(query).strip()
    try:
        async with aiohttp.ClientSession() as session:
            # Step 1: Search for the movie
            search_url = "https://api.themoviedb.org/3/search/multi"
            params = {"query": q, "api_key": TMDB_API_KEY}
            async with session.get(search_url, params=params) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"TMDB Search API request failed [{resp.status}] for query={q}\n {text}")
                    return {"error": True}
                data = await resp.json()

            results = data.get("results", [])
            if not results:
                return {"error": True}

            first_result = results[0]
            tmdb_id = first_result.get("id")
            media_type = first_result.get("media_type", "movie")

            # Step 2: Get movie/tv details including images
            details_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
            params = {"api_key": TMDB_API_KEY, "append_to_response": "images"}
            async with session.get(details_url, params=params) as resp:
                if resp.status != 200:
                    return {"error": True}
                details_data = await resp.json()

    except Exception as e:
        logger.error(f"An error occurred in get_movie_detailsx: {e}")
        return {"error": True}

    # Normalize fields
    details = {}
    details['title'] = details_data.get('title') or details_data.get('name') or details_data.get('original_name')

    release_date = details_data.get('release_date') or details_data.get('first_air_date')
    details['release_date'] = release_date
    details['year'] = int(release_date.split('-')[0]) if release_date else None

    rating = details_data.get('vote_average')
    details['rating'] = round(float(rating), 1) if rating else None
    details['votes'] = details_data.get('vote_count', 0)

    runtime = details_data.get('runtime')
    if not runtime and details_data.get('episode_run_time'):
        runtime = details_data.get('episode_run_time')[0] if details_data.get('episode_run_time') else None
    details['runtime'] = f"{runtime} min" if runtime else None

    details['tmdb_url'] = f"https://www.themoviedb.org/{media_type}/{tmdb_id}"

    genres = details_data.get('genres', [])
    details['genres'] = [g.get('name') for g in genres] if genres else []

    details['plot'] = details_data.get('overview')
    details['tmdb_id'] = tmdb_id

    # Images
    poster_path = details_data.get('poster_path')

    if poster_path:
        details['poster_url'] = f"https://image.tmdb.org/t/p/w500{poster_path}"
    else:
        details['poster_url'] = None

    # Backdrop Language Priority Logic
    # 1. Preferred Languages (hi, en, original_language)
    # 2. No language (clean backdrops, iso_639_1 == None)
    # 3. Any language
    # 4. Default backdrop_path
    backdrop_path = None
    images = details_data.get('images', {})
    backdrops = images.get('backdrops', [])

    if backdrops:
        # Sort by vote_average to get the best ones first
        sorted_backdrops = sorted(backdrops, key=lambda x: x.get('vote_average', 0), reverse=True)
        original_language = details_data.get('original_language')

        # Priority 1: Preferred Languages
        preferred_langs = ['en', 'hi', original_language]
        for lang in preferred_langs:
            if backdrop_path: break
            for bd in sorted_backdrops:
                if bd.get('iso_639_1') == lang:
                    backdrop_path = bd.get('file_path')
                    break

        # Priority 2: Any language
        if not backdrop_path:
            for bd in sorted_backdrops:
                if bd.get('iso_639_1') is not None and bd.get('iso_639_1') != 'xx':
                    backdrop_path = bd.get('file_path')
                    break

        # Priority 3: No language
        if not backdrop_path:
            for bd in sorted_backdrops:
                if bd.get('iso_639_1') is None or bd.get('iso_639_1') == 'xx':
                    backdrop_path = bd.get('file_path')
                    break

    # Priority 4: Fallback to the default if our search yielded nothing
    if not backdrop_path:
        backdrop_path = details_data.get('backdrop_path')

    if backdrop_path:
        details['backdrop_url'] = f"https://image.tmdb.org/t/p/w1280{backdrop_path}"
    else:
        details['backdrop_url'] = None

    return details
