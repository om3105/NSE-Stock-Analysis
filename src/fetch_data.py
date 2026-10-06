"""Download daily prices from Yahoo Finance, clean them and load them into SQLite.

Run from the project folder:  python -m src.fetch_data
Safe to run again: each ticker's old rows are deleted and the fresh rows
inserted in one transaction, and (ticker, date) is the primary key, so
duplicates cannot appear.
"""
import sqlite3
from datetime import timedelta

import pandas as pd
import yfinance as yf

import config

# yfinance column name -> our column name
COLUMN_NAMES = {
    "Date": "date",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
}
PRICE_COLUMNS = ["ticker", "date", "open", "high", "low", "close", "adj_close", "volume"]


def download(ticker: str) -> pd.DataFrame:
    """Download daily prices for one ticker. Returns an empty DataFrame on failure."""
    # yfinance treats 'end' as exclusive, so add one day to include today
    df = yf.download(
        ticker,
        start=config.START_DATE.isoformat(),
        end=(config.END_DATE + timedelta(days=1)).isoformat(),
        auto_adjust=False,        # keep both Close and Adj Close
        progress=False,
        multi_level_index=False,  # plain column names for a single ticker
    )
    return df if df is not None else pd.DataFrame()


def clean(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Rename columns, drop bad rows and make dates ISO strings."""
    df = df.reset_index().rename(columns=COLUMN_NAMES)

    # A day without a close price is useless for the analysis
    df = df.dropna(subset=["close"])

    # Yahoo sometimes adds market holidays as a row with zero volume and the
    # same high and low price. No trading happened, so drop those rows.
    holidays = (df["volume"] == 0) & (df["high"] == df["low"])
    if holidays.any():
        print(f"  {ticker}: dropped {holidays.sum()} non-trading rows")
        df = df[~holidays]

    # Store dates as 'YYYY-MM-DD' text (SQLite has no real date type)
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

    # The same date should never appear twice; keep the last row if it does
    duplicates = df["date"].duplicated().sum()
    if duplicates:
        print(f"  {ticker}: dropped {duplicates} duplicate dates")
        df = df.drop_duplicates(subset="date", keep="last")

    df["ticker"] = ticker
    return df[PRICE_COLUMNS].sort_values("date")


def save_prices(conn: sqlite3.Connection, df: pd.DataFrame, ticker: str) -> None:
    """Replace all stored rows for this ticker with the freshly cleaned rows."""
    # to_dict gives plain Python types, which sqlite3 can store directly.
    # NaN values are turned into None so they are stored as NULL.
    rows = df.astype(object).where(df.notna(), None).to_dict("records")
    for row in rows:
        if row["volume"] is not None:
            row["volume"] = int(row["volume"])
    # 'with conn' runs both statements as one transaction: if the insert
    # fails, the delete is rolled back and the old rows are kept
    with conn:
        conn.execute("DELETE FROM prices WHERE ticker = ?", (ticker,))
        conn.executemany(
            """INSERT INTO prices
               (ticker, date, open, high, low, close, adj_close, volume)
               VALUES (:ticker, :date, :open, :high, :low, :close, :adj_close, :volume)""",
            rows,
        )


def main() -> None:
    config.DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(config.SCHEMA_PATH.read_text())

    # The stocks table must be filled first because prices has a foreign key to it
    stock_rows = [(t, name, sector) for t, (name, sector) in config.STOCKS.items()]
    stock_rows.append((config.BENCHMARK, config.BENCHMARK_NAME, "Index"))
    conn.executemany("INSERT OR REPLACE INTO stocks VALUES (?, ?, ?)", stock_rows)
    conn.commit()

    print(f"Downloading {config.START_DATE} to {config.END_DATE}")
    failed = []
    for ticker, _, _ in stock_rows:
        # One bad ticker should not stop the others from loading
        try:
            raw = download(ticker)
            if raw.empty:
                raise ValueError("no data returned")
            df = clean(raw, ticker)
            save_prices(conn, df, ticker)
            print(f"  {ticker}: {len(df)} rows")
        except Exception as error:
            print(f"  {ticker}: FAILED ({error})")
            failed.append(ticker)

    # Summary straight from the database, so it shows what is actually stored
    summary = pd.read_sql_query(
        """SELECT ticker, COUNT(*) AS rows, MIN(date) AS first_date, MAX(date) AS last_date
           FROM prices GROUP BY ticker ORDER BY ticker""",
        conn,
    )
    conn.close()

    print("\nRows in database per ticker:")
    print(summary.to_string(index=False))
    print(f"Total rows: {summary['rows'].sum()}")
    if failed:
        print(f"Failed tickers (re-run to retry): {', '.join(failed)}")


if __name__ == "__main__":
    main()
