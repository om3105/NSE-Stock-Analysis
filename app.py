"""NSE Stock Analysis app. Reads everything from data/nse.db and never calls yfinance.

Run from the project folder:  streamlit run app.py
"""
from datetime import date

import pandas as pd
import streamlit as st

import config
from src import analytics, charts, queries

st.set_page_config(page_title="NSE Stock Analysis", layout="wide")

# Hide Streamlit's menu, toolbar and footer, keep lines readable on wide screens,
# make headings smaller than Streamlit's default and the stock chips less loud
st.markdown(
    """
    <style>
    #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {display: none;}
    .block-container {max-width: 1150px; padding-top: 2.5rem;}
    h1 {font-size: 1.6rem !important; font-weight: 600 !important;}
    h3 {font-size: 1.15rem !important; font-weight: 600 !important; padding-top: 1rem !important;}
    [data-tag] {background-color: #E8EEF4 !important;}
    [data-tag], [data-tag] * {color: #1F4E79 !important;}
    </style>
    """,
    unsafe_allow_html=True,
)

POSITIVE, NEGATIVE = "#2E7D4F", "#A23B3B"   # subtle green / red text for returns
PLOT_CONFIG = {"displayModeBar": False}       # hide the Plotly toolbar


# ---- Database reads, cached so each query runs once per date range ----

@st.cache_data
def load_query(name: str, start: str, end: str) -> pd.DataFrame:
    return queries.run_query(name, start, end)


@st.cache_data
def load_stocks() -> pd.DataFrame:
    return queries.read_sql("SELECT ticker, company_name, sector FROM stocks").set_index("ticker")


@st.cache_data
def load_date_bounds() -> tuple[date, date]:
    row = queries.read_sql("SELECT MIN(date) AS first, MAX(date) AS last FROM prices").iloc[0]
    return date.fromisoformat(row["first"]), date.fromisoformat(row["last"])


@st.cache_data
def load_saved_queries() -> dict[str, dict[str, str]]:
    return queries.load_queries()


# ---- Small display helpers ----

def show_chart(fig) -> None:
    # theme=None so Streamlit does not override the style from charts.py
    st.plotly_chart(fig, theme=None, config=PLOT_CONFIG)


def sign_colour(value: float) -> str:
    """CSS text colour for a table cell: green if positive, red if negative."""
    if value > 0:
        return f"color: {POSITIVE}"
    if value < 0:
        return f"color: {NEGATIVE}"
    return ""


def table_height(rows: int) -> int:
    """Pixel height that fits every row, so short tables do not scroll."""
    return 38 + 35 * rows


