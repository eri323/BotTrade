---
name: backtesting-engine
description: Convenciones del motor de backtesting event-driven del trading bot. Usar siempre que se trabaje en backtest/engine.py, backtest/metrics.py, o al comparar estrategias sobre datos históricos. Activar ante dudas sobre cómo evitar look-ahead bias en el backtester, cómo calcular Sharpe ratio o max drawdown, cómo establecer el baseline buy-and-hold, o cómo interpretar una equity curve.
---

# Motor de Backtesting — Convenciones

## Por qué event-driven (y no vectorizado)

Existen dos tipos de backtesters:

- **Vectorizado:** opera sobre arrays completos de una vez. Rápido, pero propenso a look-ahead bias accidental y difícil de hacer simétrico al loop en vivo.
- **Event-driven:** procesa velas **una por una, en orden cronológico**, simulando exactamente cómo correría el bot en vivo. Más lento, pero con dos ventajas críticas:

1. **Cero look-ahead por diseño:** si intentas acceder a datos del futuro dentro del loop, simplemente no están disponibles.
2. **Simetría con el live loop:** la lógica del backtester es casi idéntica a la del bot en vivo. Lo que validas en backtest se comporta igual en producción.

**Usar siempre event-driven en este proyecto.**

---

## Estructura del backtester

```python
# backtest/engine.py

class BacktestEngine:
    def __init__(
        self,
        strategy,            # instancia de Strategy
        risk_manager,        # instancia de RiskManager
        initial_capital: float = 10_000.0,
        commission_pct: float = 0.001,    # 0.1% por operación (simulado)
        slippage_pct: float = 0.001,      # 0.1% slippage simulado
    ):
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct

    def run(self, df: pd.DataFrame) -> dict:
        capital = self.initial_capital
        position = 0.0          # cantidad del activo que tenemos
        entry_price = 0.0
        trades = []
        equity_curve = []

        for i in range(len(df)):
            # Vista del pasado — solo filas 0..i (sin mirar adelante)
            history = df.iloc[:i+1].copy()
            current_bar = history.iloc[-1]
            current_price = float(current_bar["close"])

            # Valor actual del portfolio
            portfolio_value = capital + (position * current_price)
            equity_curve.append({
                "date": current_bar.name,
                "value": portfolio_value
            })

            # Generar señal (solo ve el historial disponible)
            signal = self.strategy.generate_signal(history)

            # Verificar riesgo (stop-loss sobre posición abierta)
            if position > 0:
                # ⚠️ El stop se evalúa contra el MÍNIMO intradía, no el cierre.
                # En velas diarias un stop a −4% saltaría dentro del día (vía el low),
                # no al cierre. Evaluar solo contra el close es optimista: ignora mechas
                # que perforaron el stop y rebotaron.
                low_price = float(current_bar["low"])
                low_pnl_pct = (low_price - entry_price) / entry_price
                if self.risk_manager.should_stop_loss(low_pnl_pct):
                    # Fill conservador: al precio de stop, o al mínimo si hubo gap a la baja
                    # (lo peor de los dos), más slippage.
                    stop_trigger = entry_price * (1 - self.risk_manager.stop_loss_pct)
                    fill_price = min(stop_trigger, low_price) * (1 - self.slippage_pct)
                    revenue = position * fill_price * (1 - self.commission_pct)
                    capital += revenue
                    trades.append({
                        "type": "SELL_STOP",
                        "price": fill_price,
                        "qty": position,
                        "pnl": revenue - (position * entry_price)
                    })
                    position = 0.0
                    entry_price = 0.0
                    continue

            # Ejecutar señal
            if signal == "BUY" and position == 0:
                # Calcular tamaño de posición
                position_size = self.risk_manager.calculate_position_size(capital)
                buy_price = current_price * (1 + self.slippage_pct)
                cost = position_size * (1 + self.commission_pct)

                if cost <= capital:
                    qty = position_size / buy_price
                    capital -= cost
                    position = qty
                    entry_price = buy_price
                    trades.append({
                        "type": "BUY",
                        "price": buy_price,
                        "qty": qty,
                        "pnl": 0
                    })

            elif signal == "SELL" and position > 0:
                sell_price = current_price * (1 - self.slippage_pct)
                revenue = position * sell_price * (1 - self.commission_pct)
                capital += revenue
                trades.append({
                    "type": "SELL",
                    "price": sell_price,
                    "qty": position,
                    "pnl": revenue - (position * entry_price)
                })
                position = 0.0
                entry_price = 0.0

        # Cerrar posición abierta al final del periodo
        if position > 0:
            final_price = float(df.iloc[-1]["close"])
            capital += position * final_price
            position = 0.0

        return {
            "trades": trades,
            "equity_curve": pd.DataFrame(equity_curve).set_index("date"),
            "final_capital": capital
        }
```

