# Dashboard web del trading bot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir una interfaz web local (localhost) para iniciar/detener el bot con botones y ver estado, cuenta, posiciones, historial, métricas y equity curve.

**Architecture:** Una capa web nueva en `src/web/` (FastAPI). El bot corre en un hilo de fondo gestionado por un `BotManager` singleton, con parada ordenada vía `threading.Event`. La capa web solo lee `Broker` y `Repository`; no duplica lógica de trading. Frontend sin build tooling (HTML/JS plano + Chart.js por CDN), servido como estáticos.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, pytest/pytest-mock, SQLite, Chart.js (CDN). Spec: `docs/superpowers/specs/2026-06-08-web-dashboard-design.md`.

---

## File Structure

- `src/bot/runner.py` (modificar): `run()` acepta `stop_event`; P&L real al cerrar; registrar `daily_metrics` por ciclo.
- `src/backtest/metrics.py` (modificar): añadir `live_summary()` (métricas del trading en vivo).
- `src/web/__init__.py` (crear): paquete.
- `src/web/bot_manager.py` (crear): ciclo de vida del bot (hilo + estado).
- `src/web/deps.py` (crear): proveedores inyectables (manager, broker, repository).
- `src/web/routes.py` (crear): endpoints JSON.
- `src/web/app.py` (crear): app FastAPI + montaje de estáticos.
- `src/web/static/index.html`, `app.js`, `style.css` (crear): dashboard.
- `scripts/run_dashboard.py` (crear): arranca uvicorn en localhost.
- `requirements.txt` (modificar): fastapi, uvicorn, httpx.
- `tests/test_bot.py` (modificar), `tests/test_metrics.py` (modificar), `tests/test_bot_manager.py` (crear), `tests/test_web_routes.py` (crear).

---

## Task 0: Rama de trabajo

- [ ] **Step 1: Crear y cambiar a la rama**

Estamos en `main`. Aísla el trabajo en una rama.

Run:
```bash
git checkout -b feat/web-dashboard
```
Expected: `Switched to a new branch 'feat/web-dashboard'`

---

## Task 1: Dependencias

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Añadir las dependencias web al final de `requirements.txt`**

Añade estas líneas (no borres las existentes):
```
fastapi>=0.110
uvicorn>=0.29
httpx>=0.27
```
(`httpx` lo necesita el `TestClient` de FastAPI/Starlette.)

- [ ] **Step 2: Instalar**

Run:
```bash
pip install -r requirements.txt
```
Expected: instala fastapi, uvicorn, httpx sin errores.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore(web): add fastapi, uvicorn, httpx deps" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `bot.run()` acepta señal de parada

**Files:**
- Modify: `src/bot/runner.py`
- Test: `tests/test_bot.py`

- [ ] **Step 1: Escribir los tests que fallan**

Añade al final de `tests/test_bot.py` (y `import threading` arriba del archivo):

```python
def test_run_stops_when_event_set(mocker, risk, repo, sample_ohlcv):
    broker = _broker(mocker, position=None)
    bot = _bot(broker, FixedStrategy("HOLD"), risk, repo)
    broker.get_account.return_value.portfolio_value = "10000.00"
    broker.get_account.return_value.last_equity = "10000.00"
    stop_event = threading.Event()
    calls = {"n": 0}

    def fetch(symbol):
        calls["n"] += 1
        stop_event.set()  # pedir parada tras el primer ciclo
        return sample_ohlcv

    bot.run(fetch, interval_seconds=0, stop_event=stop_event)

    assert calls["n"] == 1  # un símbolo, un ciclo, y para


def test_run_does_nothing_if_event_already_set(mocker, risk, repo, sample_ohlcv):
    broker = _broker(mocker, position=None)
    bot = _bot(broker, FixedStrategy("HOLD"), risk, repo)
    stop_event = threading.Event()
    stop_event.set()
    calls = {"n": 0}

    def fetch(symbol):
        calls["n"] += 1
        return sample_ohlcv

    bot.run(fetch, interval_seconds=0, stop_event=stop_event)

    assert calls["n"] == 0
```

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `pytest tests/test_bot.py::test_run_stops_when_event_set tests/test_bot.py::test_run_does_nothing_if_event_already_set -v`
Expected: FAIL (`run() got an unexpected keyword argument 'stop_event'`).

- [ ] **Step 3: Modificar `run()` en `src/bot/runner.py`**

Reemplaza el método `run` actual por:

```python
    def run(
        self,
        fetch: Callable[[str], pd.DataFrame],
        interval_seconds: int = 3600,
        stop_event: "threading.Event | None" = None,
    ) -> None:
        """Bucle continuo: procesa y duerme. Si se pasa `stop_event`, para de forma ordenada."""
        logger.info(f"Bot iniciado. Símbolos: {self.symbols}. Intervalo: {interval_seconds}s.")
        while stop_event is None or not stop_event.is_set():
            try:
                actions = self.run_once(fetch)
                logger.info(f"Ciclo completado: {actions}")
            except Exception as e:  # noqa: BLE001 — el loop no debe morir por un fallo puntual
                logger.exception(f"Error en el ciclo del bot: {e}")
            if stop_event is None:
                time.sleep(interval_seconds)
            elif stop_event.wait(interval_seconds):
                break
```

