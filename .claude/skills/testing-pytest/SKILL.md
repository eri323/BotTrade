---
name: testing-pytest
description: Patrones de testing del trading bot con pytest y pytest-mock. Usar siempre que se escriban o modifiquen tests, se mencione cobertura o QA, o se pruebe la lógica de estrategia, riesgo, indicadores, backtester o el wrapper del broker. Activar para mockear el API de Alpaca, para probar todas las reglas de gestión de riesgo, o para validar la ausencia de data leakage en el pipeline ML.
---

# Testing con pytest — Patrones del proyecto

## Setup base

```bash
pip install pytest pytest-mock pytest-cov
```

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--cov=src --cov-report=term-missing"

[tool.coverage.run]
omit = ["tests/*", "scripts/*"]
```

Correr todos los tests:
```bash
pytest --cov=src
```

---

## Principio fundamental: NUNCA llamar al API real en tests

Los tests deben ser:
- **Rápidos** (sin latencia de red).
- **Deterministas** (mismo resultado siempre).
- **Independientes** (no dependen de una cuenta de Alpaca activa).

Todo lo que toca `execution/broker.py` se mockea. Nunca se hace una llamada real a Alpaca en tests.

---

## Estructura de tests

```
tests/
├── conftest.py              # fixtures compartidos
├── test_indicators.py       # features/indicators.py
├── test_strategy.py         # strategy/rule_based.py, ml_strategy.py
├── test_risk.py             # risk/manager.py — cobertura EXHAUSTIVA
├── test_backtest.py         # backtest/engine.py + metrics.py
├── test_broker.py           # execution/broker.py con mocks de Alpaca
└── test_ml_pipeline.py      # models/train.py — anti-leakage y split
```

---

## conftest.py — fixtures compartidos

```python
# tests/conftest.py
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


@pytest.fixture
def sample_ohlcv():
    """DataFrame con velas OHLCV sintéticas (100 días)."""
    n = 100
    dates = pd.date_range(start="2023-01-01", periods=n, freq="D")
    np.random.seed(42)

    close = 30_000 + np.cumsum(np.random.randn(n) * 500)  # BTC sintético
    df = pd.DataFrame({
        "open":   close * (1 + np.random.uniform(-0.005, 0.005, n)),
        "high":   close * (1 + np.random.uniform(0, 0.01, n)),
        "low":    close * (1 - np.random.uniform(0, 0.01, n)),
        "close":  close,
        "volume": np.random.uniform(1000, 5000, n),
    }, index=dates)
    return df


@pytest.fixture
def trending_up_df():
    """Mercado claramente alcista — debe generar señales BUY."""
    n = 60
    dates = pd.date_range(start="2023-01-01", periods=n, freq="D")
    close = np.linspace(20_000, 40_000, n)  # subida lineal
    df = pd.DataFrame({
        "open": close * 0.99, "high": close * 1.01,
        "low":  close * 0.98, "close": close,
        "volume": np.ones(n) * 2000,
    }, index=dates)
    return df


@pytest.fixture
def mock_trading_client(mocker):
    """Mock del TradingClient de Alpaca."""
    client = mocker.MagicMock()

    # Simular cuenta con $10,000
    account = mocker.MagicMock()
    account.cash = "10000.00"
    account.portfolio_value = "10000.00"
    client.get_account.return_value = account

    # Sin posiciones iniciales
    client.get_all_positions.return_value = []
    client.get_open_position.side_effect = Exception("No position")

    return client
```

---

## test_indicators.py — funciones puras

```python
# tests/test_indicators.py
import pytest
import pandas as pd
import numpy as np
from src.features.indicators import build_features


def test_rsi_range(sample_ohlcv):
    """RSI siempre entre 0 y 100."""
    df = build_features(sample_ohlcv)
    assert df["rsi_14"].between(0, 100).all(), "RSI fuera de rango 0-100"


def test_ema_cross_binary(sample_ohlcv):
    """ema_cross solo toma valores 0 o 1."""
    df = build_features(sample_ohlcv)
    assert set(df["ema_cross"].unique()).issubset({0, 1})


