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
        # Serializa start()/stop(): FastAPI atiende los endpoints en un threadpool,
        # así que dos /api/start simultáneos no deben arrancar dos bots.
        self._lock = threading.Lock()

    def _build_bot(self) -> tuple[TradingBot, Broker]:
        broker = Broker()
        # Esta conexión SQLite la usa SOLO el hilo del bot (único escritor); por eso
        # `check_same_thread=False` es seguro aquí. Las lecturas de la web usan sus
        # propias conexiones (ver web/deps.py).
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
        with self._lock:
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
        with self._lock:
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
