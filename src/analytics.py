"""Risk and return calculations with Pandas and NumPy.

All functions take daily data. A year is taken as 252 trading days.
"""
import numpy as np
import pandas as pd

TRADING_DAYS = 252


def annualised_return(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    """Compound annual growth rate (CAGR) from a series of daily returns.

    Multiply (1 + r) for every day to get the total growth, then turn that
    into a yearly rate: growth ** (1 / years) - 1.
    """
    returns = returns.dropna()
    total_growth = (1 + returns).prod()
    years = len(returns) / periods_per_year
    return total_growth ** (1 / years) - 1


def annualised_volatility(returns: pd.Series, periods_per_year: int = TRADING_DAYS) -> float:
    """Standard deviation of daily returns, scaled to a year: daily std * sqrt(252)."""
    return returns.dropna().std() * np.sqrt(periods_per_year)


def sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.07,
    periods_per_year: int = TRADING_DAYS,
) -> float:
    """Return earned above the risk-free rate per unit of volatility.

    (annualised return - risk-free rate) / annualised volatility.
    The default 7% is an assumption (roughly the Indian 10-year bond yield).
    """
    excess_return = annualised_return(returns, periods_per_year) - risk_free_rate
    return excess_return / annualised_volatility(returns, periods_per_year)


def max_drawdown(prices: pd.Series) -> float:
    """Largest fall from a previous peak, as a negative fraction (-0.25 = -25%)."""
    prices = prices.dropna()
    running_peak = prices.cummax()          # highest price seen so far
    drawdown = prices / running_peak - 1    # how far below that peak we are today
    return drawdown.min()


def beta_vs_benchmark(stock_returns: pd.Series, nifty_returns: pd.Series) -> float:
    """How much the stock moves when the Nifty moves: cov(stock, nifty) / var(nifty).

    Only days where both series have a return are used.
    """
    both = pd.concat([stock_returns, nifty_returns], axis=1).dropna()
    stock, nifty = both.iloc[:, 0], both.iloc[:, 1]
    return stock.cov(nifty) / nifty.var()


def correlation_matrix(returns_df: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation of daily returns between every pair of columns."""
    return returns_df.corr()


def summary_table(
    returns_df: pd.DataFrame,
    prices_df: pd.DataFrame,
    benchmark: str,
    risk_free_rate: float = 0.07,
) -> pd.DataFrame:
    """One row per column of returns_df with all the metrics above.

    returns_df and prices_df have one column per ticker and one row per date.
    """
    rows = []
    for ticker in returns_df.columns:
        r = returns_df[ticker]
        rows.append({
            "ticker": ticker,
            "ann_return": annualised_return(r),
            "ann_volatility": annualised_volatility(r),
            "sharpe": sharpe_ratio(r, risk_free_rate),
            "max_drawdown": max_drawdown(prices_df[ticker]),
            "beta": beta_vs_benchmark(r, returns_df[benchmark]),
        })
    return pd.DataFrame(rows).set_index("ticker")
