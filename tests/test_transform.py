"""Beginner-friendly tests for src/transform.py. Run with:  pytest"""

import pandas as pd

from src.transform import (
    build_genres_table,
    build_movie_genres_table,
    clean_movies,
    dataframe_to_records,
    flatten_movie,
    is_valid_movie,
    transform_movies,
)


def make_movie(**changes):
    """Helper: a normal movie as the TMDB details endpoint returns it. Override any field."""
    movie = {
        "id": 1,
        "title": "Test Movie",
        "release_date": "2010-07-16",
        "overview": "A test.",
        "popularity": 12.5,
        "vote_average": 8.1,
        "vote_count": 1000,
        "original_language": "en",
        "adult": False,
        "budget": 1000000,
        "revenue": 5000000,
        "genres": [{"id": 28, "name": "Action"}, {"id": 18, "name": "Drama"}],
    }
    movie.update(changes)
    return movie


GENRES = [{"id": 28, "name": "Action"}, {"id": 18, "name": "Drama"}]


def clean(*movies):
    """Helper: raw movies -> cleaned DataFrame."""
    return clean_movies(pd.DataFrame([flatten_movie(movie) for movie in movies]))


# ---------- validation ----------
def test_movie_without_title_is_invalid():
    assert not is_valid_movie(make_movie(title="   "))
    assert not is_valid_movie(make_movie(id=None))
    assert is_valid_movie(make_movie())


# ---------- duplicates ----------
def test_duplicate_movies_are_removed():
    df = clean(make_movie(id=1), make_movie(id=1), make_movie(id=2, title="Other"))
    assert len(df) == 2
    assert sorted(df["movie_id"]) == [1, 2]


# ---------- missing values ----------
def test_missing_values_are_handled():
    df = clean(make_movie(overview="", popularity=None, vote_average=None, original_language=None))
    row = df.iloc[0]
    assert pd.isna(row["overview"])            # empty text -> missing (NULL)
    assert row["popularity"] == 0              # unknown number -> 0
    assert row["vote_average"] == 0
    assert row["original_language"] == "unknown"


def test_zero_budget_and_revenue_become_missing():
    df = clean(make_movie(budget=0, revenue=0))
    assert pd.isna(df.iloc[0]["budget"])
    assert pd.isna(df.iloc[0]["revenue"])


# ---------- dates ----------
def test_date_is_converted_to_datetime():
    df = clean(make_movie(release_date="2010-07-16"))
    assert df.iloc[0]["release_date"] == pd.Timestamp("2010-07-16")


def test_bad_or_empty_dates_become_missing():
    df = clean(make_movie(id=1, release_date=""), make_movie(id=2, release_date="not a date"))
    assert df["release_date"].isna().all()


# ---------- numbers ----------
def test_text_numbers_are_converted():
    df = clean(make_movie(popularity="15.5", vote_count="200", budget="3000000"))
    row = df.iloc[0]
    assert row["popularity"] == 15.5
    assert row["vote_count"] == 200
    assert row["budget"] == 3000000


# ---------- genres ----------
def test_genres_table_has_no_duplicates():
    raw_genres = GENRES + [{"id": 28, "name": "Action"}]
    genres_df = build_genres_table(raw_genres)
    assert list(genres_df.columns) == ["genre_id", "genre_name"]
    assert len(genres_df) == 2


def test_genres_are_normalized_to_one_row_per_pair():
    df = clean(make_movie(id=1), make_movie(id=2, title="Two", genres=[{"id": 18, "name": "Drama"}]))
    links = build_movie_genres_table(df, valid_genre_ids={28, 18})
    pairs = set(zip(links["movie_id"], links["genre_id"]))
    assert pairs == {(1, 28), (1, 18), (2, 18)}


def test_unknown_genre_ids_are_skipped():
    df = clean(make_movie(genres=[{"id": 999, "name": "Mystery Genre"}]))
    links = build_movie_genres_table(df, valid_genre_ids={28, 18})
    assert links.empty


# ---------- full transform + database-ready records ----------
def test_transform_movies_end_to_end():
    raw_movies = [make_movie(id=1), make_movie(id=1), make_movie(id=2, title=""), make_movie(id=3, title="Three")]
    genres_df, movies_df, links_df = transform_movies(raw_movies, GENRES)
    assert sorted(movies_df["movie_id"]) == [1, 3]   # duplicate and untitled movie are gone
    assert "genre_ids" not in movies_df.columns
    assert len(genres_df) == 2
    assert len(links_df) == 4                        # 2 movies x 2 genres


def test_records_use_none_for_missing_values():
    df = clean(make_movie(budget=0, release_date=""))
    record = dataframe_to_records(df)[0]
    assert record["budget"] is None
    assert record["release_date"] is None
    assert record["title"] == "Test Movie"