Añade el import arriba (junto a los otros imports estándar):
```python
import threading
```

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `pytest tests/test_bot.py -v`
Expected: PASS (todos, incluidos los previos).

- [ ] **Step 5: Commit**

```bash
git add src/bot/runner.py tests/test_bot.py
git commit -m "feat(bot): run() acepta stop_event para parada ordenada" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: P&L real al cerrar posiciones

**Files:**
- Modify: `src/bot/runner.py`
- Test: `tests/test_bot.py`

- [ ] **Step 1: Escribir el test que falla**

Añade a `tests/test_bot.py`:

```python
def test_sell_records_realized_pnl(mocker, risk, repo, sample_ohlcv):
    pos = mocker.MagicMock(unrealized_plpc="0.03", unrealized_pl="150.50", qty="0.01")
    broker = _broker(mocker, position=pos)
    bot = _bot(broker, FixedStrategy("SELL"), risk, repo)

    bot.process_symbol("BTC/USD", sample_ohlcv)

    assert repo.get_trades()[0]["pnl"] == pytest.approx(150.50)


def test_stop_loss_records_realized_pnl(mocker, risk, repo, sample_ohlcv):
    pos = mocker.MagicMock(unrealized_plpc="-0.05", unrealized_pl="-220.00", qty="0.01")
    broker = _broker(mocker, position=pos)
    bot = _bot(broker, FixedStrategy("HOLD"), risk, repo)

    bot.process_symbol("BTC/USD", sample_ohlcv)

    assert repo.get_trades()[0]["pnl"] == pytest.approx(-220.00)
