"""Conexión y esquema de SQLite (vía `sqlite3` de la stdlib, sin ORM)."""

from __future__ import annotations

import sqlite3

from config.settings import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp  TEXT    NOT NULL,
    symbol     TEXT    NOT NULL,
    side       TEXT    NOT NULL,
    qty        REAL    NOT NULL,
    price      REAL    NOT NULL,
    pnl        REAL    NOT NULL DEFAULT 0.0,
    order_id   TEXT
);

CREATE TABLE IF NOT EXISTS daily_metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT    NOT NULL,
    portfolio_value REAL    NOT NULL,
    daily_pnl_pct   REAL    NOT NULL DEFAULT 0.0,
    drawdown_pct    REAL    NOT NULL DEFAULT 0.0
);
"""


def get_connection(path: str | None = None) -> sqlite3.Connection:
    """Conexión SQLite con filas accesibles por nombre (sqlite3.Row)."""
    conn = sqlite3.connect(path or settings.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Crea las tablas si no existen."""
    conn.executescript(SCHEMA)
    conn.commit()
