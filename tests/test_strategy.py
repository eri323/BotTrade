"""Tests de la estrategia de reglas (baseline) en src/strategy/rule_based.py."""

import numpy as np
import pandas as pd

from src.features.indicators import build_features
from src.strategy.base import Strategy
from src.strategy.rule_based import RuleBasedStrategy


def _ohlcv_from_close(close: np.ndarray) -> pd.DataFrame:
    """Construye un OHLCV plausible a partir de una serie de cierres."""
    n = len(close)
    dates = pd.date_range(start="2023-01-01", periods=n, freq="D")
    return pd.DataFrame(
        {
            "open": close * 0.999,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(n, 2000.0),
        },
        index=dates,
    )


def _signals(strategy: Strategy, features: pd.DataFrame) -> list[str]:
    return [strategy.generate_signal(features.iloc[: i + 1]) for i in range(len(features))]


def test_rule_based_is_a_strategy():
    assert isinstance(RuleBasedStrategy(), Strategy)


def test_signal_only_valid_values(sample_ohlcv):
    features = build_features(sample_ohlcv)
    strategy = RuleBasedStrategy()
    valid = {"BUY", "SELL", "HOLD"}
    assert all(s in valid for s in _signals(strategy, features))


def test_hold_with_single_row():
    """Sin fila previa no se puede detectar un cruce → HOLD."""
    features = build_features(_ohlcv_from_close(np.linspace(100, 120, 40)))
    strategy = RuleBasedStrategy()
    assert strategy.generate_signal(features.iloc[:1]) == "HOLD"


def test_golden_cross_triggers_buy():
    """Caída y luego subida → EMA(9) cruza arriba de EMA(21) con RSI moderado → BUY."""
    close = np.concatenate([np.linspace(120, 100, 30), np.linspace(100, 160, 40)])
    features = build_features(_ohlcv_from_close(close))
    strategy = RuleBasedStrategy()
    assert "BUY" in _signals(strategy, features)


def test_uptrend_then_drop_triggers_sell():
    """Subida fuerte y luego caída → death cross o RSI alto → SELL."""
    close = np.concatenate([np.linspace(100, 180, 40), np.linspace(180, 110, 30)])
    features = build_features(_ohlcv_from_close(close))
    strategy = RuleBasedStrategy()
    assert "SELL" in _signals(strategy, features)