```

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `pytest tests/test_bot.py::test_sell_records_realized_pnl tests/test_bot.py::test_stop_loss_records_realized_pnl -v`
Expected: FAIL (pnl == 0.0, no 150.50 / -220.00).

- [ ] **Step 3: Implementar en `src/bot/runner.py`**

Añade un helper a nivel de módulo (debajo de la constante `SELL_STOP`):

```python
def _to_float(value: object, default: float = 0.0) -> float:
    """Convierte a float de forma segura (Alpaca devuelve strings; un mock no convierte)."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
```

Cambia la firma de `_record` para aceptar `pnl`:

```python
    def _record(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        order_id: str | None = None,
        pnl: float = 0.0,
    ) -> None:
        self.repository.save_trade(
            timestamp=datetime.now(UTC).isoformat(),
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            pnl=pnl,
            order_id=order_id,
        )
```

En `process_symbol`, en el bloque de stop-loss, calcula y pasa el pnl:

```python
            if self.risk.should_stop_loss(pnl_pct):
                logger.warning(f"Stop-loss en {symbol} (P&L {pnl_pct:.2%}); cerrando.")
                realized_pnl = _to_float(getattr(position, "unrealized_pl", 0.0))
                self.broker.close_position(symbol)
                self._record(symbol, SELL_STOP, float(position.qty), last_price, pnl=realized_pnl)
                return SELL_STOP
```

Y en el bloque de la señal SELL:

```python
        if signal == SELL and position is not None:
            realized_pnl = _to_float(getattr(position, "unrealized_pl", 0.0))
            self.broker.close_position(symbol)
            self._record(symbol, SELL, float(position.qty), last_price, pnl=realized_pnl)
            logger.info(f"SELL {symbol} (señal de la estrategia).")
            return SELL
```

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `pytest tests/test_bot.py -v`
Expected: PASS (incluidos `test_sell_signal_closes_position` y `test_stop_loss_takes_priority_over_signal`, que siguen verdes porque sus mocks no fijan `unrealized_pl` y `_to_float` devuelve 0.0).

- [ ] **Step 5: Commit**

```bash
git add src/bot/runner.py tests/test_bot.py
git commit -m "feat(bot): registrar P&L realizado al cerrar posiciones" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Registrar `daily_metrics` por ciclo

**Files:**
- Modify: `src/bot/runner.py`
- Test: `tests/test_bot.py`

- [ ] **Step 1: Escribir el test que falla**

Añade a `tests/test_bot.py`:

```python
def test_run_once_records_daily_metric(mocker, risk, repo, sample_ohlcv):
    broker = _broker(mocker, position=None)
    broker.get_account.return_value.portfolio_value = "10500.00"
    broker.get_account.return_value.last_equity = "10000.00"
    bot = _bot(broker, FixedStrategy("HOLD"), risk, repo)

    bot.run_once(lambda symbol: sample_ohlcv)

    metrics = repo.get_daily_metrics()
    assert len(metrics) == 1
    assert metrics[0]["portfolio_value"] == pytest.approx(10500.0)
    assert metrics[0]["daily_pnl_pct"] == pytest.approx(0.05)


def test_daily_metric_drawdown_vs_peak(mocker, risk, repo, sample_ohlcv):
    broker = _broker(mocker, position=None)
    bot = _bot(broker, FixedStrategy("HOLD"), risk, repo)

    # Ciclo 1: pico en 10000
    broker.get_account.return_value.portfolio_value = "10000.00"
    broker.get_account.return_value.last_equity = "10000.00"
    bot.run_once(lambda symbol: sample_ohlcv)

    # Ciclo 2: cae a 9000 → drawdown -10%
    broker.get_account.return_value.portfolio_value = "9000.00"
    broker.get_account.return_value.last_equity = "10000.00"
    bot.run_once(lambda symbol: sample_ohlcv)

    metrics = repo.get_daily_metrics()
    assert metrics[1]["drawdown_pct"] == pytest.approx(-0.10)
```

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `pytest tests/test_bot.py::test_run_once_records_daily_metric tests/test_bot.py::test_daily_metric_drawdown_vs_peak -v`
Expected: FAIL (`daily_metrics` vacío).

- [ ] **Step 3: Implementar en `src/bot/runner.py`**

Añade el método `_record_daily_metric` a `TradingBot`:

```python
    def _record_daily_metric(self) -> None:
        """Guarda el valor del portafolio, P&L del día y drawdown vs pico histórico."""
        account = self.broker.get_account()
        portfolio_value = _to_float(getattr(account, "portfolio_value", 0.0))
        last_equity = _to_float(getattr(account, "last_equity", None), portfolio_value)
        daily_pnl_pct = (portfolio_value - last_equity) / last_equity if last_equity else 0.0

        history = [m["portfolio_value"] for m in self.repository.get_daily_metrics()]
        peak = max(history + [portfolio_value]) if (history or portfolio_value) else portfolio_value
        drawdown_pct = (portfolio_value - peak) / peak if peak else 0.0

        self.repository.save_daily_metric(
            date=datetime.now(UTC).date().isoformat(),
            portfolio_value=portfolio_value,
            daily_pnl_pct=daily_pnl_pct,
            drawdown_pct=drawdown_pct,
        )
```

Cambia `run_once` para llamarlo tras procesar los símbolos:

```python
    def run_once(self, fetch: Callable[[str], pd.DataFrame]) -> dict[str, str]:
        """Procesa todos los símbolos una vez. `fetch(symbol) -> df_raw`."""
        actions = {symbol: self.process_symbol(symbol, fetch(symbol)) for symbol in self.symbols}
        self._record_daily_metric()
        return actions
```

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `pytest tests/test_bot.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bot/runner.py tests/test_bot.py
git commit -m "feat(bot): registrar daily_metrics (valor, P&L, drawdown) por ciclo" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Métricas del trading en vivo (`live_summary`)

**Files:**
- Modify: `src/backtest/metrics.py`
- Test: `tests/test_metrics.py`

- [ ] **Step 1: Escribir el test que falla**

Añade a `tests/test_metrics.py` (y `from src.backtest.metrics import live_summary` arriba):

```python
def test_live_summary_basic():
    trades = [{"pnl": 100.0}, {"pnl": -40.0}, {"pnl": 60.0}]
    portfolio_values = [10_000.0, 10_200.0, 10_120.0]

    result = live_summary(trades, portfolio_values)

    assert result["total_trades"] == 3
    assert result["win_rate_pct"] == pytest.approx(66.67, abs=0.01)
    assert result["profit_factor"] == pytest.approx(4.0)
    assert result["total_return_pct"] == pytest.approx(1.2)


def test_live_summary_handles_no_losses_and_empty():
    # Sin pérdidas → profit_factor sería infinito; debe devolverse None (JSON-safe).
    assert live_summary([{"pnl": 10.0}], [10_000.0])["profit_factor"] is None
    # Sin datos → todo a cero, sin errores.
    empty = live_summary([], [])
    assert empty["total_trades"] == 0
    assert empty["sharpe_ratio"] == 0.0
    assert empty["max_drawdown_pct"] == 0.0
```

- [ ] **Step 2: Ejecutar y verificar que fallan**

Run: `pytest tests/test_metrics.py::test_live_summary_basic tests/test_metrics.py::test_live_summary_handles_no_losses_and_empty -v`
Expected: FAIL (`cannot import name 'live_summary'`).

- [ ] **Step 3: Implementar en `src/backtest/metrics.py`**

Añade al final del archivo:

```python
def live_summary(trades: list[dict], portfolio_values: list[float]) -> dict:
    """Métricas del trading en vivo a partir de trades (con pnl) y la serie de valor del portafolio.

    `profit_factor` se devuelve como None cuando sería infinito (no hay pérdidas),
    para que el resultado sea serializable a JSON.
    """
    pf = profit_factor(trades)
    result = {
        "win_rate_pct": round(win_rate(trades) * 100, 2),
        "profit_factor": None if pf == float("inf") else round(pf, 3),
        "total_trades": len(trades),
        "total_return_pct": 0.0,
        "sharpe_ratio": 0.0,
        "max_drawdown_pct": 0.0,
    }
    if len(portfolio_values) >= 1:
        equity = pd.Series(portfolio_values, dtype="float64")
        result["max_drawdown_pct"] = round(max_drawdown(equity) * 100, 2)
    if len(portfolio_values) >= 2:
        equity = pd.Series(portfolio_values, dtype="float64")
        result["sharpe_ratio"] = round(sharpe_ratio(equity), 3)
        result["total_return_pct"] = round(
            total_return(portfolio_values[0], portfolio_values[-1]) * 100, 2
        )
    return result
```

- [ ] **Step 4: Ejecutar y verificar que pasan**

Run: `pytest tests/test_metrics.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/backtest/metrics.py tests/test_metrics.py
git commit -m "feat(metrics): live_summary para métricas del trading en vivo" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: `BotManager` (ciclo de vida del bot)

**Files:**
- Create: `src/web/__init__.py`
- Create: `src/web/bot_manager.py`
- Test: `tests/test_bot_manager.py`

- [ ] **Step 1: Crear el paquete**

Crea `src/web/__init__.py` vacío:
```python
```

- [ ] **Step 2: Escribir los tests que fallan**

Crea `tests/test_bot_manager.py`:

```python
"""Tests del ciclo de vida del bot (src/web/bot_manager.py).

