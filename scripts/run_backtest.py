"""CLI: corre un backtest (buy-and-hold vs reglas) y muestra métricas + gráfica.

Uso:
    python scripts/run_backtest.py --symbol BTC/USD --start 2020-01-01

Requiere keys de Alpaca en `.env` (entorno paper) para descargar los datos.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

# Permite ejecutar el script directamente (python scripts/run_backtest.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# La consola de Windows usa cp1252 por defecto y rompe con acentos/símbolos.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

import matplotlib  # noqa: E402

matplotlib.use("Agg")  # backend sin ventana (guarda a archivo)

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.backtest.compare import run_comparison  # noqa: E402
from src.data.historical import fetch_daily_bars  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backtest: buy-and-hold vs estrategia de reglas")
    p.add_argument("--symbol", default="BTC/USD", help="Símbolo (ej. BTC/USD)")
    p.add_argument("--start", default="2020-01-01", help="Fecha inicio (YYYY-MM-DD)")
    p.add_argument("--end", default=None, help="Fecha fin (YYYY-MM-DD); por defecto hoy")
    p.add_argument("--capital", type=float, default=10_000.0, help="Capital inicial")
    p.add_argument("--out", default="backtest_results.png", help="Ruta de la gráfica")
    p.add_argument("--no-plot", action="store_true", help="No generar la gráfica")
    return p.parse_args()


def _plot(df_raw: pd.DataFrame, results: dict, out_path: str) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))

    # Buy & hold normalizado.
    bh = df_raw["close"] / df_raw["close"].iloc[0]
    bh.plot(ax=ax, label="buy_hold", alpha=0.8)

    # Estrategia de reglas normalizada.
    rules_eq = results["rules"]["equity_curve"]["value"]
    (rules_eq / rules_eq.iloc[0]).plot(ax=ax, label="rules", alpha=0.8)

    ax.set_title("Equity curves (normalizadas)")
    ax.set_ylabel("Retorno normalizado")
    ax.legend()
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"\nGráfica guardada en {out_path}")


def main() -> None:
    args = _parse_args()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    end = datetime.fromisoformat(args.end).replace(tzinfo=UTC) if args.end else datetime.now(UTC)

    print(f"Descargando {args.symbol} ({args.start} → {args.end or 'hoy'})...")
    df_raw = fetch_daily_bars(args.symbol, start, end)
    print(f"  {len(df_raw)} velas diarias descargadas.")

    out = run_comparison(df_raw, initial_capital=args.capital)

    print("\n=== Comparativa de estrategias ===")
    print(pd.DataFrame(out["summary"]).T.to_string())

    if not args.no_plot:
        _plot(df_raw, out["results"], args.out)


if __name__ == "__main__":
    main()
