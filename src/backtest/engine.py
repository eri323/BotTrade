"""Backtester event-driven — procesa velas una por una, en orden cronológico.

Cero look-ahead por diseño (cada vela solo ve el pasado) y simetría con el loop
en vivo: usa la misma estrategia y el mismo RiskManager que producción.

`run(df)` NO construye features: recibe un df ya listo para la estrategia (la
construcción de features es responsabilidad del caller). Necesita al menos las
columnas `close` y `low`, más las que la estrategia consuma.
"""

from __future__ import annotations

import pandas as pd

from src.risk.manager import RiskManager
from src.strategy.base import BUY, SELL, Strategy


class BacktestEngine:
    def __init__(
        self,
        strategy: Strategy,
        risk_manager: RiskManager,
        initial_capital: float = 10_000.0,
        commission_pct: float = 0.001,
        slippage_pct: float = 0.001,
    ) -> None:
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct

    def run(self, df: pd.DataFrame) -> dict:
        capital = self.initial_capital
        position = 0.0  # cantidad del activo en cartera
        entry_price = 0.0
        trades: list[dict] = []
        equity_curve: list[dict] = []

        for i in range(len(df)):
            history = df.iloc[: i + 1]  # solo el pasado disponible
            current_bar = history.iloc[-1]
            current_price = float(current_bar["close"])

            # Valor del portfolio al inicio de la vela (pre-trade).
            equity_curve.append(
                {"date": current_bar.name, "value": capital + position * current_price}
            )

            # --- Riesgo: stop-loss sobre posición abierta (contra el mínimo intradía) ---
            if position > 0:
                low_price = float(current_bar["low"])
                low_pnl_pct = (low_price - entry_price) / entry_price
                if self.risk_manager.should_stop_loss(low_pnl_pct):
                    # Fill conservador: al precio de stop, o al mínimo si hubo gap.
                    stop_trigger = entry_price * (1 - self.risk_manager.stop_loss_pct)
                    fill_price = min(stop_trigger, low_price) * (1 - self.slippage_pct)
                    revenue = position * fill_price * (1 - self.commission_pct)
                    capital += revenue
                    trades.append(
                        {
                            "type": "SELL_STOP",
                            "price": fill_price,
                            "qty": position,
                            "pnl": revenue - position * entry_price,
                        }
                    )
                    position = 0.0
                    entry_price = 0.0
                    continue

            # --- Señal de la estrategia ---
            signal = self.strategy.generate_signal(history)

            if signal == BUY and position == 0:
                position_size = self.risk_manager.calculate_position_size(capital)
                buy_price = current_price * (1 + self.slippage_pct)
                cost = position_size * (1 + self.commission_pct)
                if position_size > 0 and cost <= capital:
                    qty = position_size / buy_price
                    capital -= cost
                    position = qty
                    entry_price = buy_price
                    trades.append({"type": "BUY", "price": buy_price, "qty": qty, "pnl": 0.0})

            elif signal == SELL and position > 0:
                sell_price = current_price * (1 - self.slippage_pct)
                revenue = position * sell_price * (1 - self.commission_pct)
                capital += revenue
                trades.append(
                    {
                        "type": "SELL",
                        "price": sell_price,
                        "qty": position,
                        "pnl": revenue - position * entry_price,
                    }
                )
                position = 0.0
                entry_price = 0.0

        # Cerrar posición abierta al final del periodo (liquidación forzada).
        if position > 0:
            final_price = float(df.iloc[-1]["close"])
            capital += position * final_price
            position = 0.0

        return {
            "trades": trades,
            "equity_curve": pd.DataFrame(equity_curve).set_index("date"),
            "final_capital": capital,
        }
