"""Proveedores inyectables para la capa web (overridables en tests vía dependency_overrides)."""

from __future__ import annotations

from collections.abc import Iterator

from src.execution.broker import Broker
from src.persistence.db import get_connection, init_db
from src.persistence.repository import Repository
from src.web.bot_manager import BotManager

_manager = BotManager(interval_seconds=86_400)


def get_manager() -> BotManager:
    return _manager


def get_broker() -> Broker:
    return Broker()


def get_repository() -> Iterator[Repository]:
    """Conexión por request, cerrada al terminar (dependencia FastAPI con yield)."""
    conn = get_connection()
    init_db(conn)
    try:
        yield Repository(conn)
    finally:
        conn.close()