def test_no_future_data_in_features(sample_ohlcv):
    """
    Las features de hoy no deben usar datos del mañana.
    Cortamos el df en dos mitades — las features de la primera mitad
    deben ser idénticas sin importar qué datos haya en la segunda.
    """
    df_full  = build_features(sample_ohlcv)
    df_half  = build_features(sample_ohlcv.iloc[:50])

    # Las features hasta el día 45 deben ser iguales en ambos casos
    # (margen de 5 por ventanas rolling de warmup)
    for col in ["rsi_14", "ema_9", "ema_21"]:
        pd.testing.assert_series_equal(
            df_full[col].iloc[20:45],
            df_half[col].iloc[20:45],
            check_names=False,
            rtol=1e-6
        )


def test_features_no_nan_after_warmup(sample_ohlcv):
    """No debe haber NaN después del periodo de warmup (21 días)."""
    df = build_features(sample_ohlcv)
    assert df.iloc[21:].isnull().sum().sum() == 0
```

---

## test_risk.py — cobertura EXHAUSTIVA (prioridad máxima)

```python
# tests/test_risk.py
import pytest
from src.risk.manager import RiskManager


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


class TestPositionSizing:
    def test_max_position_pct(self, risk):
        size = risk.calculate_position_size(capital=10_000)
        assert size == pytest.approx(2_000.0)  # 20% de 10,000

    def test_no_negative_size(self, risk):
        size = risk.calculate_position_size(capital=0)
        assert size == 0


class TestStopLoss:
    def test_triggers_at_threshold(self, risk):
        assert risk.should_stop_loss(pnl_pct=-0.04) is True

    def test_triggers_below_threshold(self, risk):
        assert risk.should_stop_loss(pnl_pct=-0.10) is True

    def test_does_not_trigger_above(self, risk):
        assert risk.should_stop_loss(pnl_pct=-0.03) is False

    def test_does_not_trigger_on_gain(self, risk):
        assert risk.should_stop_loss(pnl_pct=0.05) is False


class TestTakeProfit:
    def test_triggers_at_threshold(self, risk):
        assert risk.should_take_profit(pnl_pct=0.08) is True

    def test_does_not_trigger_below(self, risk):
        assert risk.should_take_profit(pnl_pct=0.05) is False


class TestDailyLossLimit:
    def test_halts_on_daily_loss(self, risk):
        # Simular que el día ya perdió 5%
        assert risk.daily_limit_reached(daily_pnl_pct=-0.05) is True

    def test_allows_trading_below_limit(self, risk):
        assert risk.daily_limit_reached(daily_pnl_pct=-0.03) is False


class TestCircuitBreaker:
    def test_triggers_on_drawdown(self, risk):
        assert risk.circuit_breaker_triggered(drawdown_pct=-0.20) is True

    def test_triggers_beyond_threshold(self, risk):
        assert risk.circuit_breaker_triggered(drawdown_pct=-0.35) is True

    def test_does_not_trigger_below(self, risk):
        assert risk.circuit_breaker_triggered(drawdown_pct=-0.15) is False


class TestMaxConcurrentPositions:
    def test_allows_below_limit(self, risk):
        assert risk.can_open_position(open_positions=1) is True

    def test_blocks_at_limit(self, risk):
        assert risk.can_open_position(open_positions=2) is False

    def test_blocks_above_limit(self, risk):
        assert risk.can_open_position(open_positions=5) is False
```

---

## test_broker.py — mocks del API de Alpaca

```python
# tests/test_broker.py
import pytest
from unittest.mock import MagicMock
from src.execution.broker import Broker


def test_submit_order_called_with_correct_params(mock_trading_client):
    broker = Broker(client=mock_trading_client)
    broker.buy("BTC/USD", notional=500.0)

    mock_trading_client.submit_order.assert_called_once()
    call_args = mock_trading_client.submit_order.call_args[0][0]
    assert call_args.symbol == "BTC/USD"
    assert float(call_args.notional) == 500.0


def test_no_duplicate_order_if_position_exists(mock_trading_client, mocker):
    """Si ya hay posición abierta, no debe enviar otra orden de compra."""
    existing_position = MagicMock()
    existing_position.symbol = "BTC/USD"
    mock_trading_client.get_open_position.return_value = existing_position

    broker = Broker(client=mock_trading_client)
    result = broker.buy("BTC/USD", notional=500.0)

    assert result is None
    mock_trading_client.submit_order.assert_not_called()


def test_handles_api_error_gracefully(mock_trading_client):
    """El broker maneja errores del API sin crashear el bot."""
    from alpaca.common.exceptions import APIError
    # ⚠️ La firma real es APIError(error, http_error=None) — NO acepta
    # status_code= ni message= como kwargs (eso lanzaría TypeError).
    # `error` es el cuerpo JSON como string. En tests no dependemos de
    # `.status_code` (sería None sin un http_error con .response).
    mock_trading_client.submit_order.side_effect = APIError(
        '{"code": 50010000, "message": "internal server error"}'
    )

    broker = Broker(client=mock_trading_client)
    result = broker.buy("BTC/USD", notional=500.0)

    assert result is None  # no crashea — retorna None y loguea el error
