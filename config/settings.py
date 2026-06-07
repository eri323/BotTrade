"""Configuración central del bot — única fuente de parámetros.

Carga las variables desde `.env` (vía python-dotenv) y expone un objeto
`settings` inmutable. Ningún otro módulo debe leer `os.environ` directamente
ni hardcodear umbrales: todo pasa por aquí (principio del plan §4 / CLAUDE.md).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _get_float(key: str, default: float) -> float:
    return float(os.getenv(key, default))


def _get_int(key: str, default: int) -> int:
    return int(os.getenv(key, default))


def _get_bool(key: str, default: bool) -> bool:
    return os.getenv(key, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _get_list(key: str, default: list[str]) -> list[str]:
    raw = os.getenv(key)
    if not raw:
        return list(default)
    return [s.strip() for s in raw.split(",") if s.strip()]


@dataclass(frozen=True)
class Settings:
    """Parámetros del bot, cargados desde el entorno con defaults seguros."""

    # --- Alpaca / broker ---
    ALPACA_API_KEY: str = field(default_factory=lambda: os.getenv("ALPACA_API_KEY", ""))
    ALPACA_SECRET_KEY: str = field(default_factory=lambda: os.getenv("ALPACA_SECRET_KEY", ""))
    PAPER: bool = field(default_factory=lambda: _get_bool("PAPER", True))

    # --- Trading ---
    SYMBOLS: list[str] = field(default_factory=lambda: _get_list("SYMBOLS", ["BTC/USD", "ETH/USD"]))
    TIMEFRAME: str = field(default_factory=lambda: os.getenv("TIMEFRAME", "1Day"))

    # --- Gestión de riesgo (§7 del plan) ---
    MAX_POSITION_PCT: float = field(default_factory=lambda: _get_float("MAX_POSITION_PCT", 0.20))
    STOP_LOSS_PCT: float = field(default_factory=lambda: _get_float("STOP_LOSS_PCT", 0.04))
    TAKE_PROFIT_PCT: float = field(default_factory=lambda: _get_float("TAKE_PROFIT_PCT", 0.08))
    DAILY_LOSS_LIMIT_PCT: float = field(
        default_factory=lambda: _get_float("DAILY_LOSS_LIMIT_PCT", 0.05)
    )
    CIRCUIT_BREAKER_DRAWDOWN_PCT: float = field(
        default_factory=lambda: _get_float("CIRCUIT_BREAKER_DRAWDOWN_PCT", 0.20)
    )
    MAX_CONCURRENT_POSITIONS: int = field(
        default_factory=lambda: _get_int("MAX_CONCURRENT_POSITIONS", 2)
    )

    # --- Persistencia ---
    DATABASE_PATH: str = field(
        default_factory=lambda: os.getenv("DATABASE_PATH", "./trading_bot.db")
    )

    # --- Alertas (fase 4) ---
    TELEGRAM_BOT_TOKEN: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    TELEGRAM_CHAT_ID: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))


settings = Settings()
