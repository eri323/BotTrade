"""Loop principal en vivo (orquestador).

Flujo por símbolo: datos → features → señal → RIESGO → ejecutar → registrar.
"Riesgo primero": el stop-loss se evalúa antes que la señal de la estrategia.

`process_symbol` es la unidad testeable (un ciclo de decisión). `run_once`
procesa todos los símbolos una vez. `run` es el bucle continuo (no testeado).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime

import pandas as pd
from loguru import logger

from src.execution.broker import Broker
from src.features.indicators import build_features
from src.risk.manager import RiskManager
from src.strategy.base import BUY, HOLD, SELL, Strategy

# Acciones posibles de un ciclo (para logging/observabilidad).
SELL_STOP = "SELL_STOP"


class TradingBot:
    def __init__(
        self,
        broker: Broker,
        strategy: Strategy,
        risk: RiskManager,
        repository,
        symbols: list[str],
    ) -> None:
        self.broker = broker
        self.strategy = strategy
        self.risk = risk
        self.repository = repository
        self.symbols = symbols

    def _record(
        self, symbol: str, side: str, qty: float, price: float, order_id: str | None = None
    ) -> None:
        self.repository.save_trade(
            timestamp=datetime.now(UTC).isoformat(),
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            order_id=order_id,
        )

    def process_symbol(self, symbol: str, df_raw: pd.DataFrame) -> str:
        """Ejecuta un ciclo de decisión para un símbolo. Devuelve la acción tomada."""
        features = build_features(df_raw)
        if len(features) < 2:
            return HOLD

        last_price = float(df_raw["close"].iloc[-1])
        position = self.broker.get_position(symbol)

        # --- Riesgo primero: stop-loss sobre posición abierta ---
        if position is not None:
            pnl_pct = float(position.unrealized_plpc)
            if self.risk.should_stop_loss(pnl_pct):
                logger.warning(f"Stop-loss en {symbol} (P&L {pnl_pct:.2%}); cerrando.")
                self.broker.close_position(symbol)
                self._record(symbol, SELL_STOP, float(position.qty), last_price)
                return SELL_STOP

        signal = self.strategy.generate_signal(features)

        if signal == BUY and position is None:
            open_positions = len(self.broker.list_positions())
            if not self.risk.can_open_position(open_positions):
                logger.info(f"Máximo de posiciones alcanzado; no se abre {symbol}.")
                return HOLD
            capital = float(self.broker.get_account().cash)
            notional = self.risk.calculate_position_size(capital)
            order = self.broker.buy(symbol, notional)
            if order is not None:
                qty = notional / last_price if last_price > 0 else 0.0
                self._record(symbol, BUY, qty, last_price, order_id=getattr(order, "id", None))
                logger.info(f"BUY {symbol} por {notional:.2f} USD.")
                return BUY
            return HOLD

        if signal == SELL and position is not None:
            self.broker.close_position(symbol)
            self._record(symbol, SELL, float(position.qty), last_price)
            logger.info(f"SELL {symbol} (señal de la estrategia).")
            return SELL

        return HOLD

    def run_once(self, fetch: Callable[[str], pd.DataFrame]) -> dict[str, str]:
        """Procesa todos los símbolos una vez. `fetch(symbol) -> df_raw`."""
        return {symbol: self.process_symbol(symbol, fetch(symbol)) for symbol in self.symbols}

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
