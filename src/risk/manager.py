"""Gestión de riesgo — capa OBLIGATORIA. Ninguna orden se ejecuta sin pasar por aquí.

Pura y agnóstica al broker: recibe datos, devuelve decisiones. Implementa
position sizing, stop-loss, take-profit, límite de pérdida diaria, circuit
breaker y tope de posiciones concurrentes (§7 del plan).

Convención de signos: los porcentajes de P&L y drawdown se pasan como fracciones
(−0.04 = −4%). Los umbrales se guardan como magnitudes positivas.
"""

from __future__ import annotations


class RiskManager:
    def __init__(
        self,
        max_position_pct: float,
        stop_loss_pct: float,
        take_profit_pct: float,
        daily_loss_limit_pct: float,
        circuit_breaker_pct: float,
        max_concurrent_positions: int,
    ) -> None:
        self.max_position_pct = max_position_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.circuit_breaker_pct = circuit_breaker_pct
        self.max_concurrent_positions = max_concurrent_positions

    def calculate_position_size(self, capital: float) -> float:
        """USD a invertir en una posición: `max_position_pct` del capital."""
        if capital <= 0:
            return 0.0
        return capital * self.max_position_pct

    def should_stop_loss(self, pnl_pct: float) -> bool:
        """True si la pérdida no realizada alcanzó el stop-loss."""
        return pnl_pct <= -self.stop_loss_pct

    def should_take_profit(self, pnl_pct: float) -> bool:
        """True si la ganancia no realizada alcanzó el take-profit."""
        return pnl_pct >= self.take_profit_pct

    def daily_limit_reached(self, daily_pnl_pct: float) -> bool:
        """True si la pérdida del día alcanzó el límite diario."""
        return daily_pnl_pct <= -self.daily_loss_limit_pct

    def circuit_breaker_triggered(self, drawdown_pct: float) -> bool:
        """True si el drawdown total alcanzó el umbral del circuit breaker."""
        return drawdown_pct <= -self.circuit_breaker_pct

    def can_open_position(self, open_positions: int) -> bool:
        """True si aún se puede abrir una posición más."""
        return open_positions < self.max_concurrent_positions
