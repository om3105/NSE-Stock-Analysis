"""Read the saved queries from sql/queries.sql and run them against data/nse.db."""
import math
import sqlite3

import pandas as pd

import config


def get_connection() -> sqlite3.Connection:
    """Open the database. Read-only, because the app never writes to it."""
    conn = sqlite3.connect(config.DB_PATH.as_uri() + "?mode=ro", uri=True)
    # Not every SQLite build has SQRT (needed for volatility), so add Python's
    conn.create_function("SQRT", 1, math.sqrt)
    return conn


def read_sql(sql: str, params: dict | None = None) -> pd.DataFrame:
    """Run any SQL and return the result as a DataFrame."""
    conn = get_connection()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


def load_queries() -> dict[str, dict[str, str]]:
    """Split queries.sql into {name: {"title": ..., "sql": ...}}.

    Each query starts with '-- name: <name>' and the next comment line is its title.
    The SQL text keeps its comments so the app can show them.
    """
    queries = {}
    # Everything before the first '-- name:' is the file header, so skip it
    for block in config.QUERIES_PATH.read_text().split("-- name:")[1:]:
        name, sql = block.split("\n", 1)
        title = sql.split("\n", 1)[0].lstrip("- ").strip()
        queries[name.strip()] = {"title": title, "sql": sql.strip()}
    return queries


def run_query(name: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Run one saved query for a date range (dates as 'YYYY-MM-DD')."""
    sql = load_queries()[name]["sql"]
    return read_sql(sql, {"start_date": str(start_date), "end_date": str(end_date)})
