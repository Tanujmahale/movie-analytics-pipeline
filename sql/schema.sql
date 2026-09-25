-- =====================================================================
-- schema.sql : database design for the movie analytics project
--
-- Three tables:
--   movies        one row per movie
--   genres        one row per genre (Action, Drama, ...)
--   movie_genres  link table: a movie can have many genres, a genre can have many movies
--
-- Safe to run more than once (IF NOT EXISTS).
-- =====================================================================

-- ---------- genres ----------
CREATE TABLE IF NOT EXISTS genres (
    genre_id    INTEGER      PRIMARY KEY,        -- the ID that TMDB uses
    genre_name  VARCHAR(100) NOT NULL UNIQUE     -- two genres can not have the same name
);

-- ---------- movies ----------
CREATE TABLE IF NOT EXISTS movies (
    movie_id           INTEGER       PRIMARY KEY,                -- the ID that TMDB uses
    title              VARCHAR(500)  NOT NULL,
    release_date       DATE,                                     -- NULL allowed: some movies have no date
    overview           TEXT,                                     -- NULL allowed: some movies have no summary
    popularity         NUMERIC(10,3) NOT NULL DEFAULT 0,         -- NUMERIC = exact decimals (FLOAT can be inexact)
    vote_average       NUMERIC(4,3)  NOT NULL DEFAULT 0
                       CHECK (vote_average BETWEEN 0 AND 10),    -- ratings are 0 to 10
    vote_count         INTEGER       NOT NULL DEFAULT 0
                       CHECK (vote_count >= 0),
    original_language  VARCHAR(10)   NOT NULL DEFAULT 'unknown',
    adult              BOOLEAN       NOT NULL DEFAULT FALSE,
    budget             BIGINT,                                   -- NULL = unknown (BIGINT: budgets can pass 2 billion)
    revenue            BIGINT                                    -- NULL = unknown
);

-- ---------- movie_genres (many-to-many link table) ----------
CREATE TABLE IF NOT EXISTS movie_genres (
    movie_id  INTEGER NOT NULL REFERENCES movies (movie_id) ON DELETE CASCADE,  -- delete a movie -> its links go too
    genre_id  INTEGER NOT NULL REFERENCES genres (genre_id),
    PRIMARY KEY (movie_id, genre_id)   -- the same genre can not be attached to the same movie twice
);

-- ---------- indexes ----------
-- The primary keys already have indexes. These extra ones speed up common filters and sorts.
CREATE INDEX IF NOT EXISTS idx_movies_release_date  ON movies (release_date);    -- "movies in year X"
CREATE INDEX IF NOT EXISTS idx_movies_vote_average  ON movies (vote_average);    -- "highest rated"
CREATE INDEX IF NOT EXISTS idx_movies_popularity    ON movies (popularity);      -- "most popular"
CREATE INDEX IF NOT EXISTS idx_movie_genres_genre   ON movie_genres (genre_id);  -- "all movies of genre X"
-- (movie_genres by movie_id is already covered by the primary key (movie_id, genre_id))
