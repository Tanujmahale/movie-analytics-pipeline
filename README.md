# Movie Analytics Data Pipeline

A small end-to-end data engineering / analytics project:

**Public REST API → Python → Data Cleaning → PostgreSQL → Analytical SQL → Charts**

It downloads about 500 movies from the [TMDB API](https://developer.themoviedb.org/docs), cleans them with pandas, stores them in a normalized PostgreSQL database, answers questions with 22 SQL queries, and draws four charts with matplotlib.

---

## Architecture

```text
TMDB API
   ↓   src/api.py         (requests, pagination, retries, rate-limit handling)
Raw JSON  (data/raw_movies.json, saved so the API is not called twice)
   ↓   src/transform.py   (pandas: types, missing values, duplicates, genres)
Clean DataFrames
   ↓   src/load.py        (psycopg2: upsert in one transaction)
PostgreSQL  (sql/schema.sql, sql/views.sql)
   ↓
SQL Analytics  (sql/analytical_queries.sql)
   ↓   src/analysis.py
Matplotlib charts  (visualizations/)
```

`src/main.py` runs **Fetch → Transform → Load → Verify** with one command.

## Features

- Pagination, timeouts, retries with backoff, HTTP 429 (rate limit) handling
- Duplicate prevention (when collecting IDs, in pandas, and in the database via primary keys)
- Raw JSON cache: re-running the pipeline does not call the API again unless you ask (`--refresh`)
- Cleaning of dates, numbers, missing values and duplicate movies
- Normalized schema (3 tables) with primary keys, foreign keys, CHECK constraints and indexes
- Idempotent load: run it as many times as you like, with no duplicate rows
- All-or-nothing load using one database transaction
- 22 commented SQL queries, 3 views, 4 charts, 12 unit tests

## Tech Stack

| Tool | Why it is used |
|---|---|
| Python 3 | Glue language for the whole pipeline |
| requests | Calls the REST API |
| pandas | Cleans and reshapes the data |
| PostgreSQL | Stores the data and runs the analysis |
| psycopg2-binary | Lets Python talk to PostgreSQL |
| matplotlib | Draws the charts |
| python-dotenv | Reads secrets (API key, password) from `.env` |
| pytest | Tests the transformation code |

## Project Structure

```text
movie-analytics-pipeline/
├── data/                    raw JSON is saved here (ignored by git)
├── sql/
│   ├── schema.sql           tables, keys, indexes
│   ├── analytical_queries.sql   22 analysis queries
│   └── views.sql            3 reusable views
├── src/
│   ├── config.py            settings + paths, reads .env
│   ├── api.py               talks to TMDB
│   ├── transform.py         cleaning (no API, no database)
│   ├── database.py          connection + run .sql files
│   ├── load.py              inserts data + verification
│   ├── analysis.py          SQL results -> charts
│   └── main.py              runs the whole pipeline
├── tests/test_transform.py
├── visualizations/          charts are saved here
├── .env.example
├── requirements.txt
└── README.md
```

## Database Schema

```text
genres                      movie_genres                  movies
──────────                  ────────────                  ──────
genre_id  (PK)  ◄────────── genre_id  (FK)                movie_id (PK)  ◄── movie_id (FK)
genre_name (UNIQUE)         movie_id  (FK) ──────────────► title, release_date, overview,
                            PRIMARY KEY (movie_id, genre_id)  popularity, vote_average,
                                                              vote_count, original_language,
                                                              adult, budget, revenue
```

- **movies**: one row per movie. `budget` and `revenue` are `NULL` when TMDB does not know them (TMDB sends 0, which would ruin averages).
- **genres**: one row per genre.
- **movie_genres**: a movie has many genres and a genre has many movies (**many-to-many**), so a link table connects them. Storing genres as a list inside `movies` would break normalization and make genre queries hard.
- **Constraints**: `NOT NULL` on required columns, `CHECK` on rating (0–10) and vote count (≥ 0), `ON DELETE CASCADE` from movies to links.
- **Indexes**: `release_date`, `vote_average`, `popularity`, and `movie_genres(genre_id)`.

## Setup

### 1. Get a TMDB API key (free)
Create an account at https://www.themoviedb.org, open **Settings → API**, and request a key. Use the **API Key (v3 auth)**.

### 2. Install PostgreSQL
Download it from https://www.postgresql.org/download/ and remember the password you set for the `postgres` user. On Windows, make sure the installer's `bin` folder (for example `C:\Program Files\PostgreSQL\16\bin`) is on your PATH so the `psql` command works.

### 3. Create the database
```bash
psql -U postgres -c "CREATE DATABASE movie_analytics;"
```

### 4. Create a virtual environment and install packages

Windows (PowerShell):
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

macOS / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Configure `.env`
Copy the example file and edit it:

```bash
copy .env.example .env        # Windows
cp .env.example .env          # macOS / Linux
```

Open `.env` and put in **your** TMDB key and PostgreSQL password. Never commit `.env` (it is in `.gitignore`).

### 6. (Optional) Create the tables yourself
The pipeline creates the tables and views automatically, but you can also do it by hand:

```bash
psql -U postgres -d movie_analytics -f sql/schema.sql
psql -U postgres -d movie_analytics -f sql/views.sql
```

## How to Run

```bash
python -m src.main               # Fetch -> Transform -> Load -> Verify (about 500 movies)
python -m src.main --movies 1000 # collect more movies
python -m src.main --refresh     # ignore the saved JSON and download again
python -m src.analysis           # create the charts in visualizations/
pytest                           # run the tests
```

Run the SQL queries:

```bash
psql -U postgres -d movie_analytics -f sql/analytical_queries.sql
```
or open `sql/analytical_queries.sql` in pgAdmin / DBeaver and run one query at a time.

The first run makes roughly 25 requests for the movie list plus one request per movie for its details (budget and revenue only exist in the details endpoint), so expect a few minutes.

## SQL Analysis

`sql/analytical_queries.sql` uses:

- `SELECT`, `WHERE`, `ORDER BY`, `LIMIT`
- `GROUP BY` and `HAVING`
- `JOIN` and `LEFT JOIN`
- Subqueries
- CTEs (`WITH`)
- Window functions: `RANK`, `ROW_NUMBER`, `LAG`, running totals with `SUM() OVER`

Views in `sql/views.sql`: `movie_genre_analysis`, `yearly_movie_statistics`, `top_movies_by_genre`.

## Visualizations

`python -m src.analysis` saves these into `visualizations/`:

| File | Chart |
|---|---|
| `avg_rating_by_genre.png` | Average rating for each genre |
| `movies_per_year.png` | Number of movies per release year |
| `top_10_popular_movies.png` | The 10 most popular movies |
| `avg_revenue_by_genre.png` | Average revenue per genre (movies with known revenue) |

## Example Insights

_Run the project, look at your charts and query results, and write your real findings here. For example: which genre has the highest average rating, and how many movies does it have? Which decade has the most movies in the data?_

- 
- 
- 

## Design Decisions

- **Why sort by vote count when collecting?** Movies with many votes have trustworthy ratings and usually have revenue data.
- **Why cache the raw JSON?** API calls are slow and rate-limited. Cleaning and loading can be repeated for free.
- **Why upsert (`ON CONFLICT DO UPDATE`)?** The pipeline is safe to re-run. New data updates existing rows instead of failing or duplicating.
- **Why one transaction?** If the load fails halfway, nothing is saved, so the database never holds half-loaded data.
- **Why `NULL` instead of 0 for unknown budget/revenue?** SQL aggregate functions ignore `NULL`, so averages stay correct.
- **Why keep `transform.py` free of API and database code?** Pure functions are easy to test.

## Limitations

- The dataset is the ~500 movies with the most votes, so it is biased towards well-known movies. Conclusions apply to this sample, not to all movies.
- A movie with several genres is counted once per genre in genre statistics.
- Revenue and budget are missing for many movies.

## Future Improvements

- Scheduled ingestion (cron / Task Scheduler)
- Docker for PostgreSQL and the app
- Orchestration with Airflow
- Dashboard in Power BI or Metabase
- Incremental loading (only new or changed movies)
- Cloud database (for example AWS RDS or Supabase)
