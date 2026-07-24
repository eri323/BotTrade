"""Tests del orquestador del bot (src/bot/runner.py).

Broker mockeado; risk y repository reales. Se prueba la lógica de decisión de
un ciclo (process_symbol), incluyendo "riesgo primero".
"""

import threading

import pytest

from src.bot.runner import TradingBot
from src.persistence.db import get_connection, init_db
from src.persistence.repository import Repository
from src.risk.manager import RiskManager
from src.strategy.base import Strategy


class FixedStrategy(Strategy):
    def __init__(self, signal: str) -> None:
        self.signal = signal

    def generate_signal(self, df):
        return self.signal


@pytest.fixture
def risk():
    return RiskManager(
        max_position_pct=0.20,
        stop_loss_pct=0.04,
        take_profit_pct=0.08,
        daily_loss_limit_pct=0.05,
        circuit_breaker_pct=0.20,
        max_concurrent_positions=2,
    )


@pytest.fixture
def repo():
    conn = get_connection(":memory:")
    init_db(conn)
    yield Repository(conn)
    conn.close()


def _broker(mocker, *, position=None, positions=None, cash="10000.00"):
    broker = mocker.MagicMock()
    broker.get_position.return_value = position
    broker.list_positions.return_value = positions if positions is not None else []
    account = mocker.MagicMock()
    account.cash = cash
    broker.get_account.return_value = account
    broker.buy.return_value = mocker.MagicMock(id="order-1")
    return broker


def _bot(broker, strategy, risk, repo):
    return TradingBot(broker, strategy, risk, repo, symbols=["BTC/USD"])


def test_buy_on_buy_signal_without_position(mocker, risk, repo, sample_ohlcv):
    broker = _broker(mocker, position=None)
    bot = _bot(broker, FixedStrategy("BUY"), risk, repo)

    action = bot.process_symbol("BTC/USD", sample_ohlcv)

    assert action == "BUY"
    broker.buy.assert_called_once_with("BTC/USD", pytest.approx(2_000.0))
    assert repo.get_trades()[0]["side"] == "BUY"


def test_no_buy_when_position_exists(mocker, risk, repo, sample_ohlcv):
    pos = mocker.MagicMock(unrealized_plpc="0.01", qty="0.01")
    broker = _broker(mocker, position=pos)
    bot = _bot(broker, FixedStrategy("BUY"), risk, repo)

    action = bot.process_symbol("BTC/USD", sample_ohlcv)

    assert action == "HOLD"
    broker.buy.assert_not_called()


def test_sell_signal_closes_position(mocker, risk, repo, sample_ohlcv):
    pos = mocker.MagicMock(unrealized_plpc="0.03", qty="0.01")
    broker = _broker(mocker, position=pos)
    bot = _bot(broker, FixedStrategy("SELL"), risk, repo)

    action = bot.process_symbol("BTC/USD", sample_ohlcv)

    assert action == "SELL"
    broker.close_position.assert_called_once_with("BTC/USD")
    assert repo.get_trades()[0]["side"] == "SELL"


def test_stop_loss_takes_priority_over_signal(mocker, risk, repo, sample_ohlcv):
    """Con pérdida más allá del stop, se cierra aunque la señal sea HOLD."""
    pos = mocker.MagicMock(unrealized_plpc="-0.05", qty="0.01")
    broker = _broker(mocker, position=pos)
    bot = _bot(broker, FixedStrategy("HOLD"), risk, repo)

    action = bot.process_symbol("BTC/USD", sample_ohlcv)

    assert action == "SELL_STOP"
    broker.close_position.assert_called_once_with("BTC/USD")
    assert repo.get_trades()[0]["side"] == "SELL_STOP"


def test_hold_with_insufficient_data(mocker, risk, repo, sample_ohlcv):
    broker = _broker(mocker, position=None)
    bot = _bot(broker, FixedStrategy("BUY"), risk, repo)

    action = bot.process_symbol("BTC/USD", sample_ohlcv.iloc[:10])

    assert action == "HOLD"
    broker.buy.assert_not_called()


