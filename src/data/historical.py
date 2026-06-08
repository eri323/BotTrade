"""Descarga de velas históricas vía Alpaca (CryptoHistoricalDataClient).

Ver skill `alpaca-integration`. El cliente se puede inyectar para tests.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame

from config.settings import settings


def get_crypto_data_client() -> CryptoHistoricalDataClient:
    """Cliente de datos de cripto. Las keys son opcionales para datos públicos."""
    return CryptoHistoricalDataClient(
        api_key=settings.ALPACA_API_KEY or None,
        secret_key=settings.ALPACA_SECRET_KEY or None,
    )


def fetch_daily_bars(
    symbol: str,
    start: datetime,
    end: datetime,
    client: CryptoHistoricalDataClient | None = None,
) -> pd.DataFrame:
    """Descarga velas diarias de un símbolo y devuelve un DataFrame plano.

    El SDK devuelve un MultiIndex (symbol, timestamp); aquí se aplana al símbolo
    pedido para que el resto del sistema trabaje con un índice temporal simple.
    """
    client = client or get_crypto_data_client()
    request = CryptoBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
    )
    bars = client.get_crypto_bars(request)
    df = bars.df
    if isinstance(df.index, pd.MultiIndex):
        df = df.loc[symbol].copy()
    return df
