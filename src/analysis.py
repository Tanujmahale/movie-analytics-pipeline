"""Reads results from PostgreSQL and saves 4 simple charts.

Run with:  python -m src.analysis
"""

import logging

import matplotlib

matplotlib.use("Agg")  # draw to files only, so it also works without a screen
import matplotlib.pyplot as plt
import pandas as pd

from src import config, database

logger = logging.getLogger(__name__)

# Each query returns the small table needed for one chart.
# ::float turns PostgreSQL's exact NUMERIC type into a normal number that matplotlib understands.
AVG_RATING_BY_GENRE_SQL = """
    SELECT genre_name, ROUND(AVG(vote_average), 2)::float AS avg_rating
    FROM movie_genre_analysis
    GROUP BY genre_name
    ORDER BY avg_rating
"""

MOVIES_PER_YEAR_SQL = """
    SELECT release_year, movie_count
    FROM yearly_movie_statistics
    ORDER BY release_year
"""

TOP_POPULAR_MOVIES_SQL = """
    SELECT title, popularity::float AS popularity
    FROM movies
    ORDER BY popularity DESC
    LIMIT 10
"""

AVG_REVENUE_BY_GENRE_SQL = """
    SELECT genre_name, ROUND(AVG(revenue) / 1000000.0, 1)::float AS avg_revenue_millions
    FROM movie_genre_analysis
    WHERE revenue IS NOT NULL
    GROUP BY genre_name
    ORDER BY avg_revenue_millions
"""


def run_query(connection, sql):
    """Run a SELECT and return the result as a pandas DataFrame."""
    with connection.cursor() as cursor:
        cursor.execute(sql)
        column_names = [column.name for column in cursor.description]
        return pd.DataFrame(cursor.fetchall(), columns=column_names)


def save_chart(figure, file_name):
    path = config.VISUALIZATIONS_DIR / file_name
    config.VISUALIZATIONS_DIR.mkdir(exist_ok=True)
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)
    logger.info("Saved %s", path)


def plot_avg_rating_by_genre(connection):
    df = run_query(connection, AVG_RATING_BY_GENRE_SQL)
    figure, axis = plt.subplots(figsize=(9, 7))
    axis.barh(df["genre_name"], df["avg_rating"], color="steelblue")
    axis.set_title("Average Rating by Genre")
    axis.set_xlabel("Average rating (0-10)")
    save_chart(figure, "avg_rating_by_genre.png")


def plot_movies_per_year(connection):
    df = run_query(connection, MOVIES_PER_YEAR_SQL)
    figure, axis = plt.subplots(figsize=(10, 5))
    axis.bar(df["release_year"], df["movie_count"], color="seagreen")
    axis.set_title("Number of Movies by Release Year")
    axis.set_xlabel("Release year")
    axis.set_ylabel("Number of movies")
    save_chart(figure, "movies_per_year.png")


def plot_top_popular_movies(connection):
    df = run_query(connection, TOP_POPULAR_MOVIES_SQL)
    df = df.iloc[::-1]  # reverse so the most popular movie is drawn at the top
    figure, axis = plt.subplots(figsize=(9, 6))
    axis.barh(df["title"], df["popularity"], color="darkorange")
    axis.set_title("Top 10 Movies by Popularity")
    axis.set_xlabel("TMDB popularity score")
    save_chart(figure, "top_10_popular_movies.png")


def plot_avg_revenue_by_genre(connection):
    df = run_query(connection, AVG_REVENUE_BY_GENRE_SQL)
    figure, axis = plt.subplots(figsize=(9, 7))
    axis.barh(df["genre_name"], df["avg_revenue_millions"], color="firebrick")
    axis.set_title("Average Revenue by Genre (movies with known revenue)")
    axis.set_xlabel("Average revenue (million USD)")
    save_chart(figure, "avg_revenue_by_genre.png")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    connection = database.get_connection()
    try:
        database.create_tables_and_views(connection)  # makes sure the views exist
        plot_avg_rating_by_genre(connection)
        plot_movies_per_year(connection)
        plot_top_popular_movies(connection)
        plot_avg_revenue_by_genre(connection)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