def test_buy_blocked_at_max_concurrent_positions(mocker, risk, repo, sample_ohlcv):
    others = [mocker.MagicMock(), mocker.MagicMock()]  # ya hay 2 abiertas
    broker = _broker(mocker, position=None, positions=others)
    bot = _bot(broker, FixedStrategy("BUY"), risk, repo)

    action = bot.process_symbol("BTC/USD", sample_ohlcv)

    assert action == "HOLD"
    broker.buy.assert_not_called()


def test_run_stops_when_event_set(mocker, risk, repo, sample_ohlcv):
    broker = _broker(mocker, position=None)
    bot = _bot(broker, FixedStrategy("HOLD"), risk, repo)
    broker.get_account.return_value.portfolio_value = "10000.00"
    broker.get_account.return_value.last_equity = "10000.00"
    stop_event = threading.Event()
    calls = {"n": 0}

    def fetch(symbol):
        calls["n"] += 1
        stop_event.set()  # pedir parada tras el primer ciclo
        return sample_ohlcv

    bot.run(fetch, interval_seconds=0, stop_event=stop_event)

    assert calls["n"] == 1  # un símbolo, un ciclo, y para


def test_run_does_nothing_if_event_already_set(mocker, risk, repo, sample_ohlcv):
    broker = _broker(mocker, position=None)
    bot = _bot(broker, FixedStrategy("HOLD"), risk, repo)
    stop_event = threading.Event()
    stop_event.set()
    calls = {"n": 0}

    def fetch(symbol):
        calls["n"] += 1
        return sample_ohlcv

    bot.run(fetch, interval_seconds=0, stop_event=stop_event)

    assert calls["n"] == 0


def test_sell_records_realized_pnl(mocker, risk, repo, sample_ohlcv):
    pos = mocker.MagicMock(unrealized_plpc="0.03", unrealized_pl="150.50", qty="0.01")
    broker = _broker(mocker, position=pos)
    bot = _bot(broker, FixedStrategy("SELL"), risk, repo)

    bot.process_symbol("BTC/USD", sample_ohlcv)

    assert repo.get_trades()[0]["pnl"] == pytest.approx(150.50)


def test_stop_loss_records_realized_pnl(mocker, risk, repo, sample_ohlcv):
    pos = mocker.MagicMock(unrealized_plpc="-0.05", unrealized_pl="-220.00", qty="0.01")
    broker = _broker(mocker, position=pos)
    bot = _bot(broker, FixedStrategy("HOLD"), risk, repo)

    bot.process_symbol("BTC/USD", sample_ohlcv)

    assert repo.get_trades()[0]["pnl"] == pytest.approx(-220.00)


def test_run_once_records_daily_metric(mocker, risk, repo, sample_ohlcv):
    broker = _broker(mocker, position=None)
    broker.get_account.return_value.portfolio_value = "10500.00"
    broker.get_account.return_value.last_equity = "10000.00"
    bot = _bot(broker, FixedStrategy("HOLD"), risk, repo)

    bot.run_once(lambda symbol: sample_ohlcv)

    metrics = repo.get_daily_metrics()
    assert len(metrics) == 1
    assert metrics[0]["portfolio_value"] == pytest.approx(10500.0)
    assert metrics[0]["daily_pnl_pct"] == pytest.approx(0.05)


def test_daily_metric_drawdown_vs_peak(mocker, risk, repo, sample_ohlcv):
    broker = _broker(mocker, position=None)
    bot = _bot(broker, FixedStrategy("HOLD"), risk, repo)

    # Ciclo 1: pico en 10000
    broker.get_account.return_value.portfolio_value = "10000.00"
    broker.get_account.return_value.last_equity = "10000.00"
    bot.run_once(lambda symbol: sample_ohlcv)

    # Ciclo 2: cae a 9000 -> drawdown -10%
    broker.get_account.return_value.portfolio_value = "9000.00"
    broker.get_account.return_value.last_equity = "10000.00"
    bot.run_once(lambda symbol: sample_ohlcv)

    metrics = repo.get_daily_metrics()
    assert metrics[1]["drawdown_pct"] == pytest.approx(-0.10)
