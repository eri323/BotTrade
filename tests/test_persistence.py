"""Tests de la capa de persistencia SQLite (src/persistence)."""

import pytest

from src.persistence.db import get_connection, init_db
from src.persistence.repository import Repository


@pytest.fixture
def repo():
    conn = get_connection(":memory:")
    init_db(conn)
    yield Repository(conn)
    conn.close()


def test_init_db_creates_tables():
    conn = get_connection(":memory:")
    init_db(conn)
    names = {
        row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"trades", "daily_metrics"}.issubset(names)
    conn.close()


def test_get_trades_empty(repo):
    assert repo.get_trades() == []


def test_save_and_get_trade(repo):
    repo.save_trade(
        timestamp="2024-01-01T00:00:00",
        symbol="BTC/USD",
        side="BUY",
        qty=0.01,
        price=42_000.0,
        pnl=0.0,
        order_id="abc-123",
    )
    trades = repo.get_trades()
    assert len(trades) == 1
    t = trades[0]
    assert t["symbol"] == "BTC/USD"
    assert t["side"] == "BUY"
    assert t["qty"] == pytest.approx(0.01)
    assert t["price"] == pytest.approx(42_000.0)
    assert t["order_id"] == "abc-123"


def test_save_and_get_daily_metric(repo):
    repo.save_daily_metric(
        date="2024-01-01",
        portfolio_value=10_500.0,
        daily_pnl_pct=0.05,
        drawdown_pct=-0.02,
    )
    metrics = repo.get_daily_metrics()
    assert len(metrics) == 1
    m = metrics[0]
    assert m["portfolio_value"] == pytest.approx(10_500.0)
    assert m["daily_pnl_pct"] == pytest.approx(0.05)
    assert m["drawdown_pct"] == pytest.approx(-0.02)


def test_multiple_trades_preserve_order(repo):
    for i in range(3):
        repo.save_trade(
            timestamp=f"2024-01-0{i + 1}T00:00:00",
            symbol="ETH/USD",
            side="BUY",
            qty=1.0,
            price=2000.0 + i,
        )
    trades = repo.get_trades()
    assert [t["price"] for t in trades] == [2000.0, 2001.0, 2002.0]
