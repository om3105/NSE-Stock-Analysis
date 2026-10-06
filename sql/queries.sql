-- Saved SQL queries used by the app and shown in its SQL explorer tab.
-- Every query starts with a comment line holding its name (name: ...) so
-- src/queries.py can split this file into separate queries. The line after
-- the name is the title.
-- :start_date and :end_date are filled in from the date filter in the app.


-- name: daily_returns
-- 1. Daily return per stock
-- Answers: by what percentage did each stock (and the Nifty 50) move each day?
-- LAG() looks back one row inside each ticker's own rows (PARTITION BY ticker),
-- ordered by date, so it returns the previous trading day's price.
-- adj_close is used so dividends and splits do not look like price drops.
-- The return is calculated on all rows first and filtered afterwards, so the
-- first day of the chosen range still has a previous day to compare with.
WITH returns AS (
    SELECT
        ticker,
        date,
        adj_close,
        adj_close / LAG(adj_close) OVER (PARTITION BY ticker ORDER BY date) - 1 AS daily_return
    FROM prices
)
SELECT ticker, date, adj_close, daily_return
FROM returns
WHERE date BETWEEN :start_date AND :end_date
ORDER BY ticker, date;


-- name: moving_averages
-- 2. 30-day and 200-day moving averages of the close price
-- Answers: what are the short-term and long-term price trends of each stock?
-- The frame "ROWS BETWEEN 29 PRECEDING AND CURRENT ROW" averages today's close
-- with the 29 trading days before it. COUNT(*) over the same frame tells us
-- how many days were really available, so the average stays NULL until a
-- full 30 (or 200) days of history exist.
WITH ma AS (
    SELECT
        ticker,
        date,
        close,
        AVG(close) OVER last_30  AS ma_30,
        COUNT(*)   OVER last_30  AS days_30,
        AVG(close) OVER last_200 AS ma_200,
        COUNT(*)   OVER last_200 AS days_200
    FROM prices
    WINDOW
        last_30  AS (PARTITION BY ticker ORDER BY date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW),
        last_200 AS (PARTITION BY ticker ORDER BY date ROWS BETWEEN 199 PRECEDING AND CURRENT ROW)
)
SELECT
    ticker,
    date,
    close,
    CASE WHEN days_30 = 30 THEN ma_30 END    AS ma_30,
    CASE WHEN days_200 = 200 THEN ma_200 END AS ma_200
FROM ma
WHERE date BETWEEN :start_date AND :end_date
ORDER BY ticker, date;


-- name: sector_risk_return
-- 3. Average daily return and volatility per sector
-- Answers: which sectors gave higher returns, and which moved around more?
-- JOIN adds the sector from the stocks table, then GROUP BY sector.
-- SQLite has no STDEV function, so volatility uses the population formula
-- variance = AVG(r*r) - AVG(r)*AVG(r), then SQRT of that.
-- Annualised: average daily return x 252, volatility x SQRT(252).
-- All daily returns of all stocks in a sector are pooled together.
WITH returns AS (
    SELECT
        p.ticker,
        s.sector,
        p.date,
        p.adj_close / LAG(p.adj_close) OVER (PARTITION BY p.ticker ORDER BY p.date) - 1 AS r
    FROM prices AS p
    JOIN stocks AS s ON s.ticker = p.ticker
)
SELECT
    sector,
    COUNT(DISTINCT ticker)                                      AS stocks,
    ROUND(AVG(r) * 100, 3)                                      AS avg_daily_return_pct,
    ROUND(SQRT(AVG(r * r) - AVG(r) * AVG(r)) * 100, 3)          AS daily_volatility_pct,
    ROUND(AVG(r) * 252 * 100, 2)                                AS ann_return_pct,
    ROUND(SQRT(AVG(r * r) - AVG(r) * AVG(r)) * SQRT(252) * 100, 2) AS ann_volatility_pct
FROM returns
WHERE r IS NOT NULL
  AND date BETWEEN :start_date AND :end_date
GROUP BY sector
ORDER BY ann_return_pct DESC;


-- name: biggest_moves
-- 4. Top 5 best and worst single-day moves
-- Answers: which days had the largest one-day gains and losses, and for which company?
-- The returns CTE uses LAG like query 1, the JOIN adds the company name, and
-- two small CTEs pick the top 5 and bottom 5 before UNION ALL stacks them.
-- The Nifty 50 index is left out so only individual stocks are ranked.
WITH returns AS (
    SELECT
        ticker,
        date,
        adj_close / LAG(adj_close) OVER (PARTITION BY ticker ORDER BY date) - 1 AS daily_return
    FROM prices
),
moves AS (
    SELECT s.company_name, s.sector, ret.date, ret.daily_return
    FROM returns AS ret
    JOIN stocks AS s ON s.ticker = ret.ticker
    WHERE s.sector <> 'Index'
      AND ret.daily_return IS NOT NULL
      AND ret.date BETWEEN :start_date AND :end_date
),
best AS (
    SELECT 'Best' AS move, * FROM moves ORDER BY daily_return DESC LIMIT 5
),
worst AS (
    SELECT 'Worst' AS move, * FROM moves ORDER BY daily_return ASC LIMIT 5
)
SELECT move, company_name, sector, date, ROUND(daily_return * 100, 2) AS return_pct FROM best
UNION ALL
SELECT move, company_name, sector, date, ROUND(daily_return * 100, 2) AS return_pct FROM worst;


-- name: monthly_volume
-- 5. Monthly average volume per stock
-- Answers: how actively was each stock traded, month by month?
-- strftime('%Y-%m', date) turns '2024-06-04' into '2024-06' so rows can be
-- grouped by month. The Nifty 50 is left out because Yahoo does not give a
-- reliable volume for the index.
SELECT
    p.ticker,
    s.company_name,
    strftime('%Y-%m', p.date) AS month,
    COUNT(*)                  AS trading_days,
    CAST(ROUND(AVG(p.volume)) AS INTEGER) AS avg_volume
FROM prices AS p
JOIN stocks AS s ON s.ticker = p.ticker
WHERE s.sector <> 'Index'
  AND p.date BETWEEN :start_date AND :end_date
GROUP BY p.ticker, month
ORDER BY p.ticker, month;


-- name: days_above_ma200
-- 6. Share of days each stock closed above vs below its 200-day moving average
-- Answers: how often was each stock trading above its long-term trend?
-- The CTE works out the 200-day average first, then the main query counts
-- the days. (close > ma_200) is 1 when true and 0 when false, so SUM() counts
-- the days above. Days without a full 200 days of history are skipped.
WITH ma AS (
    SELECT
        ticker,
        date,
        close,
        AVG(close) OVER last_200 AS ma_200,
        COUNT(*)   OVER last_200 AS days_in_window
    FROM prices
    WINDOW last_200 AS (PARTITION BY ticker ORDER BY date ROWS BETWEEN 199 PRECEDING AND CURRENT ROW)
)
SELECT
    ma.ticker,
    s.company_name,
    COUNT(*)                                         AS days,
    ROUND(100.0 * SUM(ma.close > ma.ma_200) / COUNT(*), 1)  AS pct_above,
    ROUND(100.0 * SUM(ma.close <= ma.ma_200) / COUNT(*), 1) AS pct_below
FROM ma
JOIN stocks AS s ON s.ticker = ma.ticker
WHERE ma.days_in_window = 200
  AND ma.date BETWEEN :start_date AND :end_date
GROUP BY ma.ticker, s.company_name
ORDER BY pct_above DESC;
