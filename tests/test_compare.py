"""Tests de la comparativa de estrategias (src/backtest/compare.py)."""

from src.backtest.compare import run_comparison


def test_run_comparison_structure(sample_ohlcv):
    out = run_comparison(sample_ohlcv, initial_capital=10_000.0)

    assert set(out) == {"summary", "results"}
    assert "buy_hold" in out["summary"]
    assert "rules" in out["summary"]

    # buy_hold no pasa por el engine → no tiene equity_curve cruda
    assert "rules" in out["results"]
    assert "equity_curve" in out["results"]["rules"]

    # las métricas de buy_hold incluyen el retorno total
    assert "total_return_pct" in out["summary"]["buy_hold"]
    assert "sharpe_ratio" in out["summary"]["rules"]
