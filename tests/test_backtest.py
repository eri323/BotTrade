"""Tests del backtester event-driven (src/backtest/engine.py)."""

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import BacktestEngine
from src.risk.manager import RiskManager
from src.strategy.base import Strategy


class ScriptedStrategy(Strategy):
    """Estrategia controlada: devuelve la señal correspondiente a cada vela."""

    def __init__(self, signals: list[str]) -> None:
        self.signals = list(signals)

    def generate_signal(self, df: pd.DataFrame) -> str:
        idx = len(df) - 1
        return self.signals[idx] if idx < len(self.signals) else "HOLD"


def _df(close: list[float], low: list[float] | None = None) -> pd.DataFrame:
    close_arr = np.array(close, dtype=float)
    low_arr = np.array(low, dtype=float) if low is not None else close_arr * 0.999
    n = len(close_arr)
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {
            "open": close_arr,
            "high": close_arr * 1.001,
            "low": low_arr,
            "close": close_arr,
            "volume": np.full(n, 1000.0),
        },
        index=dates,
    )


@pytest.fixture
def risk():
    return RiskManager(
        max_position_pct=0.20,
        stop_loss_pct=0.04,
        take_profit_pct=0.08,
        daily_loss_limit_pct=0.05,
        circuit_breaker_pct=0.20,
        max_concurrent_positions=2,
    )


def _engine(strategy, risk, **kw):
    # Por defecto sin fricción para asserts exactos; los tests de costos la activan.
    kw.setdefault("commission_pct", 0.0)
    kw.setdefault("slippage_pct", 0.0)
    return BacktestEngine(strategy, risk, initial_capital=10_000.0, **kw)


def test_result_has_expected_keys(risk):
    engine = _engine(ScriptedStrategy(["HOLD"] * 3), risk)
    result = engine.run(_df([100, 101, 102]))
    assert set(result) >= {"trades", "equity_curve", "final_capital"}
    assert list(result["equity_curve"].columns) == ["value"]


def test_all_hold_no_trades(risk):
    engine = _engine(ScriptedStrategy(["HOLD"] * 4), risk)
    result = engine.run(_df([100, 100, 100, 100]))
    assert result["trades"] == []
    assert result["final_capital"] == pytest.approx(10_000.0)
    assert len(result["equity_curve"]) == 4


def test_buy_then_hold_profits_on_rise(risk):
    engine = _engine(ScriptedStrategy(["BUY", "HOLD", "HOLD"]), risk)
    result = engine.run(_df([100, 100, 110]))
    buys = [t for t in result["trades"] if t["type"] == "BUY"]
    assert len(buys) == 1
    # 20% de 10k = 2000 → 20 unidades a 100. Al cerrar a 110: 8000 + 20*110 = 10200.
    assert result["final_capital"] == pytest.approx(10_200.0)


def test_stop_loss_exits_on_intraday_low(risk):
    engine = _engine(ScriptedStrategy(["BUY", "HOLD", "HOLD"]), risk)
    # El mínimo del día 3 (89) perfora el stop a -4% (96) → SELL_STOP.
    result = engine.run(_df([100, 100, 95], low=[99, 99, 89]))
    types = [t["type"] for t in result["trades"]]
    assert "BUY" in types
    assert "SELL_STOP" in types


def test_sell_signal_closes_position(risk):
    engine = _engine(ScriptedStrategy(["BUY", "HOLD", "SELL"]), risk)
    result = engine.run(_df([100, 100, 105], low=[99, 99, 104]))
    types = [t["type"] for t in result["trades"]]
    assert types == ["BUY", "SELL"]
    # 8000 + 20*105 = 10100
    assert result["final_capital"] == pytest.approx(10_100.0)


def test_no_double_buy_while_in_position(risk):
    engine = _engine(ScriptedStrategy(["BUY", "BUY", "HOLD"]), risk)
    result = engine.run(_df([100, 102, 104]))
    buys = [t for t in result["trades"] if t["type"] == "BUY"]
    assert len(buys) == 1


def test_commission_and_slippage_reduce_returns(risk):
    cheap = _engine(ScriptedStrategy(["BUY", "HOLD", "SELL"]), risk)
    costly = _engine(
        ScriptedStrategy(["BUY", "HOLD", "SELL"]),
        risk,
        commission_pct=0.01,
        slippage_pct=0.01,
    )
    df = _df([100, 100, 110], low=[99, 99, 109])
    assert costly.run(df)["final_capital"] < cheap.run(df)["final_capital"]