Bot y broker mockeados; no se toca Alpaca. El bot falso bloquea hasta que se
activa el stop_event, imitando el loop real.
"""

import pytest

from src.web.bot_manager import BotManager


class _FakeBot:
    def __init__(self):
        self.run_calls = 0

    def run(self, fetch, interval_seconds, stop_event):
        self.run_calls += 1
        stop_event.wait()  # bloquea hasta que se pida parada


def test_start_then_stop(mocker):
    broker = mocker.MagicMock()
    broker.list_positions.return_value = []
    bot = _FakeBot()
    mgr = BotManager(bot_factory=lambda: (bot, broker))

    assert not mgr.is_running()
    mgr.start()
    assert mgr.is_running()

    result = mgr.stop()
    assert not mgr.is_running()
    assert bot.run_calls == 1
    assert result["running"] is False


def test_start_is_idempotent(mocker):
    broker = mocker.MagicMock()
    broker.list_positions.return_value = []
    bot = _FakeBot()
    mgr = BotManager(bot_factory=lambda: (bot, broker))

    mgr.start()
    mgr.start()  # segunda llamada no relanza
    mgr.stop()

    assert bot.run_calls == 1


def test_stop_closes_positions_when_requested(mocker):
    pos = mocker.MagicMock(symbol="BTC/USD")
    broker = mocker.MagicMock()
    broker.list_positions.return_value = [pos]
    mgr = BotManager(bot_factory=lambda: (_FakeBot(), broker))

    mgr.start()
    result = mgr.stop(close_positions=True)

    broker.close_position.assert_called_once_with("BTC/USD")
    assert result["closed_positions"] == ["BTC/USD"]


def test_stop_leaves_positions_by_default(mocker):
    pos = mocker.MagicMock(symbol="BTC/USD")
    broker = mocker.MagicMock()
    broker.list_positions.return_value = [pos]
    mgr = BotManager(bot_factory=lambda: (_FakeBot(), broker))

    mgr.start()
    mgr.stop(close_positions=False)

    broker.close_position.assert_not_called()


def test_start_live_requires_confirmation(mocker):
    fake_settings = mocker.MagicMock(PAPER=False, SYMBOLS=["BTC/USD"])
    mocker.patch("src.web.bot_manager.settings", fake_settings)
    mgr = BotManager(bot_factory=lambda: (_FakeBot(), mocker.MagicMock()))

    with pytest.raises(PermissionError):
        mgr.start()


def test_status_reports_state(mocker):
    broker = mocker.MagicMock()
    broker.list_positions.return_value = []
    mgr = BotManager(bot_factory=lambda: (_FakeBot(), broker))

    status = mgr.status()
    assert status["running"] is False
    assert status["mode"] in {"PAPER", "LIVE"}
    assert "symbols" in status
```

- [ ] **Step 3: Ejecutar y verificar que fallan**

Run: `pytest tests/test_bot_manager.py -v`
Expected: FAIL (`No module named 'src.web.bot_manager'`).

- [ ] **Step 4: Implementar `src/web/bot_manager.py`**

```python
"""Ciclo de vida del bot para la capa web — corre el loop en un hilo de fondo.

Singleton de la app: arranca/detiene el bot con parada ordenada vía threading.Event.
No conoce Alpaca directamente; usa Broker (única capa que sí lo conoce).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pandas as pd
from loguru import logger

from config.settings import settings
from src.backtest.compare import default_risk
from src.bot.runner import TradingBot
from src.data.historical import fetch_daily_bars
from src.execution.broker import Broker
from src.persistence.db import get_connection, init_db
from src.persistence.repository import Repository
from src.strategy.rule_based import RuleBasedStrategy


class BotManager:
    """Controla el ciclo de vida del bot en un hilo de fondo."""

    def __init__(
        self,
        *,
        bot_factory: Callable[[], tuple[TradingBot, Broker]] | None = None,
        interval_seconds: int = 86_400,
        lookback_days: int = 200,
    ) -> None:
        self._bot_factory = bot_factory or self._build_bot
        self._interval_seconds = interval_seconds
        self._lookback_days = lookback_days
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._bot: TradingBot | None = None
        self._broker: Broker | None = None
        self._error: str | None = None

    def _build_bot(self) -> tuple[TradingBot, Broker]:
        broker = Broker()
        conn = get_connection()
        init_db(conn)
        repo = Repository(conn)
        bot = TradingBot(
            broker, RuleBasedStrategy(), default_risk(), repo, symbols=settings.SYMBOLS
        )
        return bot, broker

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, *, confirm_live: bool = False) -> dict:
        if self.is_running():
            return {"running": True, "message": "El bot ya estaba corriendo."}
        if not settings.PAPER and not confirm_live:
            raise PermissionError("PAPER=false (live) requiere confirmación explícita.")

        self._stop_event.clear()
        self._error = None
        self._bot, self._broker = self._bot_factory()

        def _fetch(symbol: str) -> pd.DataFrame:
            end = datetime.now(UTC)
            start = end - timedelta(days=self._lookback_days)
            return fetch_daily_bars(symbol, start, end)

        def _loop() -> None:
            try:
                self._bot.run(
                    _fetch,
                    interval_seconds=self._interval_seconds,
                    stop_event=self._stop_event,
                )
            except Exception as e:  # noqa: BLE001 — el hilo no debe morir en silencio
                self._error = str(e)
                logger.exception(f"El loop del bot terminó con error: {e}")

        self._thread = threading.Thread(target=_loop, daemon=True, name="trading-bot")
        self._thread.start()
        return {"running": True, "message": "Bot iniciado."}

    def stop(self, *, close_positions: bool = False, timeout: float = 30.0) -> dict:
        if not self.is_running():
            return {"running": False, "message": "El bot no estaba corriendo."}

        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

        closed: list[str] = []
        if close_positions and self._broker is not None:
            for position in self._broker.list_positions():
                self._broker.close_position(position.symbol)
                closed.append(position.symbol)

        return {
            "running": self.is_running(),
            "closed_positions": closed,
            "message": "Bot detenido.",
        }

    def status(self) -> dict:
        return {
            "running": self.is_running(),
            "mode": "PAPER" if settings.PAPER else "LIVE",
            "symbols": list(settings.SYMBOLS),
            "interval_seconds": self._interval_seconds,
            "error": self._error,
        }
