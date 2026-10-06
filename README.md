# NSE Stock Analysis

Live demo: [LIVE DEMO URL]

The demo runs on Render's free tier, which sleeps after 15 minutes without visitors. If it has been asleep, the first load takes about a minute.

## What this project does

It takes 5 years of daily prices (5 Oct 2021 to 5 Oct 2026) for 10 large NSE stocks from different sectors, plus the Nifty 50 index, and:

1. downloads the data with yfinance, cleans it and stores it in a SQLite database (`data/nse.db`)
2. answers six questions with SQL: daily returns (`LAG`), 30 and 200-day moving averages (window frames), sector risk and return (`JOIN` + `GROUP BY`), biggest one-day moves, monthly volume and days above the 200-day average (CTE)
3. calculates annualised return, volatility, Sharpe ratio, max drawdown, beta and correlation with Pandas and NumPy
4. shows everything in a small Streamlit app with five tabs. The last tab shows the SQL behind each number.

The app only reads from the SQLite file. It never calls Yahoo Finance, so it keeps working even if the API is down or rate-limited.

![Overview tab](screenshots/overview.png)

## Why I built it

I wanted to practise the work a data analyst does with market data: getting raw prices into a database, writing SQL that answers real questions, and turning daily prices into the risk and return numbers people actually use. I kept the stack small (Python, SQLite, Pandas, Streamlit) so I can explain every line.

## Data and assumptions

| Stock | Sector | | Stock | Sector |
|---|---|---|---|---|
| RELIANCE.NS | Energy | | ITC.NS | FMCG |
| TCS.NS | IT | | HINDUNILVR.NS | FMCG |
| INFY.NS | IT | | LT.NS | Infrastructure |
| HDFCBANK.NS | Banking | | SUNPHARMA.NS | Pharma |
| ICICIBANK.NS | Banking | | SBIN.NS | Banking |
| SBIN.NS | Banking | | ^NSEI | Index (Nifty 50) |

- Source: Yahoo Finance through the `yfinance` library. 13,576 rows in total (about 1,234 trading days per stock).
- Returns use the adjusted close, so dividends and splits are not counted as price drops. Moving averages use the normal close, because that is the price people see on a chart.
- A year is 252 trading days. Annualised return is the compound annual growth rate (CAGR). Volatility is the standard deviation of daily returns times the square root of 252.
- **Risk-free rate: 7% a year.** This is my assumption, roughly the Indian 10-year government bond yield. It is used in the Sharpe ratio and can be changed in `config.py` (`RISK_FREE_RATE`).
- Beta is cov(stock, Nifty) / var(Nifty), using only days where both have data.
- Cleaning: rows without a close price are dropped, duplicate dates are removed, and dates are stored as `YYYY-MM-DD` text. Yahoo also included about 6 market holidays per stock as rows with zero volume and the same high and low price. No trading happened on those days, so the loader drops them.
- Sector numbers in SQL query 3 pool the daily returns of every stock in the sector. SQLite has no standard deviation function, so volatility there is `SQRT(AVG(r*r) - AVG(r)*AVG(r))` (population formula). Pandas uses the sample formula, but with 1,200+ days the difference is tiny.
- Limitations: the 10 stocks are today's large caps, so the list has survivorship bias. Corporate actions such as the ITC Hotels demerger (January 2025) rely on Yahoo's adjusted prices, which I did not check against exchange data.

## Project structure

```
nse-stock-analysis/
  app.py                  Streamlit app (reads data/nse.db only)
  config.py               tickers, sectors, dates, risk-free rate
  requirements.txt        pinned package versions
  render.yaml             Render deployment settings
  .streamlit/config.toml  app theme
  data/nse.db             SQLite database (committed so the deployed app has data)
  db/schema.sql           table definitions
  sql/queries.sql         the six saved SQL queries, with comments
  src/fetch_data.py       download, clean and load into SQLite
  src/queries.py          reads queries.sql and runs the queries
  src/analytics.py        return, volatility, Sharpe, drawdown, beta, correlation
  src/charts.py           Plotly charts with one shared style
  tests/test_analytics.py unit tests with hand-checked answers
  notebooks/exploration.ipynb  the same analysis step by step
  screenshots/            images used in this README
```

## How to run locally

Needs Python 3.11.

```bash
git clone https://github.com/om3105/NSE-Stock-Analysis.git
cd nse-stock-analysis
python3.11 -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m pytest                   # run the unit tests
streamlit run app.py               # opens http://localhost:8501
```

The database is already in the repo. To download fresh data (the last 5 years up to today), run the loader. It is safe to run more than once:

```bash
python -m src.fetch_data
```

Re-running it will change the numbers below, because the 5-year window moves.

To open the notebook:

```bash
pip install jupyter
jupyter notebook notebooks/exploration.ipynb
```

## Key findings

All numbers are for 5 Oct 2021 to 5 Oct 2026.

1. **Sun Pharma had the best risk-adjusted return.** It returned 18.3% a year with 20.0% volatility (Sharpe 0.57) and had the lowest beta of the 10 stocks (0.56). L&T (18.5%) and SBI (18.1%) returned about the same but with 24.5% volatility and a beta above 1.1, so their Sharpe ratios were lower.
2. **The two IT stocks did worst.** TCS returned -8.9% a year and Infosys -7.2%, with max drawdowns of -53.4% and -48.2%. They were also the most correlated pair in the dataset (0.73). Infosys and TCS closed above their 200-day average on only 39-43% of days, against 82% for L&T and ICICI Bank.
3. **The index was much less volatile than any single stock.** The Nifty 50 had 13.8% volatility, while every one of the 10 stocks was between 20.0% and 26.1%. The average correlation between two of the stocks was only 0.28, which shows why holding many stocks reduces risk.
4. **Half the stocks beat the 7% risk-free rate; the index did not.** The Nifty 50 returned 4.9% a year, so its Sharpe ratio was negative (-0.15). Only Sun Pharma, L&T, SBI, ICICI Bank and ITC returned more than 7% a year.
5. **The biggest one-day losses clustered on one day.** Two of the five worst single-day moves were on 4 June 2024, the general election result day: SBI fell 14.4% and L&T fell 12.7%, while the Nifty 50 fell 5.9%. Hindustan Unilever rose 6.0% on the same day.

![Price and trend tab](screenshots/price_trend.png)

![Compare tab](screenshots/compare.png)

## What I would improve

1. Pull the risk-free rate from real data (for example RBI T-bill yields) instead of using a fixed 7%.
2. Add more stocks, ideally all Nifty 50 members including ones that left the index, to reduce survivorship bias.
3. Add a portfolio page where you choose weights for the stocks and see the portfolio's return, volatility and Sharpe ratio, with a simple minimum-variance option.

---

For learning and analysis only. Not investment advice.
