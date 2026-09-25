"""Writes the clean DataFrames into PostgreSQL and checks that the load worked."""

import logging

from psycopg2.extras import execute_values

from src.transform import dataframe_to_records

logger = logging.getLogger(__name__)


def to_rows(df, columns):
    """DataFrame -> list of tuples in the same order as the SQL columns."""
    return [tuple(record[column] for column in columns) for record in dataframe_to_records(df)]


def load_genres(cursor, genres_df):
    # ON CONFLICT ... DO UPDATE = "upsert": insert new rows, update rows that already exist.
    execute_values(
        cursor,
        """
        INSERT INTO genres (genre_id, genre_name)
        VALUES %s
        ON CONFLICT (genre_id) DO UPDATE SET genre_name = EXCLUDED.genre_name
        """,
        to_rows(genres_df, ["genre_id", "genre_name"]),
    )


def load_movies(cursor, movies_df):
    columns = [
        "movie_id", "title", "release_date", "overview", "popularity", "vote_average",
        "vote_count", "original_language", "adult", "budget", "revenue",
    ]
    execute_values(
        cursor,
        """
        INSERT INTO movies (movie_id, title, release_date, overview, popularity, vote_average,
                            vote_count, original_language, adult, budget, revenue)
        VALUES %s
        ON CONFLICT (movie_id) DO UPDATE SET
            title = EXCLUDED.title,
            release_date = EXCLUDED.release_date,
            overview = EXCLUDED.overview,
            popularity = EXCLUDED.popularity,
            vote_average = EXCLUDED.vote_average,
            vote_count = EXCLUDED.vote_count,
            original_language = EXCLUDED.original_language,
            adult = EXCLUDED.adult,
            budget = EXCLUDED.budget,
            revenue = EXCLUDED.revenue
        """,
        to_rows(movies_df, columns),
    )


def load_movie_genres(cursor, movies_df, movie_genres_df):
    # Remove the old genre links of these movies first, so genres removed by TMDB disappear too.
    cursor.execute(
        "DELETE FROM movie_genres WHERE movie_id = ANY(%s)",
        (movies_df["movie_id"].tolist(),),
    )
    execute_values(
        cursor,
        "INSERT INTO movie_genres (movie_id, genre_id) VALUES %s ON CONFLICT DO NOTHING",
        to_rows(movie_genres_df, ["movie_id", "genre_id"]),
    )


def load_all(connection, genres_df, movies_df, movie_genres_df):
    """Load everything in ONE transaction: either all of it is saved, or none of it."""
    try:
        with connection.cursor() as cursor:
            load_genres(cursor, genres_df)              # 1. genres first (parent table)
            load_movies(cursor, movies_df)              # 2. movies (parent table)
            load_movie_genres(cursor, movies_df, movie_genres_df)  # 3. link table last
        connection.commit()
    except Exception:
        connection.rollback()  # undo everything if anything failed
        raise
    logger.info(
        "Loaded %d genres, %d movies, %d movie-genre links",
        len(genres_df), len(movies_df), len(movie_genres_df),
    )


def verify_load(connection, expected_movies):
    """Count the rows in the database and make sure the movies really arrived."""
    with connection.cursor() as cursor:
        counts = {}
        for table in ["movies", "genres", "movie_genres"]:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")  # table names are fixed above, not user input
            counts[table] = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*) FROM movies m
            WHERE NOT EXISTS (SELECT 1 FROM movie_genres mg WHERE mg.movie_id = m.movie_id)
            """
        )
        counts["movies_without_genre"] = cursor.fetchone()[0]

    for name, value in counts.items():
        logger.info("  %-22s %d", name, value)

    if counts["movies"] < expected_movies:
        raise RuntimeError(
            f"Expected at least {expected_movies} movies in the database but found {counts['movies']}"
        )
    return counts