```

- [ ] **Step 5: Ejecutar y verificar que pasan**

Run: `pytest tests/test_bot_manager.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/web/__init__.py src/web/bot_manager.py tests/test_bot_manager.py
git commit -m "feat(web): BotManager para iniciar/detener el bot en un hilo" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: App FastAPI + endpoints

**Files:**
- Create: `src/web/deps.py`
- Create: `src/web/routes.py`
- Create: `src/web/app.py`
- Test: `tests/test_web_routes.py`

- [ ] **Step 1: Crear los proveedores inyectables `src/web/deps.py`**

```python
"""Proveedores inyectables para la capa web (overridables en tests vía dependency_overrides)."""

from __future__ import annotations

from src.execution.broker import Broker
from src.persistence.db import get_connection, init_db
from src.persistence.repository import Repository
from src.web.bot_manager import BotManager

_manager = BotManager(interval_seconds=86_400)


def get_manager() -> BotManager:
    return _manager


def get_broker() -> Broker:
    return Broker()


def get_repository() -> Repository:
    conn = get_connection()
    init_db(conn)
    return Repository(conn)
```

- [ ] **Step 2: Crear los endpoints `src/web/routes.py`**

```python
"""Endpoints JSON del dashboard. Solo leen Broker y Repository; no operan el mercado."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.backtest.metrics import live_summary
from src.execution.broker import Broker
from src.persistence.repository import Repository
from src.web.bot_manager import BotManager
from src.web.deps import get_broker, get_manager, get_repository

router = APIRouter()


@router.get("/status")
def status(manager: BotManager = Depends(get_manager)) -> dict:
    return manager.status()


@router.post("/start")
def start(confirm_live: bool = False, manager: BotManager = Depends(get_manager)) -> dict:
    try:
        return manager.start(confirm_live=confirm_live)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router.post("/stop")
def stop(close_positions: bool = False, manager: BotManager = Depends(get_manager)) -> dict:
    return manager.stop(close_positions=close_positions)


@router.get("/account")
def account(broker: Broker = Depends(get_broker)) -> dict:
    acct = broker.get_account()
    portfolio_value = float(acct.portfolio_value)
    return {
        "portfolio_value": portfolio_value,
        "cash": float(acct.cash),
        "last_equity": float(getattr(acct, "last_equity", None) or portfolio_value),
    }


@router.get("/positions")
def positions(broker: Broker = Depends(get_broker)) -> list[dict]:
    return [
        {
            "symbol": p.symbol,
            "qty": float(p.qty),
            "avg_entry_price": float(p.avg_entry_price),
            "unrealized_pl": float(p.unrealized_pl),
            "unrealized_plpc": float(p.unrealized_plpc),
        }
        for p in broker.list_positions()
    ]


@router.get("/trades")
def trades(repo: Repository = Depends(get_repository)) -> list[dict]:
    return repo.get_trades()


@router.get("/equity")
def equity(repo: Repository = Depends(get_repository)) -> list[dict]:
    return repo.get_daily_metrics()


@router.get("/metrics")
def metrics(repo: Repository = Depends(get_repository)) -> dict:
    portfolio_values = [m["portfolio_value"] for m in repo.get_daily_metrics()]
    return live_summary(repo.get_trades(), portfolio_values)
```

- [ ] **Step 3: Crear la app `src/web/app.py`**

```python
"""App FastAPI: monta la API en /api y sirve el dashboard estático en /."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.web.routes import router

_STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="Trading Bot Dashboard")
    app.include_router(router, prefix="/api")
    # check_dir=False: el directorio estático puede no existir aún en tests de la API.
    app.mount(
        "/", StaticFiles(directory=str(_STATIC_DIR), html=True, check_dir=False), name="static"
    )
    return app


app = create_app()
```

- [ ] **Step 4: Escribir los tests `tests/test_web_routes.py`**

