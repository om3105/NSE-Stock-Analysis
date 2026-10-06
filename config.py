"""Project settings. Change the stock list, dates or assumptions here."""
from datetime import date, timedelta
from pathlib import Path

# File locations, all relative to this file so the project runs from any folder
ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "nse.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"
QUERIES_PATH = ROOT / "sql" / "queries.sql"

# Yahoo Finance ticker -> (company name, sector)
STOCKS = {
    "RELIANCE.NS": ("Reliance Industries", "Energy"),
    "TCS.NS": ("Tata Consultancy Services", "IT"),
    "INFY.NS": ("Infosys", "IT"),
    "HDFCBANK.NS": ("HDFC Bank", "Banking"),
    "ICICIBANK.NS": ("ICICI Bank", "Banking"),
    "SBIN.NS": ("State Bank of India", "Banking"),
    "ITC.NS": ("ITC", "FMCG"),
    "HINDUNILVR.NS": ("Hindustan Unilever", "FMCG"),
    "LT.NS": ("Larsen & Toubro", "Infrastructure"),
    "SUNPHARMA.NS": ("Sun Pharmaceutical", "Pharma"),
}

# The benchmark goes in the same tables, with sector = 'Index'
BENCHMARK = "^NSEI"
BENCHMARK_NAME = "Nifty 50"

# Last 5 years of daily data, ending today (5 * 365.25 days is about 5 years)
END_DATE = date.today()
START_DATE = END_DATE - timedelta(days=1826)

# Assumptions used in the analysis
TRADING_DAYS = 252      # trading days in a year, used to annualise daily numbers
RISK_FREE_RATE = 0.07   # approx. Indian 10-year government bond yield (assumption)
