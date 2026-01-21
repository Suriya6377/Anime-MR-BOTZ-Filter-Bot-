import re
import asyncio
import aiohttp
import warnings
import logging
from io import BytesIO
from PIL import Image, ImageFilter
from info import DEENDAYAL_IMAGE_FETCH, TMDB_API_KEY
from imdb import Cinemagoer


logger = logging.getLogger(__name__)
ia = Cinemagoer()
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

async def get_movie_details(query, id=False, file=None):
    try:
        if not id:
            query = query.strip().lower()
            title = query
            year = re.findall(r'[1-2]\d{3}$', query, re.IGNORECASE)
            if year:
                year = list_to_str(year[:1])
                title = query.replace(year, "").strip()
            elif file is not None:
                year = re.findall(r'[1-2]\d{3}', file, re.IGNORECASE)
                if year:
                    year = list_to_str(year[:1])
            else:
                year = None
            movieid = ia.search_movie(title.lower(), results=10)
            if not movieid:
                return None
            if year:
                filtered = list(filter(lambda k: str(k.get('year')) == str(year), movieid))
                if not filtered:
                    filtered = movieid
            else:
                filtered = movieid
            movieid = list(filter(lambda k: k.get('kind') in ['movie', 'tv series'], filtered))
            if not movieid:
                movieid = filtered
            movieid = movieid[0].movieID
        else:
            movieid = query
        movie = ia.get_movie(movieid)
        ia.update(movie, info=['main', 'vote details'])

        if movie.get("original air date"):
            date = movie["original air date"]
        elif movie.get("year"):
            date = movie.get("year")
        else:
            date = "N/A"
        plot = movie.get('plot')
        if plot and len(plot) > 0:
            plot = plot[0]
        else:
            plot = movie.get('plot outline')
        if plot and len(plot) > 800:
            plot = plot[:800] + "..."
        poster_url = movie.get('full-size cover url')
        return {
            'title': movie.get('title'),
            'backdrop_url': poster_url, # Fallback to poster if real backdrop not available via this method, as user requested fallback behavior
            'votes': movie.get('votes'),
            "aka": list_to_str(movie.get("akas")),
            "seasons": movie.get("number of seasons"),
            "box_office": movie.get('box office'),
            'localized_title': movie.get('localized title'),
            'kind': movie.get("kind"),
            "imdb_id": f"tt{movie.get('imdbID')}",
            "cast": list_to_str(movie.get("cast")),
            "runtime": list_to_str(movie.get("runtimes")),
            "countries": list_to_str(movie.get("countries")),
            "certificates": list_to_str(movie.get("certificates")),
            "languages": list_to_str(movie.get("languages")),
            "director": list_to_str(movie.get("director")),
            "writer": list_to_str(movie.get("writer")),
            "producer": list_to_str(movie.get("producer")),
            "composer": list_to_str(movie.get("composer")),
            "cinematographer": list_to_str(movie.get("cinematographer")),
            "music_team": list_to_str(movie.get("music department")),
            "distributors": list_to_str(movie.get("distributors")),
            'release_date': date,
            'year': movie.get('year'),
            'genres': list_to_str(movie.get("genres")),
            'poster_url': poster_url,
            'plot': plot,
            'rating': str(movie.get("rating", "N/A")),
            'url': f'https://www.imdb.com/title/tt{movieid}'
        }
    except Exception as e:
        logger.error(f"An error occurred in get_movie_details: {e}")
        return None

async def get_movie_detailsx(query, id=False, file=None):
    base_url = "https://bharath-boy-api.vercel.app/api/movie-posters"
    q = str(query).strip()
    try:
        async with aiohttp.ClientSession() as session:
            params = {"query": q, "api_key": TMDB_API_KEY}
            async with session.get(base_url, params=params) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"API request failed [{resp.status}] for query={q}\n {text}")
                    return await resp.json()

                data = await resp.json()
    except Exception as e:
        logger.error(f"An error occurred in get_movie_detailsx: {e}")
        return None

    # Normalize fields
    details = {}
    details['title'] = data.get('title') or data.get('localized_title')
    details['year'] = (data.get('year', 0)) if data.get('year') else None
    details['release_date'] = data.get('release_date')
    details['rating'] = round(float(data.get('rating', 0)), 1) if data.get('rating') is not None else None
    details['votes'] = int(data.get('votes', 0))
    details['runtime'] = data.get('runtime')
    details['certificates'] = data.get('certificates')
    details['tmdb_url'] = data.get('url')

    for key in ('genres', 'languages', 'countries'):
        raw = data.get(key)
        details[key] = [s.strip() for s in raw.split(',')] if raw else []
    for role in ('director', 'writer', 'producer', 'composer', 'cinematographer', 'cast'):
        raw = data.get(role)
        details[role] = [s.strip() for s in raw.split(',')] if raw else []

    details['plot'] = data.get('plot')
    details['tagline'] = data.get('tagline')
    details['box_office'] = (data.get('box_office', 0)) if data.get('box_office') else None
    raw_dist = data.get('distributors')
    details['distributors'] = [d.strip() for d in raw_dist.split(',')] if raw_dist else []
    details['imdb_id'] = data.get('imdb_id')
    details['tmdb_id'] = data.get('tmdb_id')

    posters = data.get('images', {}).get('posters', {})
    original_language = data.get('images', {}).get('original_language')
    poster_url = data.get('poster_url')
    if not poster_url:
        for key in ('en', original_language, 'xx'):
            if key and posters.get(key):
                poster_url = posters[key][0]
                break
    details['poster_url'] = poster_url

    backdrops = data.get('images', {}).get('backdrops', {})
    original_language = data.get('images', {}).get('original_language')
    backdrop_url = None
    for key in ('en', original_language, 'xx'):
        if key and backdrops.get(key):
            backdrop_url = backdrops[key][0]
            break
    details['backdrop_url'] = backdrop_url

    details['all_posters'] = posters.get('all', [])
    details['all_backdrops'] = backdrops.get('all', [])
    details['raw_posters'] = posters
    details['raw_backdrops'] = backdrops

    return details
