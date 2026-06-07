"""Fixtures compartidos de la suite de tests (ver skill `testing-pytest`)."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """DataFrame con velas OHLCV sintéticas (100 días)."""
    n = 100
    dates = pd.date_range(start="2023-01-01", periods=n, freq="D")
    np.random.seed(42)

    close = 30_000 + np.cumsum(np.random.randn(n) * 500)  # BTC sintético
    return pd.DataFrame(
        {
            "open": close * (1 + np.random.uniform(-0.005, 0.005, n)),
            "high": close * (1 + np.random.uniform(0, 0.01, n)),
            "low": close * (1 - np.random.uniform(0, 0.01, n)),
            "close": close,
            "volume": np.random.uniform(1000, 5000, n),
        },
        index=dates,
    )


@pytest.fixture
def trending_up_df() -> pd.DataFrame:
    """Mercado claramente alcista — debe generar señales BUY."""
    n = 60
    dates = pd.date_range(start="2023-01-01", periods=n, freq="D")
    close = np.linspace(20_000, 40_000, n)  # subida lineal
    return pd.DataFrame(
        {
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.98,
            "close": close,
            "volume": np.ones(n) * 2000,
        },
        index=dates,
    )


@pytest.fixture
def mock_trading_client(mocker):
    """Mock del TradingClient de Alpaca (cuenta con $10,000, sin posiciones)."""
    client = mocker.MagicMock()

    account = mocker.MagicMock()
    account.cash = "10000.00"
    account.portfolio_value = "10000.00"
    client.get_account.return_value = account

    client.get_all_positions.return_value = []
    client.get_open_position.side_effect = Exception("No position")

    return client
