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
    repo.save_trade(
        timestamp="2026-06-07T14:00:00",
        symbol="BTC/USD",
        side="SELL",
        qty=0.01,
        price=2410.0,
        pnl=32.0,
    )
    repo.save_daily_metric(date="2026-06-06", portfolio_value=10_000.0)
    repo.save_daily_metric(date="2026-06-07", portfolio_value=10_320.0)
    app.dependency_overrides[deps.get_repository] = lambda: repo

    c = TestClient(app)
    assert len(c.get("/api/trades").json()) == 1
    metrics = c.get("/api/metrics").json()
    assert metrics["total_trades"] == 1
    assert metrics["win_rate_pct"] == 100.0

    conn.close()
