"""Indicadores técnicos — funciones PURAS (sin estado, sin I/O, sin broker).

Fuente única de verdad de `build_features()`: el pipeline ML, el backtester y el
bot en vivo importan de aquí. Toda feature usa solo datos pasados o del momento
actual; nunca datos futuros (cero look-ahead).
"""

from __future__ import annotations

import pandas as pd
import ta


def ema(series: pd.Series, span: int) -> pd.Series:
    """Media móvil exponencial.

    `adjust=False`: la EMA depende solo del valor previo, no del largo del
    historial. Garantiza que sea idéntica en backtest y en el bot en vivo.
    """
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index (0–100)."""
    return ta.momentum.RSIIndicator(series, window=window).rsi()


def bollinger_pband(close: pd.Series, window: int = 20) -> pd.Series:
    """%B de Bollinger: posición relativa del precio dentro de las bandas.

    0 = banda inferior, 1 = banda superior (puede salirse de [0, 1]).
    """
    return ta.volatility.BollingerBands(close, window=window).bollinger_pband()


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """Average True Range — medida de volatilidad (siempre >= 0)."""
    return ta.volatility.AverageTrueRange(
        high=high, low=low, close=close, window=window
    ).average_true_range()


def pct_return(series: pd.Series, periods: int = 1) -> pd.Series:
    """Retorno porcentual respecto a `periods` velas atrás."""
    return series.pct_change(periods)


# Velas mínimas para calcular features sin que la librería `ta` falle y para que
# las ventanas más largas (ema_21, ret_20d) tengan sentido.
MIN_ROWS = 21


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Construye el set de features sobre velas OHLCV diarias.

    Devuelve el DataFrame con las features añadidas y sin filas con NaN
    (el periodo de warmup de los indicadores se descarta). Si hay menos de
    `MIN_ROWS` velas, devuelve un DataFrame vacío en vez de crashear.
    """
    if len(df) < MIN_ROWS:
        return df.iloc[0:0].copy()

    df = df.copy()

    # Momentum
    df["rsi_14"] = rsi(df["close"], window=14)

    # Tendencia
    df["ema_9"] = ema(df["close"], span=9)
    df["ema_21"] = ema(df["close"], span=21)
    df["ema_cross"] = (df["ema_9"] > df["ema_21"]).astype(int)

    # Volatilidad
    df["bb_pct"] = bollinger_pband(df["close"], window=20)
    df["atr_14"] = atr(df["high"], df["low"], df["close"], window=14)

    # Retornos pasados
    df["ret_1d"] = pct_return(df["close"], periods=1)
    df["ret_5d"] = pct_return(df["close"], periods=5)
    df["ret_20d"] = pct_return(df["close"], periods=20)

    # Volumen relativo
    df["vol_ratio"] = df["volume"] / df["volume"].rolling(20).mean()

    return df.dropna()
