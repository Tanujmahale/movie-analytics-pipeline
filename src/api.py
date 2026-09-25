"""Talks to the TMDB REST API. Nothing in this file touches the database."""

import json
import logging
import time

import requests

from src import config

logger = logging.getLogger(__name__)

session = requests.Session()  # re-uses the connection, so many requests are faster


class ApiError(Exception):
    """Raised when the API keeps failing or rejects our request."""


def get_json(endpoint, params=None):
    """Send one GET request and return the JSON as a dict.

    - Retries on timeouts, connection problems, HTTP 429 (rate limit) and 5xx (server errors).
    - Returns None for HTTP 404 (for example, a movie that no longer exists).
    - Raises ApiError for anything else (wrong API key, etc.).
    """
    url = config.TMDB_BASE_URL + endpoint
    all_params = dict(params or {})
    all_params["api_key"] = config.TMDB_API_KEY

    for attempt in range(1, config.MAX_RETRIES + 1):
        wait_seconds = 2 ** attempt  # 2, 4, 8 ... (exponential backoff)

        try:
            response = session.get(url, params=all_params, timeout=config.REQUEST_TIMEOUT_SECONDS)
        except (requests.Timeout, requests.ConnectionError) as error:
            logger.warning("Network problem (%s). Attempt %d/%d", error, attempt, config.MAX_RETRIES)
            time.sleep(wait_seconds)
            continue

        if response.status_code == 200:
            time.sleep(config.REQUEST_DELAY_SECONDS)  # stay under the rate limit
            return response.json()

        if response.status_code == 404:
            return None

        if response.status_code == 429:  # too many requests: do what the server asks
            wait_seconds = int(response.headers.get("Retry-After", wait_seconds))
            logger.warning("Rate limited. Waiting %d seconds.", wait_seconds)
            time.sleep(wait_seconds)
            continue

        if response.status_code >= 500:  # the server had a problem, so try again
            logger.warning("Server error %d. Attempt %d/%d", response.status_code, attempt, config.MAX_RETRIES)
            time.sleep(wait_seconds)
            continue

        # 401 (bad key), 400, etc. Retrying will not help.
        raise ApiError(f"TMDB returned {response.status_code} for {endpoint}: {response.text[:200]}")

    raise ApiError(f"Gave up on {endpoint} after {config.MAX_RETRIES} attempts")


def fetch_genres():
    """Return the list of movie genres, e.g. [{"id": 28, "name": "Action"}, ...]."""
    data = get_json("/genre/movie/list", {"language": "en-US"})
    if not data or "genres" not in data:
        raise ApiError("Genre response did not contain 'genres'")
    return data["genres"]


def fetch_movie_ids(target_count):
    """Page through /discover/movie and collect unique movie IDs.

    Each page holds 20 movies, so 500 movies need 25 requests.
    We sort by vote count so the ratings are based on many votes.
    """
    movie_ids = []
    seen_ids = set()  # prevents duplicates (pages can overlap if the data changes mid-run)
    page = 1

    while len(movie_ids) < target_count:
        data = get_json(
            "/discover/movie",
            {
                "sort_by": "vote_count.desc",
                "vote_count.gte": config.MIN_VOTE_COUNT,
                "include_adult": "false",
                "language": "en-US",
                "page": page,
            },
        )
        if not data or "results" not in data:
            raise ApiError(f"Unexpected discover response on page {page}")

        for movie in data["results"]:
            if movie["id"] not in seen_ids:
                seen_ids.add(movie["id"])
                movie_ids.append(movie["id"])

        # TMDB allows at most 500 pages, and total_pages tells us when we ran out
        if page >= min(data.get("total_pages", 1), 500):
            break
        page += 1

    return movie_ids[:target_count]


def fetch_movie_details(movie_id):
    """Return the full record for one movie (this is the only place budget and revenue exist)."""
    return get_json(f"/movie/{movie_id}", {"language": "en-US"})


def fetch_all_movies(target_count):
    """Collect movie IDs, then fetch the details of each one."""
    movie_ids = fetch_movie_ids(target_count)
    logger.info("Found %d movie IDs. Fetching details...", len(movie_ids))

    movies = []
    for number, movie_id in enumerate(movie_ids, start=1):
        details = fetch_movie_details(movie_id)
        if details is not None:
            movies.append(details)
        if number % 50 == 0:
            logger.info("  fetched %d/%d movies", number, len(movie_ids))
    return movies


def save_raw_data(genres, movies, path=config.RAW_DATA_FILE):
    """Save the untouched API data to disk, so we do not have to call the API again."""
    path.parent.mkdir(exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump({"genres": genres, "movies": movies}, file)
    logger.info("Saved raw data to %s", path)


def load_raw_data(path=config.RAW_DATA_FILE):
    """Read the raw data saved earlier. Returns (genres, movies)."""
    with open(path, encoding="utf-8") as file:
        data = json.load(file)
    return data["genres"], data["movies"]
