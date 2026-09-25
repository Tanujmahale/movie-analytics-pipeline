-- =====================================================================
-- analytical_queries.sql : 22 queries, from beginner to intermediate.
--
-- How to run one query: copy it into psql / pgAdmin / DBeaver.
-- How to run them all:  psql -d movie_analytics -f sql/analytical_queries.sql
--
-- Notes:
--  * vote_count >= 500 is used when ranking by rating. A movie with 3 votes
--    and a 10.0 rating is not "the best movie", so we ignore tiny samples.
--  * Change the numbers (year 2010, minimum 30 movies, ...) to explore.
-- =====================================================================


-- =====================  BASIC  =====================

-- 1. Total number of movies in the database.
SELECT COUNT(*) AS total_movies
FROM movies;

-- 2. Average movie rating across all movies.
SELECT ROUND(AVG(vote_average), 2) AS average_rating
FROM movies;

-- 3. Top 10 highest-rated movies (with enough votes to be trusted).
SELECT title, vote_average, vote_count
FROM movies
WHERE vote_count >= 500
ORDER BY vote_average DESC, vote_count DESC
LIMIT 10;

-- 4. Top 10 most popular movies.
SELECT title, popularity
FROM movies
ORDER BY popularity DESC
LIMIT 10;

-- 5. Movies released in one particular year (2010 here).
--    A date range lets PostgreSQL use the index on release_date.
SELECT title, release_date, vote_average
FROM movies
WHERE release_date >= DATE '2010-01-01'
  AND release_date <  DATE '2011-01-01'
ORDER BY release_date;


-- =====================  GROUP BY / HAVING  =====================

-- 6. Average rating by genre (best genre first).
SELECT
    g.genre_name,
    ROUND(AVG(m.vote_average), 2) AS avg_rating
FROM genres g
JOIN movie_genres mg ON mg.genre_id = g.genre_id
JOIN movies m        ON m.movie_id  = mg.movie_id
GROUP BY g.genre_name
ORDER BY avg_rating DESC;

-- 7. Number of movies in each genre.
--    A movie with 3 genres is counted once in each of its 3 genres.
SELECT
    g.genre_name,
    COUNT(*) AS movie_count
FROM genres g
JOIN movie_genres mg ON mg.genre_id = g.genre_id
GROUP BY g.genre_name
ORDER BY movie_count DESC;

-- 8. Average popularity by genre.
SELECT
    g.genre_name,
    ROUND(AVG(m.popularity), 2) AS avg_popularity
FROM genres g
JOIN movie_genres mg ON mg.genre_id = g.genre_id
JOIN movies m        ON m.movie_id  = mg.movie_id
GROUP BY g.genre_name
ORDER BY avg_popularity DESC;

-- 9. Genres with more than 30 movies.
--    WHERE filters rows BEFORE grouping. HAVING filters groups AFTER grouping.
SELECT
    g.genre_name,
    COUNT(*) AS movie_count
FROM genres g
JOIN movie_genres mg ON mg.genre_id = g.genre_id
GROUP BY g.genre_name
HAVING COUNT(*) > 30
ORDER BY movie_count DESC;


-- =====================  JOIN  =====================

-- 10. Every movie with all its genres in one text column.
--     LEFT JOIN keeps movies that have no genre. STRING_AGG glues the genre names together.
SELECT
    m.title,
    STRING_AGG(g.genre_name, ', ' ORDER BY g.genre_name) AS genres
FROM movies m
LEFT JOIN movie_genres mg ON mg.movie_id = m.movie_id
LEFT JOIN genres g        ON g.genre_id  = mg.genre_id
GROUP BY m.movie_id, m.title
ORDER BY m.title;

-- 11. Highest-rated movie in each genre.
--     Step 1 (subquery): find the best rating per genre.
--     Step 2 (join): find the movie(s) that have that rating. Ties show up as several rows.
SELECT
    best.genre_name,
    a.title,
    a.vote_average
FROM (
    SELECT genre_name, MAX(vote_average) AS max_rating
    FROM movie_genre_analysis
    WHERE vote_count >= 500
    GROUP BY genre_name
) AS best
JOIN movie_genre_analysis a
  ON a.genre_name   = best.genre_name
 AND a.vote_average = best.max_rating
WHERE a.vote_count >= 500
ORDER BY best.genre_name;

-- 12. Average revenue by genre (only movies whose revenue is known).
SELECT
    g.genre_name,
    COUNT(*)                     AS movies_with_revenue,
    ROUND(AVG(m.revenue), 0)     AS avg_revenue
FROM genres g
JOIN movie_genres mg ON mg.genre_id = g.genre_id
JOIN movies m        ON m.movie_id  = mg.movie_id
WHERE m.revenue IS NOT NULL
GROUP BY g.genre_name
ORDER BY avg_revenue DESC;


-- =====================  SUBQUERIES / CTEs  =====================

-- 13. Movies rated above the average rating.
--     The subquery in parentheses returns ONE number (the average).
SELECT title, vote_average
FROM movies
WHERE vote_average > (SELECT AVG(vote_average) FROM movies)
ORDER BY vote_average DESC;

-- 14. Movies more popular than the average movie.
SELECT title, popularity
FROM movies
WHERE popularity > (SELECT AVG(popularity) FROM movies)
ORDER BY popularity DESC;

