-- Database schema for the NSE stock project (SQLite).
-- IF NOT EXISTS means this file can be run again without errors.

-- One row per stock. The Nifty 50 index is stored here too, with sector = 'Index'.
CREATE TABLE IF NOT EXISTS stocks (
    ticker       TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    sector       TEXT NOT NULL
);

-- One row per stock per trading day.
-- The primary key (ticker, date) stops the same day being stored twice.
CREATE TABLE IF NOT EXISTS prices (
    ticker    TEXT NOT NULL,
    date      TEXT NOT NULL,   -- ISO format 'YYYY-MM-DD', so text sorting = date sorting
    open      REAL,
    high      REAL,
    low       REAL,
    close     REAL NOT NULL,
    adj_close REAL,            -- close adjusted for dividends and splits
    volume    INTEGER,
    PRIMARY KEY (ticker, date),
    FOREIGN KEY (ticker) REFERENCES stocks (ticker)
);

-- Most queries filter on a date range, so index the date column.
CREATE INDEX IF NOT EXISTS idx_prices_date ON prices (date);
