"""Comparativa de estrategias sobre datos históricos.

Para Fase 1: baseline buy-and-hold vs estrategia de reglas. El ML se añadirá en
Fase 3. Devuelve `{"summary": ..., "results": ...}`:
  - summary: métricas resumidas por estrategia (para imprimir/comparar).
  - results: resultados crudos del engine con equity_curve (para graficar).
"""

from __future__ import annotations

import pandas as pd

from config.settings import settings
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import buy_and_hold_metrics, summary
from src.features.indicators import build_features
from src.risk.manager import RiskManager
from src.strategy.rule_based import RuleBasedStrategy


def default_risk() -> RiskManager:
    """RiskManager con los parámetros de config/settings."""
    return RiskManager(
        max_position_pct=settings.MAX_POSITION_PCT,
        stop_loss_pct=settings.STOP_LOSS_PCT,
        take_profit_pct=settings.TAKE_PROFIT_PCT,
        daily_loss_limit_pct=settings.DAILY_LOSS_LIMIT_PCT,
        circuit_breaker_pct=settings.CIRCUIT_BREAKER_DRAWDOWN_PCT,
        max_concurrent_positions=settings.MAX_CONCURRENT_POSITIONS,
    )


def run_comparison(
    df_raw: pd.DataFrame,
    risk: RiskManager | None = None,
    initial_capital: float = 10_000.0,
) -> dict:
    """Corre buy-and-hold y la estrategia de reglas sobre `df_raw` (OHLCV crudo)."""
    risk = risk or default_risk()
    features = build_features(df_raw)

    raw: dict = {}
    table: dict = {}

    # Baseline buy-and-hold (sobre el df crudo, no pasa por el engine).
    table["buy_hold"] = buy_and_hold_metrics(df_raw, initial_capital)

    # Estrategia de reglas (sobre el df con features).
    raw["rules"] = BacktestEngine(RuleBasedStrategy(), risk, initial_capital).run(features)
    table["rules"] = summary(raw["rules"], initial_capital)

    return {"summary": table, "results": raw}
