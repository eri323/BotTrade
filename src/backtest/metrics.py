"""Métricas financieras del backtest — funciones puras.

Sharpe anualizado a 365 días (cripto opera 24/7, no 252 como las acciones).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sharpe_ratio(equity_curve: pd.Series, risk_free_rate: float = 0.0) -> float:
    """Sharpe ratio anualizado a partir de los valores diarios del portfolio."""
    returns = equity_curve.pct_change().dropna()
    if returns.std() == 0 or len(returns) == 0:
        return 0.0
    sharpe = (returns.mean() - risk_free_rate) / returns.std()
    # Cripto 24/7 → 365 días/año (usar 252 inflaría el Sharpe).
    return float(sharpe * np.sqrt(365))


def max_drawdown(equity_curve: pd.Series) -> float:
    """Máxima caída desde un pico. Valor negativo (p. ej. -0.23 = -23%)."""
    rolling_max = equity_curve.cummax()
    drawdowns = (equity_curve - rolling_max) / rolling_max
    return float(drawdowns.min())


def win_rate(trades: list[dict]) -> float:
    """Porcentaje de operaciones ganadoras (0–1)."""
    if not trades:
        return 0.0
    winners = [t for t in trades if t["pnl"] > 0]
    return len(winners) / len(trades)


def profit_factor(trades: list[dict]) -> float:
    """Suma de ganancias / suma de pérdidas (> 1 es rentable)."""
    gains = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    losses = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    if losses == 0:
        return float("inf")
    return gains / losses


def total_return(initial_capital: float, final_capital: float) -> float:
    """Retorno total del periodo."""
    return (final_capital - initial_capital) / initial_capital


def summary(result: dict, initial_capital: float) -> dict:
    """Resumen completo de un backtest (solo métricas, sin equity_curve)."""
    equity = result["equity_curve"]["value"]
    trades = result["trades"]

    return {
        "total_return_pct": round(total_return(initial_capital, result["final_capital"]) * 100, 2),
        "sharpe_ratio": round(sharpe_ratio(equity), 3),
        "max_drawdown_pct": round(max_drawdown(equity) * 100, 2),
        "win_rate_pct": round(win_rate(trades) * 100, 2),
        "profit_factor": round(profit_factor(trades), 3),
        "total_trades": len(trades),
        "final_capital_usd": round(result["final_capital"], 2),
    }


def buy_and_hold_metrics(df: pd.DataFrame, initial_capital: float = 10_000.0) -> dict:
    """Baseline: comprar al inicio del periodo y mantener hasta el final.

    Es el mínimo que cualquier estrategia debe superar.
    """
    first_price = float(df.iloc[0]["close"])
    last_price = float(df.iloc[-1]["close"])
    qty = initial_capital / first_price
    final_capital = qty * last_price

    equity = df["close"] * qty
    return {
        "total_return_pct": round(total_return(initial_capital, final_capital) * 100, 2),
        "sharpe_ratio": round(sharpe_ratio(equity), 3),
        "max_drawdown_pct": round(max_drawdown(equity) * 100, 2),
        "final_capital_usd": round(final_capital, 2),
    }