def nice_date(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


# ---- Header and the date filter ----

stocks = load_stocks()
names = stocks["company_name"].to_dict()
first_day, last_day = load_date_bounds()
n_stocks = int((stocks["sector"] != "Index").sum())

st.title(f"NSE Stock Analysis, {n_stocks} large-cap stocks, {first_day.year}-{last_day.year}")
st.write(
    f"Daily prices for {n_stocks} NSE stocks and the Nifty 50 from {nice_date(first_day)} "
    f"to {nice_date(last_day)}, downloaded from Yahoo Finance and stored in SQLite. "
    "The date range in the sidebar applies to every tab."
)

with st.sidebar:
    picked_dates = st.date_input(
        "Date range",
        value=(first_day, last_day),
        min_value=first_day,
        max_value=last_day,
        format="DD/MM/YYYY",
    )

# While the user is still picking, the widget returns only the start date
if len(picked_dates) != 2:
    st.write("Pick an end date in the sidebar.")
    st.stop()
start, end = picked_dates
if (end - start).days < 60:
    st.warning("Pick a range of at least 60 days, otherwise the yearly figures are not meaningful.")
    st.stop()
start_s, end_s = start.isoformat(), end.isoformat()

# Daily returns from SQL (query 1), reshaped to one column per ticker
daily = load_query("daily_returns", start_s, end_s)
returns = daily.pivot(index="date", columns="ticker", values="daily_return")
prices = daily.pivot(index="date", columns="ticker", values="adj_close")

overview, trend, compare, sectors, explorer = st.tabs(
    ["Overview", "Price and trend", "Compare", "Sectors", "SQL explorer"]
)

# ---- Tab 1: one row of metrics per stock ----
with overview:
    summary = analytics.summary_table(returns, prices, config.BENCHMARK, config.RISK_FREE_RATE)
    nifty = summary.loc[config.BENCHMARK]
    joined = summary.drop(config.BENCHMARK).join(stocks)
    table = pd.DataFrame({
        "Company": joined["company_name"],
        "Sector": joined["sector"],
        "Ann. return (%)": joined["ann_return"] * 100,
        "Volatility (%)": joined["ann_volatility"] * 100,
        "Sharpe": joined["sharpe"],
        "Max drawdown (%)": joined["max_drawdown"] * 100,
        "Beta vs Nifty": joined["beta"],
    }).sort_values("Sharpe", ascending=False)

    st.subheader("Risk and return by stock")
    st.caption("Sorted by Sharpe ratio, highest first. Click a column header to sort by another column.")
    styled = table.style.format({
        "Ann. return (%)": "{:.1f}",
        "Volatility (%)": "{:.1f}",
        "Sharpe": "{:.2f}",
        "Max drawdown (%)": "{:.1f}",
        "Beta vs Nifty": "{:.2f}",
    }).map(sign_colour, subset=["Ann. return (%)"])
    st.dataframe(styled, hide_index=True, height=table_height(len(table)))
    st.caption(
        "Ann. return is the compound annual growth rate of the adjusted close. "
        "Volatility is the standard deviation of daily returns, annualised. "
        f"Sharpe is (return minus a {config.RISK_FREE_RATE:.0%} risk-free rate) divided by volatility. "
        "Max drawdown is the largest fall from a previous high. "
        "Beta is how much the stock moved, on average, for a 1% move in the Nifty 50."
    )
    st.write(
        f"Nifty 50 over the same dates: return {nifty['ann_return']:.1%} a year, "
        f"volatility {nifty['ann_volatility']:.1%}, Sharpe {nifty['sharpe']:.2f}, "
        f"max drawdown {nifty['max_drawdown']:.1%}."
    )

    st.subheader("Largest single-day moves")
    st.caption("Daily return from the adjusted close, from SQL query 4. The Nifty 50 is not included.")
    moves = load_query("biggest_moves", start_s, end_s)
    for column, move in zip(st.columns(2, gap="large"), ["Best", "Worst"]):
        part = moves.loc[moves["move"] == move, ["company_name", "date", "return_pct"]]
        part.columns = ["Company", "Date", "Return (%)"]
        column.markdown(f"**{move} 5 days**")
        column.dataframe(
            part.style.format({"Return (%)": "{:+.2f}"}).map(sign_colour, subset=["Return (%)"]),
            hide_index=True,
        )

# ---- Tab 2: price chart with moving averages for one stock ----
with trend:
    ticker = st.selectbox(
        "Stock", list(config.STOCKS), width=320,
        format_func=lambda t: f"{names[t]} ({charts.short_name(t)})",
    )
    ma = load_query("moving_averages", start_s, end_s)
    above = load_query("days_above_ma200", start_s, end_s).set_index("ticker")

    if ticker in above.index:
        row = above.loc[ticker]
        st.write(
            f"{names[ticker]} closed above its 200-day moving average on **{row['pct_above']:.1f}%** "
            f"of trading days and below it on {row['pct_below']:.1f}%. This counts the "
            f"{row['days']:,} days in the range that have a full 200 days of history before them."
        )
    else:
        st.write("No day in this range has 200 days of history before it, so there is no 200-day average.")

    show_chart(charts.price_chart(ma[ma["ticker"] == ticker], ticker))
    st.caption(
        "Close is the daily closing price in rupees. The moving averages are the mean close of the "
        "last 30 and 200 trading days, worked out with SQL window functions (query 2). "
        "A close above the 200-day line is commonly read as a long-term uptrend."
    )
    volume = load_query("monthly_volume", start_s, end_s)
    show_chart(charts.volume_chart(volume[volume["ticker"] == ticker], ticker))
    st.caption("Average number of shares traded per day in each month (query 5). The first and last month may be partial.")

# ---- Tab 3: compare 2 to 4 stocks ----
with compare:
    picked = st.multiselect(
        "Stocks to compare (2 to 4)", list(config.STOCKS),
        default=["RELIANCE.NS", "TCS.NS", "ICICIBANK.NS"], max_selections=4, width=640,
        format_func=lambda t: f"{names[t]} ({charts.short_name(t)})",
    )
    if len(picked) < 2:
        st.write("Pick at least two stocks.")
    else:
        left, right = st.columns([3, 2], gap="large")
        with left:
            # bfill fills each column from the next row, so row 0 holds each
            # stock's first available price; dividing by it starts every line at 100
            rebased = prices[picked + [config.BENCHMARK]]
            rebased = rebased / rebased.bfill().iloc[0] * 100
            show_chart(charts.cumulative_chart(rebased))
            st.caption(
                "What 100 rupees invested on the first day of the range would be worth, using the "
                "adjusted close, so dividends are counted. The dotted grey line is the Nifty 50."
            )
        with right:
            show_chart(charts.correlation_heatmap(analytics.correlation_matrix(returns[picked])))
            st.caption(
                "Correlation of daily returns. 1 means the two stocks always move together, "
                "0 means no linear relationship, -1 means they move in opposite directions."
            )

# ---- Tab 4: sector averages from SQL query 3 ----
with sectors:
    sector = load_query("sector_risk_return", start_s, end_s)
    index_label = "Nifty 50 index"
    labels = (sector["sector"] + " (" + sector["stocks"].astype(str) + ")").where(
        sector["sector"] != "Index", index_label
    )
    sector_return = pd.Series(sector["ann_return_pct"].values, index=labels)
    sector_vol = pd.Series(sector["ann_volatility_pct"].values, index=labels)

    st.caption(
        "Each sector pools the daily returns of all its stocks; the number of stocks is in brackets. "
        "The grey bar is the Nifty 50 for comparison. Both charts come from SQL query 3."
    )
    left, right = st.columns(2, gap="large")
    with left:
        show_chart(charts.bar_chart(sector_return, "Average return by sector",
                                    "Average daily return x 252 (%)", highlight=index_label))
        st.caption(
            "Return here is the average daily return multiplied by 252. It is a simple average, "
            "not compounded, so it is not the same number as the Overview tab."
        )
    with right:
        show_chart(charts.bar_chart(sector_vol, "Volatility by sector",
                                    "Annualised volatility (%)", highlight=index_label))
        st.caption(
            "Volatility is the standard deviation of daily returns, annualised by multiplying "
            "by the square root of 252. Higher means larger day-to-day swings."
        )

# ---- Tab 5: the saved SQL and its result ----
with explorer:
    saved = load_saved_queries()
    name = st.selectbox("Saved query", list(saved), width=560, format_func=lambda n: saved[n]["title"])
    st.code(saved[name]["sql"], language="sql")
    result = load_query(name, start_s, end_s)
    st.caption(f"{len(result):,} rows. :start_date = {start_s} and :end_date = {end_s}, taken from the sidebar.")
    # Thousands separators for whole-number columns such as volume
    int_columns = result.select_dtypes("integer").columns
    formats = {c: st.column_config.NumberColumn(format="localized") for c in int_columns}
    st.dataframe(result.round(4), hide_index=True, column_config=formats,
                 height=min(table_height(len(result)), 420))

st.divider()
st.caption(
    "For learning and analysis only. Not investment advice. "
    f"Data from Yahoo Finance; last trading day in the database: {nice_date(last_day)}."
)
