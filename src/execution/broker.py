"""Wrapper de Alpaca — ÚNICA capa del proyecto que conoce el broker.

Abstrae paper vs live mediante el flag PAPER. Idempotencia: no duplica órdenes
si ya hay posición abierta. Los errores del API se loguean y devuelven None en
vez de propagarse (el bot no debe crashear por un fallo transitorio).

Ver skill `alpaca-integration`.
"""

from __future__ import annotations

from typing import Any

from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest
from loguru import logger

from config.settings import settings


def get_trading_client() -> TradingClient:
    """Cliente de trading. `paper` es el ÚNICO cambio entre modos."""
    return TradingClient(
        api_key=settings.ALPACA_API_KEY,
        secret_key=settings.ALPACA_SECRET_KEY,
        paper=settings.PAPER,
    )


class Broker:
    """Fachada mínima sobre el TradingClient de Alpaca."""

    def __init__(self, client: TradingClient | None = None) -> None:
        self.client = client or get_trading_client()

    def has_position(self, symbol: str) -> bool:
        return self.get_position(symbol) is not None

    def get_position(self, symbol: str) -> Any | None:
        """Posición abierta del símbolo, o None si no existe."""
        try:
            return self.client.get_open_position(symbol)
        except Exception:
            return None

    def get_account(self) -> Any:
        return self.client.get_account()

    def list_positions(self) -> list[Any]:
        """Todas las posiciones abiertas (lista vacía si no hay)."""
        return self.client.get_all_positions()

    def buy(self, symbol: str, notional: float) -> Any | None:
        """Compra a mercado por `notional` USD. Idempotente: no duplica posición."""
        if self.has_position(symbol):
            logger.info(f"Ya existe posición en {symbol}; no se duplica la orden.")
            return None

        order = MarketOrderRequest(
            symbol=symbol,
            notional=notional,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.GTC,  # cripto: GTC
        )
        try:
            return self.client.submit_order(order)
        except APIError as e:
            logger.error(f"Error al enviar orden de compra de {symbol}: {e}")
            return None

    def close_position(self, symbol: str) -> Any | None:
        """Cierra la posición del símbolo a mercado."""
        try:
            return self.client.close_position(symbol)
        except APIError as e:
            logger.error(f"Error al cerrar posición de {symbol}: {e}")
            return None