---

## Métricas financieras

```python
# backtest/metrics.py
import numpy as np
import pandas as pd


def sharpe_ratio(equity_curve: pd.Series, risk_free_rate: float = 0.0) -> float:
    """
    Sharpe ratio anualizado.
    equity_curve: serie de valores del portfolio día a día.
    """
    returns = equity_curve.pct_change().dropna()
    if returns.std() == 0:
        return 0.0
    sharpe = (returns.mean() - risk_free_rate) / returns.std()
    # ⚠️ Cripto opera 24/7 → 365 días/año, NO 252 (eso es para acciones).
    # Usar 252 aquí subestima la volatilidad anualizada e INFLA el Sharpe,
    # justo la métrica que decide el go-live (>1.5). Usar 365.
    return float(sharpe * np.sqrt(365))  # anualizar (cripto: 365 días)


def max_drawdown(equity_curve: pd.Series) -> float:
    """
    Máxima caída desde un pico. Retorna valor negativo (ej. -0.23 = -23%).
    """
    rolling_max = equity_curve.cummax()
    drawdowns = (equity_curve - rolling_max) / rolling_max
    return float(drawdowns.min())


def win_rate(trades: list) -> float:
    """Porcentaje de operaciones ganadoras."""
    if not trades:
        return 0.0
    winners = [t for t in trades if t["pnl"] > 0]
    return len(winners) / len(trades)


def profit_factor(trades: list) -> float:
    """Suma de ganancias / suma de pérdidas (> 1 es rentable)."""
    gains  = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    losses = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    if losses == 0:
        return float("inf")
    return gains / losses


def total_return(initial_capital: float, final_capital: float) -> float:
    """Retorno total del periodo."""
    return (final_capital - initial_capital) / initial_capital


def summary(result: dict, initial_capital: float) -> dict:
    """Resumen completo de un backtest."""
    equity = result["equity_curve"]["value"]
    trades = result["trades"]

    return {
        "total_return_pct":  round(total_return(initial_capital, result["final_capital"]) * 100, 2),
        "sharpe_ratio":      round(sharpe_ratio(equity), 3),
        "max_drawdown_pct":  round(max_drawdown(equity) * 100, 2),
        "win_rate_pct":      round(win_rate(trades) * 100, 2),
        "profit_factor":     round(profit_factor(trades), 3),
        "total_trades":      len(trades),
        "final_capital_usd": round(result["final_capital"], 2),
    }
```

---

## Baseline buy-and-hold (referencia obligatoria)

**El bot tiene que vencer al baseline.** Si no, es más fácil y rentable simplemente comprar y mantener el activo.

```python
def buy_and_hold_metrics(df: pd.DataFrame, initial_capital: float = 10_000.0) -> dict:
    """
    Simula comprar al inicio del periodo y mantener hasta el final.
    Es el baseline mínimo que cualquier estrategia debe superar.
    """
    first_price = float(df.iloc[0]["close"])
    last_price  = float(df.iloc[-1]["close"])
    qty = initial_capital / first_price
    final_capital = qty * last_price

    equity = df["close"] * qty
    return {
        "total_return_pct": round(total_return(initial_capital, final_capital) * 100, 2),
        "sharpe_ratio":     round(sharpe_ratio(equity), 3),
        "max_drawdown_pct": round(max_drawdown(equity) * 100, 2),
        "final_capital_usd": round(final_capital, 2),
    }
```

