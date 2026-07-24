"""Tests de las métricas financieras en src/backtest/metrics.py."""

import numpy as np
import pandas as pd
import pytest

from src.backtest.metrics import (
    buy_and_hold_metrics,
    live_summary,
    max_drawdown,
    profit_factor,
    sharpe_ratio,
    summary,
    total_return,
    win_rate,
)

# --------------------------------------------------------------------------- #
# total_return
# --------------------------------------------------------------------------- #


def test_total_return():
    assert total_return(10_000, 12_000) == pytest.approx(0.20)
    assert total_return(10_000, 8_000) == pytest.approx(-0.20)


# --------------------------------------------------------------------------- #
# max_drawdown
# --------------------------------------------------------------------------- #


def test_max_drawdown_known_value():
    equity = pd.Series([100, 120, 60, 80, 200])
    # Pico 120 → valle 60  =>  (60 - 120) / 120 = -0.5
    assert max_drawdown(equity) == pytest.approx(-0.5)


def test_max_drawdown_monotonic_up_is_zero():
    equity = pd.Series([100, 110, 120, 130])
    assert max_drawdown(equity) == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# win_rate
# --------------------------------------------------------------------------- #


def test_win_rate():
    trades = [{"pnl": 10}, {"pnl": -5}, {"pnl": 3}, {"pnl": -1}]
    assert win_rate(trades) == pytest.approx(0.5)


def test_win_rate_empty():
    assert win_rate([]) == 0.0


# --------------------------------------------------------------------------- #
# profit_factor
# --------------------------------------------------------------------------- #


def test_profit_factor():
    trades = [{"pnl": 100}, {"pnl": -50}, {"pnl": 50}]
    assert profit_factor(trades) == pytest.approx(3.0)


def test_profit_factor_no_losses_is_inf():
    trades = [{"pnl": 10}, {"pnl": 20}]
    assert profit_factor(trades) == float("inf")


# --------------------------------------------------------------------------- #
# sharpe_ratio
# --------------------------------------------------------------------------- #


def test_sharpe_zero_variance_is_zero():
    equity = pd.Series([100.0, 100.0, 100.0, 100.0])
    assert sharpe_ratio(equity) == 0.0


def test_sharpe_uses_365_annualization():
    equity = pd.Series([100.0, 101.0, 102.5, 101.5, 103.0, 104.0])
    returns = equity.pct_change().dropna()
    expected = returns.mean() / returns.std() * np.sqrt(365)
    assert sharpe_ratio(equity) == pytest.approx(expected)


def test_sharpe_positive_on_uptrend():
    equity = pd.Series(np.linspace(100, 200, 50) + np.random.RandomState(0).randn(50))
    assert sharpe_ratio(equity) > 0


# --------------------------------------------------------------------------- #
# buy_and_hold_metrics
# --------------------------------------------------------------------------- #


def test_buy_and_hold_total_return():
    dates = pd.date_range("2023-01-01", periods=11, freq="D")
    df = pd.DataFrame({"close": np.linspace(100, 200, 11)}, index=dates)
    result = buy_and_hold_metrics(df, initial_capital=10_000)
    assert result["total_return_pct"] == pytest.approx(100.0)
    assert result["final_capital_usd"] == pytest.approx(20_000.0)


# --------------------------------------------------------------------------- #
# summary
# --------------------------------------------------------------------------- #


def test_summary_keys():
    dates = pd.date_range("2023-01-01", periods=5, freq="D")
    equity = pd.DataFrame({"value": [10_000, 10_500, 10_200, 10_800, 11_000]}, index=dates)
    result = {
        "trades": [{"pnl": 500}, {"pnl": -300}, {"pnl": 800}],
        "equity_curve": equity,
        "final_capital": 11_000.0,
    }
    s = summary(result, initial_capital=10_000)
    for key in (
        "total_return_pct",
        "sharpe_ratio",
        "max_drawdown_pct",
        "win_rate_pct",
        "profit_factor",
        "total_trades",
        "final_capital_usd",
    ):
        assert key in s
    assert s["total_trades"] == 3


# --------------------------------------------------------------------------- #
# live_summary
# --------------------------------------------------------------------------- #


def test_live_summary_basic():
    trades = [{"pnl": 100.0}, {"pnl": -40.0}, {"pnl": 60.0}]
    portfolio_values = [10_000.0, 10_200.0, 10_120.0]

    result = live_summary(trades, portfolio_values)

    assert result["total_trades"] == 3
    assert result["win_rate_pct"] == pytest.approx(66.67, abs=0.01)
    assert result["profit_factor"] == pytest.approx(4.0)
    assert result["total_return_pct"] == pytest.approx(1.2)


def test_live_summary_handles_no_losses_and_empty():
    # Sin pérdidas -> profit_factor sería infinito; debe devolverse None (JSON-safe).
    assert live_summary([{"pnl": 10.0}], [10_000.0])["profit_factor"] is None
    # Sin datos -> todo a cero, sin errores.
    empty = live_summary([], [])
    assert empty["total_trades"] == 0
    assert empty["sharpe_ratio"] == 0.0
    assert empty["max_drawdown_pct"] == 0.0
