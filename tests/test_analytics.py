"""Tests with tiny inputs where the right answer can be worked out by hand.

Run from the project folder:  python -m pytest
"""
import pandas as pd
import pytest

from src import analytics


def test_annualised_return():
    # Two periods in one "year": +10% then -10%  ->  1.10 * 0.90 = 0.99  ->  -1%
    returns = pd.Series([0.10, -0.10])
    assert analytics.annualised_return(returns, periods_per_year=2) == pytest.approx(-0.01)


def test_annualised_volatility():
    # Returns 2%, 0%, -2%: mean is 0, sample variance = (0.0004 + 0 + 0.0004) / 2
    # = 0.0004, so daily std = 0.02. With 4 periods a year: 0.02 * sqrt(4) = 0.04
    returns = pd.Series([0.02, 0.0, -0.02])
    assert analytics.annualised_volatility(returns, periods_per_year=4) == pytest.approx(0.04)


def test_sharpe_ratio():
    # +10% then -10% with 2 periods a year:
    # annual return = 0.99 - 1 = -0.01 (from the first test)
    # sample std of [0.10, -0.10] = 0.1414..., times sqrt(2) = 0.20
    # Sharpe with a 5% risk-free rate = (-0.01 - 0.05) / 0.20 = -0.30
    returns = pd.Series([0.10, -0.10])
    result = analytics.sharpe_ratio(returns, risk_free_rate=0.05, periods_per_year=2)
    assert result == pytest.approx(-0.30)


def test_max_drawdown():
    # Peak is 120, lowest point after it is 90: 90 / 120 - 1 = -25%
    prices = pd.Series([100, 120, 90, 110, 130])
    assert analytics.max_drawdown(prices) == pytest.approx(-0.25)


def test_max_drawdown_when_price_only_rises():
    prices = pd.Series([100, 101, 105, 110])
    assert analytics.max_drawdown(prices) == 0


def test_beta_of_stock_that_moves_twice_as_much():
    # The stock always moves exactly 2x the index, so beta must be 2
    nifty = pd.Series([0.01, -0.02, 0.03, 0.00])
    stock = nifty * 2
    assert analytics.beta_vs_benchmark(stock, nifty) == pytest.approx(2.0)


def test_beta_ignores_days_with_missing_data():
    # The NaN day should be dropped, leaving the same 2x relationship
    nifty = pd.Series([0.01, -0.02, None, 0.03])
    stock = pd.Series([0.02, -0.04, 0.05, 0.06])
    assert analytics.beta_vs_benchmark(stock, nifty) == pytest.approx(2.0)


def test_correlation_matrix():
    # b moves with a, c moves exactly opposite to a
    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 4, 6, 8], "c": [4, 3, 2, 1]})
    corr = analytics.correlation_matrix(df)
    assert corr.loc["a", "b"] == pytest.approx(1.0)
    assert corr.loc["a", "c"] == pytest.approx(-1.0)
    assert corr.loc["a", "a"] == pytest.approx(1.0)