```python
"""Tests de los endpoints (src/web/routes.py) con TestClient y dependencias mockeadas."""

import pytest
from fastapi.testclient import TestClient

from src.persistence.db import get_connection, init_db
from src.persistence.repository import Repository
from src.web import deps
from src.web.app import create_app


@pytest.fixture
def client(mocker):
    app = create_app()
    yield app, mocker
    app.dependency_overrides.clear()


def test_status_endpoint(client):
    app, mocker = client
    manager = mocker.MagicMock()
    manager.status.return_value = {"running": False, "mode": "PAPER", "symbols": ["BTC/USD"]}
    app.dependency_overrides[deps.get_manager] = lambda: manager

    resp = TestClient(app).get("/api/status")

    assert resp.status_code == 200
    assert resp.json()["running"] is False


def test_start_endpoint(client):
    app, mocker = client
    manager = mocker.MagicMock()
    manager.start.return_value = {"running": True, "message": "Bot iniciado."}
    app.dependency_overrides[deps.get_manager] = lambda: manager

    resp = TestClient(app).post("/api/start")

    assert resp.status_code == 200
    assert resp.json()["running"] is True
    manager.start.assert_called_once()


def test_stop_endpoint_with_close_positions(client):
    app, mocker = client
    manager = mocker.MagicMock()
    manager.stop.return_value = {"running": False, "closed_positions": ["BTC/USD"]}
    app.dependency_overrides[deps.get_manager] = lambda: manager

    resp = TestClient(app).post("/api/stop?close_positions=true")

    assert resp.status_code == 200
    manager.stop.assert_called_once_with(close_positions=True)


def test_start_live_without_confirmation_returns_403(client):
    app, mocker = client
    manager = mocker.MagicMock()
    manager.start.side_effect = PermissionError("live requiere confirmación")
    app.dependency_overrides[deps.get_manager] = lambda: manager

    resp = TestClient(app).post("/api/start")

    assert resp.status_code == 403


def test_account_endpoint(client):
    app, mocker = client
    broker = mocker.MagicMock()
    acct = mocker.MagicMock()
    acct.portfolio_value = "10500.00"
    acct.cash = "3000.00"
    acct.last_equity = "10000.00"
    broker.get_account.return_value = acct
    app.dependency_overrides[deps.get_broker] = lambda: broker

    resp = TestClient(app).get("/api/account")

    assert resp.status_code == 200
    assert resp.json()["portfolio_value"] == pytest.approx(10500.0)


def test_positions_endpoint(client):
    app, mocker = client
    broker = mocker.MagicMock()
    pos = mocker.MagicMock(
        symbol="BTC/USD",
        qty="0.05",
        avg_entry_price="60000",
        unrealized_pl="120.0",
        unrealized_plpc="0.04",
    )
    broker.list_positions.return_value = [pos]
    app.dependency_overrides[deps.get_broker] = lambda: broker

    resp = TestClient(app).get("/api/positions")

    assert resp.status_code == 200
    assert resp.json()[0]["symbol"] == "BTC/USD"


def test_trades_and_metrics_endpoints(client):
    app, mocker = client
    conn = get_connection(":memory:")
    init_db(conn)
    repo = Repository(conn)
    repo.save_trade(timestamp="2026-06-07T14:00:00", symbol="BTC/USD", side="SELL",
                    qty=0.01, price=2410.0, pnl=32.0)
    repo.save_daily_metric(date="2026-06-06", portfolio_value=10_000.0)
    repo.save_daily_metric(date="2026-06-07", portfolio_value=10_320.0)
    app.dependency_overrides[deps.get_repository] = lambda: repo

    c = TestClient(app)
    assert len(c.get("/api/trades").json()) == 1
    metrics = c.get("/api/metrics").json()
    assert metrics["total_trades"] == 1
    assert metrics["win_rate_pct"] == 100.0

    conn.close()
```

- [ ] **Step 5: Ejecutar y verificar que pasan**

Run: `pytest tests/test_web_routes.py -v`
Expected: PASS (todos los endpoints responden 200 con los datos esperados).

- [ ] **Step 6: Commit**

```bash
git add src/web/deps.py src/web/routes.py src/web/app.py tests/test_web_routes.py
git commit -m "feat(web): app FastAPI con endpoints de status, cuenta, trades y métricas" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: Frontend (dashboard de una sola página)

**Files:**
- Create: `src/web/static/index.html`
- Create: `src/web/static/style.css`
- Create: `src/web/static/app.js`

No hay test automático: se valida a mano en el navegador (Step 4).

- [ ] **Step 1: Crear `src/web/static/index.html`**

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Trading Bot</title>
  <link rel="stylesheet" href="/style.css" />
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
</head>
<body>
  <header class="topbar">
    <div class="brand">🤖 Trading Bot</div>
    <div class="topbar-right">
      <span id="mode" class="badge">—</span>
      <span id="state" class="state">●</span>
      <button id="btn-start" class="btn btn-start">▶ Iniciar</button>
      <button id="btn-stop" class="btn btn-stop">■ Detener</button>
    </div>
  </header>

  <section class="cards">
    <div class="card"><span class="card-label">Portafolio</span><span id="portfolio" class="card-value">—</span></div>
    <div class="card"><span class="card-label">Efectivo</span><span id="cash" class="card-value">—</span></div>
    <div class="card"><span class="card-label">P&L hoy</span><span id="pnl-today" class="card-value">—</span></div>
    <div class="card"><span class="card-label">P&L total</span><span id="pnl-total" class="card-value">—</span></div>
  </section>

  <section class="panel"><h2>Equity curve</h2><canvas id="equity-chart" height="90"></canvas></section>

  <div class="two-col">
    <section class="panel">
      <h2>Posiciones abiertas</h2>
      <table><thead><tr><th>Símbolo</th><th>Cant.</th><th>Entrada</th><th>P&L</th></tr></thead>
        <tbody id="positions-body"></tbody></table>
    </section>
    <section class="panel">
      <h2>Métricas</h2>
      <table><tbody id="metrics-body"></tbody></table>
    </section>
  </div>

  <section class="panel">
    <h2>Historial de trades</h2>
    <table><thead><tr><th>Fecha</th><th>Símbolo</th><th>Lado</th><th>Precio</th><th>P&L</th></tr></thead>
      <tbody id="trades-body"></tbody></table>
  </section>

  <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Crear `src/web/static/style.css`**

```css
:root {
  --bg: #0f1419; --panel: #1a2029; --border: #2a323d;
  --text: #e6edf3; --muted: #8b949e; --green: #3fb950; --red: #f85149; --accent: #58a6ff;
}
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); }
.topbar { display: flex; justify-content: space-between; align-items: center;
  padding: 14px 20px; background: var(--panel); border-bottom: 1px solid var(--border); }
