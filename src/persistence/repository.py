"""Lectura/escritura de trades y métricas sobre SQLite."""

from __future__ import annotations

import sqlite3


class Repository:
    """Acceso a datos para trades y daily_metrics."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # --- trades ---

    def save_trade(
        self,
        *,
        timestamp: str,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        pnl: float = 0.0,
        order_id: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO trades (timestamp, symbol, side, qty, price, pnl, order_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (timestamp, symbol, side, qty, price, pnl, order_id),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_trades(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM trades ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    # --- daily_metrics ---

    def save_daily_metric(
        self,
        *,
        date: str,
        portfolio_value: float,
        daily_pnl_pct: float = 0.0,
        drawdown_pct: float = 0.0,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO daily_metrics (date, portfolio_value, daily_pnl_pct, drawdown_pct)
            VALUES (?, ?, ?, ?)
            """,
            (date, portfolio_value, daily_pnl_pct, drawdown_pct),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_daily_metrics(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM daily_metrics ORDER BY id").fetchall()
        return [dict(row) for row in rows]
