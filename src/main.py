"""Entry point. Run with:  python -m src.main

Pipeline order:  Fetch -> Transform -> Load -> Verify
"""

import argparse
import logging

from src import api, config, database, load, transform

logger = logging.getLogger("pipeline")


def get_raw_data(movie_count, refresh):
    """Step 1 - FETCH. Reuse the saved JSON file if it exists, so we do not repeat API calls."""
    if config.RAW_DATA_FILE.exists() and not refresh:
        logger.info("Using saved raw data (%s). Use --refresh to download again.", config.RAW_DATA_FILE.name)
        return api.load_raw_data()

    config.require_api_key()
    logger.info("Downloading data from TMDB...")
    genres = api.fetch_genres()
    movies = api.fetch_all_movies(movie_count)
    api.save_raw_data(genres, movies)
    return genres, movies


def run_pipeline(movie_count, refresh):
    logger.info("STEP 1/4  Fetch")
    raw_genres, raw_movies = get_raw_data(movie_count, refresh)
    logger.info("Raw data: %d movies, %d genres", len(raw_movies), len(raw_genres))

    logger.info("STEP 2/4  Transform")
    genres_df, movies_df, movie_genres_df = transform.transform_movies(raw_movies, raw_genres)
    logger.info("Clean data: %d movies (removed %d)", len(movies_df), len(raw_movies) - len(movies_df))

    logger.info("STEP 3/4  Load")
    connection = database.get_connection()
    try:
        database.create_tables_and_views(connection)  # safe to repeat: does nothing if they exist
        load.load_all(connection, genres_df, movies_df, movie_genres_df)

        logger.info("STEP 4/4  Verify")
        load.verify_load(connection, expected_movies=len(movies_df))
    finally:
        connection.close()

    logger.info("Done. Next: python -m src.analysis")


def main():
    parser = argparse.ArgumentParser(description="Movie analytics pipeline: TMDB -> PostgreSQL")
    parser.add_argument("--movies", type=int, default=config.DEFAULT_MOVIE_COUNT,
                        help="how many movies to download (default: %(default)s)")
    parser.add_argument("--refresh", action="store_true",
                        help="download from the API again even if data/raw_movies.json exists")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    run_pipeline(args.movies, args.refresh)


if __name__ == "__main__":
    main()
