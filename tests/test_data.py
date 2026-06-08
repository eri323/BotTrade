"""Tests de la descarga de datos históricos (src/data/historical.py).

No se llama nunca al API real: se inyecta un cliente mock.
"""

from datetime import datetime

import numpy as np
import pandas as pd

from src.data.historical import fetch_daily_bars


def _fake_multiindex_bars(symbol: str, n: int = 5) -> pd.DataFrame:
    ts = pd.date_range("2023-01-01", periods=n, freq="D")
    index = pd.MultiIndex.from_product([[symbol], ts], names=["symbol", "timestamp"])
    close = np.linspace(100, 110, n)
    return pd.DataFrame(
        {
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": np.full(n, 1000.0),
        },
        index=index,
    )


def test_fetch_daily_bars_flattens_single_symbol(mocker):
    client = mocker.MagicMock()
    bars = mocker.MagicMock()
    bars.df = _fake_multiindex_bars("BTC/USD", n=5)
    client.get_crypto_bars.return_value = bars

    out = fetch_daily_bars("BTC/USD", datetime(2023, 1, 1), datetime(2023, 1, 5), client=client)

    assert not isinstance(out.index, pd.MultiIndex)
    assert len(out) == 5
    assert {"open", "high", "low", "close", "volume"}.issubset(out.columns)
    client.get_crypto_bars.assert_called_once()