.brand { font-weight: 600; font-size: 18px; }
.topbar-right { display: flex; align-items: center; gap: 12px; }
.badge { padding: 3px 10px; border-radius: 12px; background: #1f6feb33; color: var(--accent); font-size: 13px; }
.state { font-size: 14px; color: var(--muted); }
.state.on { color: var(--green); } .state.off { color: var(--red); }
.btn { border: none; border-radius: 6px; padding: 8px 14px; cursor: pointer; font-size: 14px; color: #fff; }
.btn-start { background: var(--green); } .btn-stop { background: var(--red); }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; padding: 20px; }
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 16px;
  display: flex; flex-direction: column; gap: 6px; }
.card-label { color: var(--muted); font-size: 13px; } .card-value { font-size: 22px; font-weight: 600; }
.panel { background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
  margin: 0 20px 20px; padding: 16px; }
.panel h2 { margin: 0 0 12px; font-size: 15px; color: var(--muted); font-weight: 600; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 0; }
.two-col .panel { margin-right: 10px; } .two-col .panel:last-child { margin-left: 10px; margin-right: 20px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 8px 6px; border-bottom: 1px solid var(--border); }
th { color: var(--muted); font-weight: 500; }
.pos { color: var(--green); } .neg { color: var(--red); }
```

- [ ] **Step 3: Crear `src/web/static/app.js`**

```javascript
const $ = (id) => document.getElementById(id);
const fmtUsd = (n) => "$" + Number(n).toLocaleString("en-US", { maximumFractionDigits: 2 });
const fmtPct = (n) => (n >= 0 ? "+" : "") + Number(n).toFixed(2) + "%";
const cls = (n) => (n >= 0 ? "pos" : "neg");

async function getJSON(url) { const r = await fetch(url); return r.json(); }
async function post(url) { return fetch(url, { method: "POST" }); }

let equityChart = null;

async function refresh() {
  const status = await getJSON("/api/status");
  $("mode").textContent = status.mode;
  $("state").textContent = status.running ? "● Corriendo" : "● Detenido";
  $("state").className = "state " + (status.running ? "on" : "off");
  $("btn-start").disabled = status.running;
  $("btn-stop").disabled = !status.running;

  const acct = await getJSON("/api/account");
  $("portfolio").textContent = fmtUsd(acct.portfolio_value);
  $("cash").textContent = fmtUsd(acct.cash);
  const today = ((acct.portfolio_value - acct.last_equity) / acct.last_equity) * 100;
  $("pnl-today").textContent = fmtPct(today);
  $("pnl-today").className = "card-value " + cls(today);

  const metrics = await getJSON("/api/metrics");
  $("pnl-total").textContent = fmtPct(metrics.total_return_pct);
  $("pnl-total").className = "card-value " + cls(metrics.total_return_pct);
  $("metrics-body").innerHTML = `
    <tr><td>Win rate</td><td>${metrics.win_rate_pct}%</td></tr>
    <tr><td>Profit factor</td><td>${metrics.profit_factor ?? "∞"}</td></tr>
    <tr><td>Sharpe</td><td>${metrics.sharpe_ratio}</td></tr>
    <tr><td>Max drawdown</td><td>${metrics.max_drawdown_pct}%</td></tr>
    <tr><td>Trades</td><td>${metrics.total_trades}</td></tr>`;

  const positions = await getJSON("/api/positions");
  $("positions-body").innerHTML = positions.map((p) => {
    const pct = p.unrealized_plpc * 100;
    return `<tr><td>${p.symbol}</td><td>${p.qty}</td><td>${fmtUsd(p.avg_entry_price)}</td>
      <td class="${cls(pct)}">${fmtPct(pct)}</td></tr>`;
  }).join("") || `<tr><td colspan="4">Sin posiciones abiertas</td></tr>`;

  const trades = await getJSON("/api/trades");
  $("trades-body").innerHTML = trades.slice().reverse().map((t) => `
    <tr><td>${t.timestamp.slice(0, 16).replace("T", " ")}</td><td>${t.symbol}</td>
      <td>${t.side}</td><td>${fmtUsd(t.price)}</td>
      <td class="${cls(t.pnl)}">${t.pnl ? fmtUsd(t.pnl) : "—"}</td></tr>`).join("")
    || `<tr><td colspan="5">Sin trades todavía</td></tr>`;

  const equity = await getJSON("/api/equity");
  const labels = equity.map((e) => e.date);
  const values = equity.map((e) => e.portfolio_value);
  if (!equityChart) {
    equityChart = new Chart($("equity-chart"), {
      type: "line",
      data: { labels, datasets: [{ data: values, borderColor: "#58a6ff", tension: 0.2, pointRadius: 0 }] },
      options: { plugins: { legend: { display: false } }, scales: { x: { ticks: { color: "#8b949e" } }, y: { ticks: { color: "#8b949e" } } } },
    });
  } else {
    equityChart.data.labels = labels;
    equityChart.data.datasets[0].data = values;
    equityChart.update();
  }
}

