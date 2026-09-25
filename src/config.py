"""Central place for settings. Secrets come from the .env file, never from the code."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Project root = the folder that contains src/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Reads the .env file (if it exists) and puts its values into environment variables
load_dotenv(PROJECT_ROOT / ".env")

# ---- Paths ----
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_FILE = DATA_DIR / "raw_movies.json"
SQL_DIR = PROJECT_ROOT / "sql"
VISUALIZATIONS_DIR = PROJECT_ROOT / "visualizations"

# ---- TMDB API ----
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
REQUEST_TIMEOUT_SECONDS = 10   # give up on a request after 10 seconds
MAX_RETRIES = 3                # how many times to try a failing request
REQUEST_DELAY_SECONDS = 0.05   # small pause between requests (TMDB allows roughly 40-50 per second)

# ---- What movies to collect ----
DEFAULT_MOVIE_COUNT = 500      # the pipeline collects about this many movies
MIN_VOTE_COUNT = 500           # only movies with at least this many votes (ratings are more reliable)

# ---- PostgreSQL ----
DB_SETTINGS = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "movie_analytics"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}


def require_api_key():
    """Stop with a clear message if the TMDB key is missing or still the placeholder."""
    if not TMDB_API_KEY or TMDB_API_KEY == "your_api_key_here":
        raise SystemExit(
            "TMDB_API_KEY is missing. Copy .env.example to .env and paste your key into it."
        )