-- 15. Highest-rated movie for each release year.
--     A CTE (WITH ...) is a named temporary result that makes the query easier to read.
WITH best_rating_per_year AS (
    SELECT
        EXTRACT(YEAR FROM release_date)::INT AS release_year,
        MAX(vote_average)                    AS max_rating
    FROM movies
    WHERE release_date IS NOT NULL
      AND vote_count >= 500
    GROUP BY EXTRACT(YEAR FROM release_date)
)
SELECT b.release_year, m.title, m.vote_average
FROM best_rating_per_year b
JOIN movies m
  ON EXTRACT(YEAR FROM m.release_date)::INT = b.release_year
 AND m.vote_average = b.max_rating
WHERE m.vote_count >= 500
ORDER BY b.release_year DESC;

-- 16. Top 5 genres by average rating (only genres with at least 10 movies, so one movie can't decide).
WITH genre_stats AS (
    SELECT
        genre_name,
        COUNT(*)                     AS movie_count,
        ROUND(AVG(vote_average), 2)  AS avg_rating
    FROM movie_genre_analysis
    GROUP BY genre_name
)
SELECT genre_name, movie_count, avg_rating
FROM genre_stats
WHERE movie_count >= 10
ORDER BY avg_rating DESC
LIMIT 5;


-- =====================  WINDOW FUNCTIONS  =====================
-- A window function calculates over a group of rows WITHOUT collapsing them into one row
-- (unlike GROUP BY). PARTITION BY = the groups, ORDER BY = the order inside each group.

-- 17. Rank every movie inside its genre by rating.
--     RANK() gives tied movies the same rank and then skips a number (1, 2, 2, 4).
SELECT
    genre_name,
    title,
    vote_average,
    RANK() OVER (PARTITION BY genre_name ORDER BY vote_average DESC) AS rank_in_genre
FROM movie_genre_analysis
WHERE vote_count >= 500
ORDER BY genre_name, rank_in_genre;

-- 18. Top 5 movies in each genre.
--     You cannot filter on a window function directly in WHERE, so we rank in a CTE first.
--     ROW_NUMBER() never gives ties, so we always get exactly 5 rows per genre.
WITH ranked AS (
    SELECT
        genre_name,
        title,
        vote_average,
        ROW_NUMBER() OVER (
            PARTITION BY genre_name
            ORDER BY vote_average DESC, vote_count DESC
        ) AS row_num
    FROM movie_genre_analysis
    WHERE vote_count >= 500
)
SELECT genre_name, row_num, title, vote_average
FROM ranked
WHERE row_num <= 5
ORDER BY genre_name, row_num;

-- 19. Year-over-year change in the number of movies.
--     LAG() reads the value from the previous row (the previous year).
--     NULLIF(x, 0) turns 0 into NULL so we never divide by zero.
WITH movies_per_year AS (
    SELECT
        EXTRACT(YEAR FROM release_date)::INT AS release_year,
        COUNT(*)                             AS movie_count
    FROM movies
    WHERE release_date IS NOT NULL
    GROUP BY EXTRACT(YEAR FROM release_date)
)
SELECT
    release_year,
    movie_count,
    LAG(movie_count) OVER (ORDER BY release_year)                AS previous_year_count,
    movie_count - LAG(movie_count) OVER (ORDER BY release_year)  AS change,
    ROUND(
        100.0 * (movie_count - LAG(movie_count) OVER (ORDER BY release_year))
        / NULLIF(LAG(movie_count) OVER (ORDER BY release_year), 0), 1
    ) AS change_percent
FROM movies_per_year
ORDER BY release_year;
-- Note: years with no movies at all do not appear, so "previous year" means the previous year that has data.

-- 20. Running average rating by release year (average of ALL movies released up to that year).
--     We keep a running total of ratings and a running count of movies, then divide.
--     (Averaging the yearly averages would be wrong: a year with 2 movies would count as much as a year with 40.)
WITH yearly AS (
    SELECT
        EXTRACT(YEAR FROM release_date)::INT AS release_year,
        SUM(vote_average)                    AS rating_sum,
        COUNT(*)                             AS movie_count
    FROM movies
    WHERE release_date IS NOT NULL
    GROUP BY EXTRACT(YEAR FROM release_date)
)
SELECT
    release_year,
    movie_count,
    ROUND(rating_sum / movie_count, 2) AS avg_rating_this_year,
    ROUND(
        SUM(rating_sum)  OVER (ORDER BY release_year)
      / SUM(movie_count) OVER (ORDER BY release_year), 2
    ) AS running_avg_rating
FROM yearly
ORDER BY release_year;


-- =====================  EXTRA: DATA QUALITY & LANGUAGE  =====================

-- 21. Movies per original language (which languages dominate the data?).
SELECT
    original_language,
    COUNT(*)                    AS movie_count,
    ROUND(AVG(vote_average), 2) AS avg_rating
FROM movies
GROUP BY original_language
ORDER BY movie_count DESC;

-- 22. Data quality check: how many movies are missing a release date, budget or revenue?
--     COUNT(column) skips NULLs, so (total - COUNT(column)) = number of missing values.
SELECT
    COUNT(*)                        AS total_movies,
    COUNT(*) - COUNT(release_date)  AS missing_release_date,
    COUNT(*) - COUNT(budget)        AS missing_budget,
    COUNT(*) - COUNT(revenue)       AS missing_revenue
FROM movies;