$("btn-start").addEventListener("click", async () => {
  await post("/api/start");
  refresh();
});

$("btn-stop").addEventListener("click", async () => {
  const positions = await getJSON("/api/positions");
  let closePositions = false;
  if (positions.length > 0) {
    const yes = confirm(`Tienes ${positions.length} posición(es) abierta(s).\n\nAceptar = cerrar todo y detener.\nCancelar = solo detener (dejar posiciones abiertas).`);
    closePositions = yes;
  }
  await post(`/api/stop?close_positions=${closePositions}`);
  refresh();
});

refresh();
setInterval(refresh, 10000); // polling cada 10s
```

- [ ] **Step 4: Validación manual en el navegador**

Run: `python scripts/run_dashboard.py` (lo creas en la Task 9; si aún no, salta este step y vuelve tras la Task 9).
Abre `http://127.0.0.1:8000`. Verifica: carga el dashboard, el estado dice "Detenido", los botones responden, y al iniciar/detener cambia el estado. (Requiere `.env` con keys paper para que `/api/account` responda.)

- [ ] **Step 5: Commit**

```bash
git add src/web/static/
git commit -m "feat(web): dashboard frontend (estado, cuenta, posiciones, métricas, equity)" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: Script de arranque + documentación

**Files:**
- Create: `scripts/run_dashboard.py`
- Modify: `COMANDOS.md`

- [ ] **Step 1: Crear `scripts/run_dashboard.py`**

```python
"""CLI: arranca el dashboard web (FastAPI + uvicorn) SOLO en localhost.

Uso:
    python scripts/run_dashboard.py
Luego abre http://127.0.0.1:8000 en el navegador.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permite ejecutar el script directamente.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402


def main() -> None:
    # host 127.0.0.1 → accesible solo desde esta PC (sin exposición a la red/internet).
    uvicorn.run("src.web.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verificar que el servidor arranca**

Run: `python scripts/run_dashboard.py`
Expected: uvicorn loguea `Uvicorn running on http://127.0.0.1:8000`. Abre la URL, confirma que carga el dashboard. Detén con `Ctrl + C`.

- [ ] **Step 3: Documentar en `COMANDOS.md`**

Añade una sección nueva tras la de "Atajos de doble clic":

```markdown
## Dashboard web (interfaz con botones)

Con el venv activado:
```bash
python scripts/run_dashboard.py
```
Luego abre **http://127.0.0.1:8000** en el navegador. Desde ahí puedes iniciar/detener
el bot con botones y ver estado, cuenta, posiciones, historial, métricas y la equity curve.

- Solo accesible desde esta PC (localhost). El acceso remoto llega en la fase de VPS.
- El bot corre mientras el servidor esté abierto. `Ctrl + C` detiene el servidor.
```

- [ ] **Step 4: Commit**

```bash
git add scripts/run_dashboard.py COMANDOS.md
git commit -m "feat(web): script run_dashboard + docs de COMANDOS" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 10: Verificación final

- [ ] **Step 1: Suite completa + cobertura**

Run: `pytest`
Expected: todos los tests en verde (incluye los nuevos de bot, métricas, manager y rutas).

- [ ] **Step 2: Lint + formato**

Run: `ruff format . ; ruff check .`
Expected: sin errores. Corrige lo que reporte y re-ejecuta.

- [ ] **Step 3: Humo manual del dashboard**

Run: `python scripts/run_dashboard.py`, abre `http://127.0.0.1:8000`, inicia el bot, espera/observa un ciclo, detén con el botón (probando el diálogo de cierre de posiciones), confirma que las métricas y la equity curve se pueblan. `Ctrl + C`.

- [ ] **Step 4: Commit final (si ruff aplicó cambios)**

```bash
git add -A
git commit -m "chore(web): formato y ajustes finales del dashboard" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Notas para el implementador

- **Separación de capas:** ningún archivo de `src/web/` debe importar `alpaca`. Solo a través de `Broker`. Si te ves importando Alpaca en la web, párate.
- **Seguridad paper/live:** el arranque en live exige `confirm_live=True`. No lo "ablandes" para probar.
- **Coverage:** `scripts/` está excluido de cobertura (ver `pyproject.toml`), por eso `run_dashboard.py` no necesita test. El frontend (HTML/JS) se valida a mano.
- **Windows:** todos los comandos asumen el venv activado (ver `dev-environment` en memoria; usar PowerShell).
