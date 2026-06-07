---
name: alpaca-integration
description: Guía de integración con Alpaca usando el SDK alpaca-py. Usar siempre que se trabaje con la conexión al broker, descarga de datos de mercado histórico o en vivo, envío o gestión de órdenes, o el wrapper en execution/broker.py. Activar ante errores de autenticación, configuración de paper vs live, símbolos de cripto, rate limits, reconexión del WebSocket, o idempotencia de órdenes.
---

# Integración con Alpaca — alpaca-py

## SDK correcto

**Usar `alpaca-py`** (SDK oficial actual).
**NO usar `alpaca-trade-api`** — está deprecado y puede dar comportamientos inesperados.

```bash
pip install alpaca-py
```

---

## Clientes disponibles

`alpaca-py` tiene clientes separados por función:

```python
from alpaca.trading.client import TradingClient          # órdenes y cuenta
from alpaca.data.historical import CryptoHistoricalDataClient  # datos históricos
from alpaca.data.live import CryptoDataStream            # stream en vivo (WebSocket)
```

---

## Inicialización — paper vs live

El flag `paper=True/False` es el ÚNICO cambio entre modos. Todo lo demás es idéntico.

```python
# config/settings.py
from alpaca.trading.client import TradingClient
from alpaca.data.historical import CryptoHistoricalDataClient

def get_trading_client() -> TradingClient:
    return TradingClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        paper=settings.PAPER  # True = paper, False = live
    )

def get_historical_client() -> CryptoHistoricalDataClient:
    return CryptoHistoricalDataClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY
    )
```

Las keys vienen de `.env` vía `config/settings.py`. **Nunca hardcodear.**

---

## Descarga de datos históricos (velas)

```python
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime

client = CryptoHistoricalDataClient(api_key, secret_key)

request = CryptoBarsRequest(
    symbol_or_symbols=["BTC/USD", "ETH/USD"],
    timeframe=TimeFrame.Day,         # velas diarias (swing)
    start=datetime(2019, 1, 1),
    end=datetime(2024, 12, 31)
)

bars = client.get_crypto_bars(request)
df = bars.df  # MultiIndex: (symbol, timestamp)

# Para trabajar con un solo símbolo:
btc_df = df.loc["BTC/USD"].copy()
```

**Símbolos de cripto en Alpaca:** formato `"BTC/USD"`, `"ETH/USD"` (con barra). No `"BTCUSD"` ni `"BTC"`.

---

## Stream de datos en vivo (WebSocket)

```python
from alpaca.data.live import CryptoDataStream

stream = CryptoDataStream(api_key, secret_key)

async def on_bar(bar):
    # se llama cada vez que llega una vela nueva
    print(f"{bar.symbol}: close={bar.close}")

stream.subscribe_bars(on_bar, "BTC/USD", "ETH/USD")
stream.run()
```

El stream corre en un event loop asyncio. El bot integra esto en `src/data/live.py`.

---

## Envío de órdenes

```python
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

client = TradingClient(api_key, secret_key, paper=True)

# Orden de mercado (compra)
order = MarketOrderRequest(
    symbol="BTC/USD",
    notional=100,            # USD a invertir (fraccional)
    # qty=0.001,             # alternativa: cantidad fija
    side=OrderSide.BUY,
    time_in_force=TimeInForce.GTC  # cripto: GTC; acciones: DAY
)
response = client.submit_order(order)
```

**`notional` vs `qty`:** para cripto fraccional, `notional` (en USD) es más práctico que `qty` en satoshis.

---

## Idempotencia de órdenes — CRÍTICO

El bot puede reiniciarse y no debe duplicar órdenes. Patrón:

```python
def submit_order_safe(client, symbol, notional, side):
    # 1. Verificar si ya hay posición abierta
    try:
        position = client.get_open_position(symbol)
        if side == OrderSide.BUY and position:
            return None  # ya tenemos posición, no duplicar
    except Exception:
        pass  # no hay posición, continuar

    # 2. Usar client_order_id único para idempotencia
    import uuid
    order = MarketOrderRequest(
        symbol=symbol,
        notional=notional,
        side=side,
        time_in_force=TimeInForce.GTC,
        client_order_id=str(uuid.uuid4())  # ID único por intento
    )
    return client.submit_order(order)
```

---

## Consulta de cuenta y posiciones

```python
# Balance y estado de la cuenta
account = client.get_account()
cash = float(account.cash)
portfolio_value = float(account.portfolio_value)

# Posiciones abiertas
positions = client.get_all_positions()
for pos in positions:
    print(f"{pos.symbol}: qty={pos.qty}, unrealized_pl={pos.unrealized_pl}")

# Una posición específica
try:
    pos = client.get_open_position("BTC/USD")
except Exception:
    # no hay posición abierta para ese símbolo
    pos = None

# Cerrar posición
client.close_position("BTC/USD")
```

---

## Manejo de errores y reconexión

```python
import time
from alpaca.common.exceptions import APIError

MAX_RETRIES = 3
RETRY_DELAY = 5  # segundos

def submit_with_retry(client, order_request, retries=MAX_RETRIES):
    for attempt in range(retries):
        try:
            return client.submit_order(order_request)
        except APIError as e:
            if e.status_code == 429:  # rate limit
                time.sleep(RETRY_DELAY * (attempt + 1))
            elif e.status_code in (403, 401):  # auth error
                raise  # no reintentar, requiere intervención
            else:
                if attempt == retries - 1:
                    raise
                time.sleep(RETRY_DELAY)
```

**Firma real de `APIError` (verificada en `alpaca/common/exceptions.py`):**
```python
class APIError(Exception):
    def __init__(self, error, http_error=None): ...
    @property
    def code(self): ...         # código numérico del cuerpo JSON: {"code": ...}
    @property
    def status_code(self): ...  # SOLO se rellena si el SDK adjuntó el http_error
```
- `e.status_code` funciona para errores **lanzados por el SDK** (el cliente adjunta el `http_error`), por eso el retry de arriba es válido.
- **No existe** `APIError(status_code=..., message=...)`. El constructor toma un `error` posicional (string/JSON) y un `http_error` opcional. Si construyes un `APIError` tú mismo (p. ej. en tests/mocks), `.status_code` será `None` salvo que pases un `http_error` con `.response` — por eso en los tests es mejor no depender de `.status_code` (ver skill `testing-pytest`).

**Rate limits de Alpaca:**
- REST API: 200 requests/minuto (plan free).
- WebSocket: reconectar con backoff exponencial ante desconexión.

---

## Diferencias paper vs live (a tener en cuenta)

| Aspecto | Paper | Live |
|---|---|---|
| Ejecución de órdenes | Al bid/ask exacto del momento | Precio real + slippage |
| Market impact | No existe | Tus órdenes grandes mueven el precio |
| Velocidad | Respuesta inmediata | Latencia real del exchange |
| Datos | Mismo feed de mercado real | Mismo feed de mercado real |

El paper no simula el slippage real. Cuando calcules métricas en paper, añade manualmente un slippage simulado de 0.1–0.2% por operación para tener una estimación más honesta.

---

## Variables de entorno necesarias

```bash
# .env
ALPACA_API_KEY=tu_key
ALPACA_SECRET_KEY=tu_secret
PAPER=true   # cambiar a false SOLO al pasar a live tras cumplir criterios
```

**Las keys del entorno paper y live son diferentes** — Alpaca genera un par de keys para cada entorno en el dashboard.
