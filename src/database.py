"""Small helpers for connecting to PostgreSQL and running .sql files."""

import logging

import psycopg2

from src import config

logger = logging.getLogger(__name__)


def get_connection():
    """Open a PostgreSQL connection using the settings from .env."""
    try:
        return psycopg2.connect(**config.DB_SETTINGS)
    except psycopg2.OperationalError as error:
        raise SystemExit(
            f"Could not connect to PostgreSQL: {error}\n"
            "Check that PostgreSQL is running and that the DB_* values in .env are correct."
        )


def run_sql_file(connection, path):
    """Execute every statement inside a .sql file."""
    with open(path, encoding="utf-8") as file:
        sql_text = file.read()
    with connection.cursor() as cursor:
        cursor.execute(sql_text)
    connection.commit()
    logger.info("Ran %s", path.name)


def create_tables_and_views(connection):
    """Create the tables and views. Safe to run many times (uses IF NOT EXISTS / OR REPLACE)."""
    run_sql_file(connection, config.SQL_DIR / "schema.sql")
    run_sql_file(connection, config.SQL_DIR / "views.sql")
