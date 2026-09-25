-- =====================================================================
-- views.sql : saved queries that make repeated analysis easier.
-- A view stores a query (not the data). Selecting from it runs the query.
-- CREATE OR REPLACE makes this file safe to run more than once.
-- =====================================================================

-- One row per (movie, genre): the join we need in almost every genre analysis.
CREATE OR REPLACE VIEW movie_genre_analysis AS
SELECT
    m.movie_id,
    m.title,
    EXTRACT(YEAR FROM m.release_date)::INT AS release_year,
    g.genre_id,
    g.genre_name,
    m.popularity,
    m.vote_average,
    m.vote_count,
    m.budget,
    m.revenue
FROM movies m
JOIN movie_genres mg ON mg.movie_id = m.movie_id
JOIN genres g        ON g.genre_id  = mg.genre_id;


-- One row per release year with summary numbers.
CREATE OR REPLACE VIEW yearly_movie_statistics AS
SELECT
    EXTRACT(YEAR FROM release_date)::INT AS release_year,
    COUNT(*)                             AS movie_count,
    ROUND(AVG(vote_average), 2)          AS avg_rating,
    ROUND(AVG(popularity), 2)            AS avg_popularity,
    SUM(revenue)                         AS total_revenue   -- SUM ignores NULLs (unknown revenue)
FROM movies
WHERE release_date IS NOT NULL
GROUP BY EXTRACT(YEAR FROM release_date);


-- The 5 highest-rated movies of every genre (ties broken by number of votes).
CREATE OR REPLACE VIEW top_movies_by_genre AS
WITH ranked AS (
    SELECT
        genre_name,
        title,
        release_year,
        vote_average,
        vote_count,
        ROW_NUMBER() OVER (
            PARTITION BY genre_name
            ORDER BY vote_average DESC, vote_count DESC
        ) AS rank_in_genre
    FROM movie_genre_analysis
    WHERE vote_count >= 500          -- ignore movies with too few votes
)
SELECT genre_name, rank_in_genre, title, release_year, vote_average, vote_count
FROM ranked
WHERE rank_in_genre <= 5;
