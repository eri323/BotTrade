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
