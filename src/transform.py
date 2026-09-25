"""Cleans raw TMDB JSON and turns it into tidy pandas DataFrames.

This file never calls the API and never touches the database, so it is easy to test.
"""

import pandas as pd

MOVIE_COLUMNS = [
    "movie_id", "title", "release_date", "overview", "popularity", "vote_average",
    "vote_count", "original_language", "adult", "budget", "revenue",
]


def is_valid_movie(raw_movie):
    """A movie is usable only if it has an ID and a non-empty title."""
    if not isinstance(raw_movie, dict):
        return False
    title = str(raw_movie.get("title") or "").strip()
    return raw_movie.get("id") is not None and title != ""


def flatten_movie(raw_movie):
    """Turn one nested API movie into a flat dictionary (one future table row)."""
    # The details endpoint sends "genres": [{"id": 28, "name": "Action"}]
    # The list endpoint sends "genre_ids": [28]. We accept both.
    genre_ids = [genre["id"] for genre in raw_movie.get("genres") or [] if "id" in genre]
    if not genre_ids:
        genre_ids = raw_movie.get("genre_ids") or []

    return {
        "movie_id": raw_movie.get("id"),
        "title": raw_movie.get("title"),
        "release_date": raw_movie.get("release_date"),
        "overview": raw_movie.get("overview"),
        "popularity": raw_movie.get("popularity"),
        "vote_average": raw_movie.get("vote_average"),
        "vote_count": raw_movie.get("vote_count"),
        "original_language": raw_movie.get("original_language"),
        "adult": raw_movie.get("adult"),
        "budget": raw_movie.get("budget"),
        "revenue": raw_movie.get("revenue"),
        "genre_ids": genre_ids,
    }


def clean_movies(movies_df):
    """Fix types, fill or blank out missing values, and remove duplicate movies."""
    df = movies_df.copy()

    # IDs must be numbers. Rows without a usable ID are useless, so drop them.
    df["movie_id"] = pd.to_numeric(df["movie_id"], errors="coerce")
    df = df.dropna(subset=["movie_id"])
    df["movie_id"] = df["movie_id"].astype(int)

    # Titles: trim spaces, and drop movies that have no title at all.
    df["title"] = df["title"].fillna("").astype(str).str.strip()
    df = df[df["title"] != ""]

    # Duplicates: keep the first row for every movie_id.
    df = df.drop_duplicates(subset="movie_id", keep="first")

    # Dates: text -> datetime. Bad or empty dates become NaT (missing), not an error.
    df["release_date"] = pd.to_datetime(df["release_date"], errors="coerce")

    # Numbers: text -> numbers. Unknown popularity/rating/votes become 0.
    for column in ["popularity", "vote_average"]:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)
    df["vote_count"] = pd.to_numeric(df["vote_count"], errors="coerce").fillna(0).astype(int)

    # TMDB uses 0 when budget/revenue is unknown. A real 0 would ruin averages,
    # so we turn 0 into "missing" (NULL in the database).
    for column in ["budget", "revenue"]:
        values = pd.to_numeric(df[column], errors="coerce")
        df[column] = values.where(values > 0).astype("Int64")

    # Text and boolean columns
    overview = df["overview"].fillna("").astype(str).str.strip()
    df["overview"] = overview.where(overview != "", None)
    language = df["original_language"].fillna("").astype(str).str.strip()
    df["original_language"] = language.where(language != "", "unknown")
    df["adult"] = df["adult"].fillna(False).astype(bool)

    return df.reset_index(drop=True)


def build_genres_table(raw_genres):
    """Genre list from the API -> DataFrame with genre_id and genre_name (no duplicates)."""
    df = pd.DataFrame(raw_genres).rename(columns={"id": "genre_id", "name": "genre_name"})
    return df[["genre_id", "genre_name"]].drop_duplicates(subset="genre_id").reset_index(drop=True)


def build_movie_genres_table(movies_df, valid_genre_ids):
    """Normalize genres: one row per (movie, genre) pair instead of a list inside a column."""
    links = movies_df[["movie_id", "genre_ids"]].explode("genre_ids")  # one row per genre
    links = links.dropna(subset=["genre_ids"])
    links = links.rename(columns={"genre_ids": "genre_id"})
    links["genre_id"] = links["genre_id"].astype(int)
    links = links[links["genre_id"].isin(valid_genre_ids)]  # skip genres that are not in the genres table
    return links.drop_duplicates().reset_index(drop=True)


def transform_movies(raw_movies, raw_genres):
    """Main function of this file. Returns (genres_df, movies_df, movie_genres_df)."""
    valid_movies = [movie for movie in raw_movies if is_valid_movie(movie)]

    flat_rows = [flatten_movie(movie) for movie in valid_movies]
    movies_df = clean_movies(pd.DataFrame(flat_rows, columns=MOVIE_COLUMNS + ["genre_ids"]))

    genres_df = build_genres_table(raw_genres)
    movie_genres_df = build_movie_genres_table(movies_df, set(genres_df["genre_id"]))

    return genres_df, movies_df[MOVIE_COLUMNS], movie_genres_df


def dataframe_to_records(df):
    """DataFrame -> list of dicts that psycopg2 can insert (missing values become None)."""
    df = df.copy()
    for column in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[column]):
            df[column] = df[column].dt.date  # datetime -> plain date (NaT stays missing)
    df = df.astype(object).where(df.notna(), None)  # NaN / NaT / <NA>  ->  None (SQL NULL)
    return df.to_dict("records")
