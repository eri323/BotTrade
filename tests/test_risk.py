"""Cobertura EXHAUSTIVA de la gestión de riesgo (src/risk/manager.py).

Prioridad máxima: ninguna orden se ejecuta sin pasar por aquí (principio #4).
"""

import pytest

from src.risk.manager import RiskManager


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


class TestPositionSizing:
    def test_max_position_pct(self, risk):
        assert risk.calculate_position_size(capital=10_000) == pytest.approx(2_000.0)

    def test_no_negative_size(self, risk):
        assert risk.calculate_position_size(capital=0) == 0


class TestStopLoss:
    def test_triggers_at_threshold(self, risk):
        assert risk.should_stop_loss(pnl_pct=-0.04) is True

    def test_triggers_below_threshold(self, risk):
        assert risk.should_stop_loss(pnl_pct=-0.10) is True

    def test_does_not_trigger_above(self, risk):
        assert risk.should_stop_loss(pnl_pct=-0.03) is False

    def test_does_not_trigger_on_gain(self, risk):
        assert risk.should_stop_loss(pnl_pct=0.05) is False


class TestTakeProfit:
    def test_triggers_at_threshold(self, risk):
        assert risk.should_take_profit(pnl_pct=0.08) is True

    def test_does_not_trigger_below(self, risk):
        assert risk.should_take_profit(pnl_pct=0.05) is False


class TestDailyLossLimit:
    def test_halts_on_daily_loss(self, risk):
        assert risk.daily_limit_reached(daily_pnl_pct=-0.05) is True

    def test_allows_trading_below_limit(self, risk):
        assert risk.daily_limit_reached(daily_pnl_pct=-0.03) is False


class TestCircuitBreaker:
    def test_triggers_on_drawdown(self, risk):
        assert risk.circuit_breaker_triggered(drawdown_pct=-0.20) is True

    def test_triggers_beyond_threshold(self, risk):
        assert risk.circuit_breaker_triggered(drawdown_pct=-0.35) is True

    def test_does_not_trigger_below(self, risk):
        assert risk.circuit_breaker_triggered(drawdown_pct=-0.15) is False


class TestMaxConcurrentPositions:
    def test_allows_below_limit(self, risk):
        assert risk.can_open_position(open_positions=1) is True

    def test_blocks_at_limit(self, risk):
        assert risk.can_open_position(open_positions=2) is False

    def test_blocks_above_limit(self, risk):
        assert risk.can_open_position(open_positions=5) is False
