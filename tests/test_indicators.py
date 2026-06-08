"""Tests de los indicadores técnicos (funciones puras) de src/features/indicators.py."""

import numpy as np
import pandas as pd
import pytest

from src.features.indicators import (
    atr,
    bollinger_pband,
    build_features,
    ema,
    pct_return,
    rsi,
)

# --------------------------------------------------------------------------- #
# ema
# --------------------------------------------------------------------------- #


def test_ema_of_constant_is_constant():
    """La EMA de una serie constante es esa misma constante."""
    s = pd.Series([5.0] * 20)
    result = ema(s, span=9)
    assert np.allclose(result.values, 5.0)


def test_ema_span_1_equals_series():
    """Con span=1 (alpha=1, adjust=False) la EMA es la propia serie."""
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    result = ema(s, span=1)
    pd.testing.assert_series_equal(result, s)


def test_ema_is_causal():
    """La EMA en el índice i no cambia si se añaden datos posteriores (sin look-ahead)."""
    s = pd.Series(np.arange(1, 51, dtype=float))
    full = ema(s, span=9)
    half = ema(s.iloc[:30], span=9)
    pd.testing.assert_series_equal(full.iloc[:30], half, rtol=1e-9)


# --------------------------------------------------------------------------- #
# rsi
# --------------------------------------------------------------------------- #


def test_rsi_within_0_100(sample_ohlcv):
    r = rsi(sample_ohlcv["close"], window=14).dropna()
    assert r.between(0, 100).all()


def test_rsi_high_on_uptrend():
    """En una subida monótona, el RSI tiende a valores altos (>70)."""
    s = pd.Series(np.linspace(100, 200, 60))
    r = rsi(s, window=14).dropna()
    assert r.iloc[-1] > 70


# --------------------------------------------------------------------------- #
# pct_return
# --------------------------------------------------------------------------- #


def test_pct_return_basic():
    s = pd.Series([100.0, 110.0, 99.0])
    r = pct_return(s, periods=1)
    assert r.iloc[1] == pytest.approx(0.10)
    assert r.iloc[2] == pytest.approx(-0.10)
    assert pd.isna(r.iloc[0])


# --------------------------------------------------------------------------- #
# atr
# --------------------------------------------------------------------------- #


def test_atr_non_negative(sample_ohlcv):
    a = atr(sample_ohlcv["high"], sample_ohlcv["low"], sample_ohlcv["close"], window=14)
    assert (a.dropna() >= 0).all()


# --------------------------------------------------------------------------- #
# bollinger_pband
# --------------------------------------------------------------------------- #


def test_bollinger_pband_high_near_upper_band():
    """Precio subiendo fuerte → %B alto (cerca o por encima de la banda superior)."""
    s = pd.Series(np.linspace(100, 200, 40))
    pb = bollinger_pband(s, window=20).dropna()
    assert pb.iloc[-1] > 0.8


# --------------------------------------------------------------------------- #
# build_features
# --------------------------------------------------------------------------- #


def test_build_features_rsi_range(sample_ohlcv):
    df = build_features(sample_ohlcv)
    assert df["rsi_14"].between(0, 100).all()


def test_build_features_ema_cross_binary(sample_ohlcv):
    df = build_features(sample_ohlcv)
    assert set(df["ema_cross"].unique()).issubset({0, 1})


def test_build_features_no_nan_after_dropna(sample_ohlcv):
    df = build_features(sample_ohlcv)
    assert df.isnull().sum().sum() == 0


def test_build_features_empty_on_short_input(sample_ohlcv):
    """Con muy pocas velas no se crashea (ta revienta): se devuelve un df vacío."""
    out = build_features(sample_ohlcv.iloc[:10])
    assert len(out) == 0


def test_build_features_no_future_data(sample_ohlcv):
    """
    Las features de una fila no deben depender de datos futuros.
    Recalcular sobre el df completo vs sobre un prefijo debe dar el mismo valor
    para las filas compartidas (cero look-ahead).
    """
    full = build_features(sample_ohlcv)
    prefix = build_features(sample_ohlcv.iloc[:60])

    common = full.index.intersection(prefix.index)
    cols = ["rsi_14", "ema_9", "ema_21", "atr_14", "bb_pct", "ret_1d", "vol_ratio"]
    for col in cols:
        pd.testing.assert_series_equal(
            full.loc[common, col], prefix.loc[common, col], rtol=1e-9, check_names=False
        )