```

---

## test_strategy.py — señales de la estrategia

```python
# tests/test_strategy.py
import pytest
from src.strategy.rule_based import RuleBasedStrategy
from src.features.indicators import build_features


def test_buy_signal_in_uptrend(trending_up_df):
    """En mercado alcista claro, la estrategia debe generar al menos una señal BUY."""
    df = build_features(trending_up_df)
    strategy = RuleBasedStrategy()

    signals = [strategy.generate_signal(df.iloc[:i+1]) for i in range(30, len(df))]
    assert "BUY" in signals, "No generó señales BUY en mercado alcista"


def test_signal_only_valid_values(sample_ohlcv):
    """La estrategia solo puede retornar BUY, SELL o HOLD."""
    df = build_features(sample_ohlcv)
    strategy = RuleBasedStrategy()

    valid_signals = {"BUY", "SELL", "HOLD"}
    for i in range(30, len(df)):
        signal = strategy.generate_signal(df.iloc[:i+1])
        assert signal in valid_signals, f"Señal inválida: {signal}"
```

---

## test_ml_pipeline.py — anti-leakage

```python
# tests/test_ml_pipeline.py
import pytest
import pandas as pd
from src.features.indicators import build_features
from models.train import create_label


def test_label_uses_future_price(sample_ohlcv):
    """El label de hoy debe basarse en el precio de MAÑANA, no de hoy."""
    features = build_features(sample_ohlcv)
    df = create_label(features, threshold=0.01)

    # Regresión: la última fila (sin día siguiente) DEBE descartarse.
    # El bug era que (NaN > x).astype(int) daba 0 (no NaN), así que `dropna`
    # no la eliminaba y quedaba un label fantasma. El loop de abajo no lo
    # detectaba porque nunca compara la última fila contra un futuro inexistente.
    assert len(df) == len(features) - 1, "create_label debe descartar la última fila"

    # Verificar que label[i] = 1 si y solo si close[i+1] > close[i] * 1.01
    for i in range(len(df) - 1):
        expected = int(
            df["close"].iloc[i+1] > df["close"].iloc[i] * 1.01
        )
        actual = int(df["label"].iloc[i])
        assert actual == expected, f"Label incorrecto en fila {i}"


def test_temporal_split_no_overlap(sample_ohlcv):
    """Train y test no deben tener fechas en común."""
    from models.train import temporal_split
    df = build_features(sample_ohlcv)
    train, val, test = temporal_split(df)

    assert train.index.max() < val.index.min()
    assert val.index.max() < test.index.min()


def test_features_available_at_prediction_time(sample_ohlcv):
    """
    La feature de la fila i solo puede depender de datos hasta la fila i.
    Recalcular features sobre el df completo vs sobre el df hasta la fila i
    debe dar el mismo resultado para esa fila.
    """
    df = build_features(sample_ohlcv)

    # Tomar la fila 50 y verificar que el RSI es igual con y sin datos futuros
    rsi_con_futuro    = df["rsi_14"].iloc[50]
    rsi_sin_futuro    = build_features(sample_ohlcv.iloc[:51])["rsi_14"].iloc[50]

    assert abs(rsi_con_futuro - rsi_sin_futuro) < 1e-6, \
        "RSI difiere entre df completo y df truncado — posible look-ahead"
```

---

## Targets de cobertura

| Módulo | Cobertura mínima esperada |
|---|---|
| `risk/manager.py` | 100% — cada regla tiene su test |
| `features/indicators.py` | 95%+ — funciones puras, fáciles de testear |
| `strategy/rule_based.py` | 90%+ |
| `backtest/metrics.py` | 90%+ — verificar fórmulas numéricamente |
| `execution/broker.py` | 85%+ — con mocks |
| `bot/runner.py` | 70%+ — loop principal |

Correr con reporte:
```bash
pytest --cov=src --cov-report=html
# Abre htmlcov/index.html para ver cobertura línea por línea
```

---

## CI — GitHub Actions

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: ruff check .
      - run: pytest --cov=src
```

Cada push al repo debe pasar tests + linter en verde. Si falla, no se avanza.