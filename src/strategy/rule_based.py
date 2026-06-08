"""Estrategia de reglas (RSI + EMA) — BASELINE determinístico.

Reglas (§8 Fase 1 del plan):
  - BUY:  EMA(9) cruza POR ARRIBA de EMA(21) y RSI < `rsi_buy_max`.
  - SELL: EMA(9) cruza POR ABAJO de EMA(21), o RSI > `rsi_sell_min`.
  - HOLD: en cualquier otro caso.

Es el punto de referencia que el ML debe vencer (principio #5 del plan).
"""

from __future__ import annotations

import pandas as pd

from src.strategy.base import BUY, HOLD, SELL, Strategy


class RuleBasedStrategy(Strategy):
    def __init__(self, rsi_buy_max: float = 70.0, rsi_sell_min: float = 75.0) -> None:
        self.rsi_buy_max = rsi_buy_max
        self.rsi_sell_min = rsi_sell_min

    def generate_signal(self, df: pd.DataFrame) -> str:
        # Se necesita la vela actual y la previa para detectar un cruce.
        if len(df) < 2:
            return HOLD

        last = df.iloc[-1]
        prev = df.iloc[-2]

        crossed_up = prev["ema_9"] <= prev["ema_21"] and last["ema_9"] > last["ema_21"]
        crossed_down = prev["ema_9"] >= prev["ema_21"] and last["ema_9"] < last["ema_21"]

        if crossed_up and last["rsi_14"] < self.rsi_buy_max:
            return BUY
        if crossed_down or last["rsi_14"] > self.rsi_sell_min:
            return SELL
        return HOLD