---

## Comparativa de estrategias

```python
# scripts/run_backtest.py

def comparar_estrategias(df, initial_capital=10_000.0):
    from src.strategy.rule_based import RuleBased
    from src.strategy.ml_strategy import MLStrategy
    from src.risk.manager import RiskManager
    from backtest.engine import BacktestEngine
    from backtest.metrics import summary, buy_and_hold_metrics

    risk = RiskManager(...)

    # OJO: `summary()` devuelve solo métricas (sin equity_curve), por eso separamos:
    #   - `raw`: resultados crudos del engine (con equity_curve y trades) → para graficar
    #   - `tabla`: métricas resumidas → para imprimir
    raw = {}      # alimenta plot_equity_curve()
    tabla = {}    # solo display

    # 1. Buy & Hold (no pasa por el engine)
    tabla["buy_hold"] = buy_and_hold_metrics(df, initial_capital)

    # 2. Estrategia de reglas
    raw["rules"] = BacktestEngine(RuleBased(), risk, initial_capital).run(df)
    tabla["rules"] = summary(raw["rules"], initial_capital)

    # 3. Modelo ML (si existe)
    raw["ml"] = BacktestEngine(
        MLStrategy("models/saved/model_latest.pkl"), risk, initial_capital
    ).run(df)
    tabla["ml"] = summary(raw["ml"], initial_capital)

    # Imprimir tabla comparativa
    import pandas as pd
    print("\n=== Comparativa de estrategias ===")
    print(pd.DataFrame(tabla).T.to_string())

    # `results` tiene equity_curve (para plot_equity_curve); `summary` es solo display.
    return {"summary": tabla, "results": raw}
```

**Regla de promoción del ML:** la estrategia ML se promueve a producción SOLO si supera a buy-and-hold Y a la estrategia de reglas en Sharpe, con drawdown comparable o menor.

---

## Incluir comisiones y slippage siempre

**No usar los parámetros de la tabla como los valores reales de Alpaca** (Alpaca es comisión cero para cripto). Usarlos como margen de seguridad y para simular condiciones reales de ejecución:

| Parámetro | Valor simulado | Justificación |
|---|---|---|
| `commission_pct` | 0.001 (0.1%) | Buffer de seguridad + posibles fees futuros |
| `slippage_pct` | 0.001 (0.1%) | Simula ejecución imperfecta |

Un backtest sin costos siempre se ve mejor de lo que es. Exigir costos simulados aunque sean pequeños es disciplina básica.

---

## Equity curve — visualización

```python
import matplotlib.pyplot as plt

def plot_equity_curve(results: dict, title: str = "Equity Curves"):
    """
    results: los resultados CRUDOS del engine (con equity_curve), es decir
    `comparar_estrategias(...)["results"]` — NO el dict de `summary`, que no
    tiene equity_curve. Buy & hold no entra aquí (no pasa por el engine).
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    # Curvas de equity normalizadas a 1
    for nombre, result in results.items():
        equity = result["equity_curve"]["value"]
        (equity / equity.iloc[0]).plot(ax=ax1, label=nombre)

    ax1.set_title(title)
    ax1.set_ylabel("Retorno normalizado")
    ax1.legend()
    ax1.grid(True)

    # Drawdown de la estrategia ML
    ml_equity = results["ml"]["equity_curve"]["value"]
    drawdown_serie = (ml_equity - ml_equity.cummax()) / ml_equity.cummax() * 100
    drawdown_serie.plot(ax=ax2, color="red", alpha=0.7)
    ax2.fill_between(drawdown_serie.index, drawdown_serie, 0, alpha=0.3, color="red")
    ax2.set_ylabel("Drawdown (%)")
    ax2.grid(True)

    plt.tight_layout()
    plt.savefig("backtest_results.png", dpi=150)
    print("Gráfica guardada en backtest_results.png")
```