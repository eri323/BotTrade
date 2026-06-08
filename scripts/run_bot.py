"""CLI: arranca el bot en paper/live según el flag PAPER de `.env`.

Uso:
    python scripts/run_bot.py --paper

El modo real (paper vs live) lo determina `PAPER` en `.env`. El flag `--paper`
es solo una salvaguarda explícita: si PAPER=false (live) el bot exige `--live`.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Permite ejecutar el script directamente (python scripts/run_bot.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# La consola de Windows usa cp1252 por defecto y rompe con acentos/símbolos.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

import pandas as pd  # noqa: E402
from loguru import logger  # noqa: E402

from config.settings import settings  # noqa: E402
from src.backtest.compare import default_risk  # noqa: E402
from src.bot.runner import TradingBot  # noqa: E402
from src.data.historical import fetch_daily_bars  # noqa: E402
from src.execution.broker import Broker  # noqa: E402
from src.persistence.db import get_connection, init_db  # noqa: E402
from src.persistence.repository import Repository  # noqa: E402
from src.strategy.rule_based import RuleBasedStrategy  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Arranca el bot de trading (paper/live)")
    p.add_argument("--paper", action="store_true", help="Confirmar modo paper (por defecto)")
    p.add_argument("--live", action="store_true", help="Confirmar modo live (dinero real)")
    p.add_argument("--interval", type=int, default=3600, help="Segundos entre ciclos")
    p.add_argument("--lookback-days", type=int, default=200, help="Días de histórico por ciclo")
    p.add_argument("--once", action="store_true", help="Ejecutar un solo ciclo y salir")
    return p.parse_args()


def _setup_logging() -> None:
    logger.add("logs/bot_{time:YYYY-MM-DD}.log", rotation="1 day", retention="30 days")


def main() -> None:
    args = _parse_args()
    _setup_logging()

    # Salvaguarda: no operar en live por accidente.
    if not settings.PAPER and not args.live:
        logger.error("PAPER=false (live) pero no se pasó --live. Abortando por seguridad.")
        sys.exit(1)
    mode = "PAPER" if settings.PAPER else "LIVE"
    logger.info(f"Arrancando bot en modo {mode}. Símbolos: {settings.SYMBOLS}")

    broker = Broker()
    strategy = RuleBasedStrategy()
    risk = default_risk()
    conn = get_connection()
    init_db(conn)
    repository = Repository(conn)

    bot = TradingBot(broker, strategy, risk, repository, symbols=settings.SYMBOLS)

    def fetch(symbol: str) -> pd.DataFrame:
        end = datetime.now(UTC)
        start = end - timedelta(days=args.lookback_days)
        return fetch_daily_bars(symbol, start, end)

    if args.once:
        actions = bot.run_once(fetch)
        logger.info(f"Ciclo único completado: {actions}")
        return

    bot.run(fetch, interval_seconds=args.interval)


if __name__ == "__main__":
    main()
