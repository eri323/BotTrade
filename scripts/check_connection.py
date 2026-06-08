"""Verifica la conexión con Alpaca y muestra el estado de la cuenta paper.

Uso:
    python scripts/check_connection.py

Requiere ALPACA_API_KEY / ALPACA_SECRET_KEY en `.env` (entorno paper).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permite ejecutar el script directamente.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# La consola de Windows usa cp1252 por defecto y rompe con acentos/símbolos.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

from config.settings import settings  # noqa: E402
from src.execution.broker import Broker  # noqa: E402


def main() -> None:
    if not settings.ALPACA_API_KEY or not settings.ALPACA_SECRET_KEY:
        print("[ERROR] Faltan ALPACA_API_KEY / ALPACA_SECRET_KEY en .env")
        sys.exit(1)

    mode = "PAPER" if settings.PAPER else "LIVE"
    print(f"Conectando a Alpaca en modo {mode}...")

    broker = Broker()
    try:
        account = broker.get_account()
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] No se pudo conectar: {e}")
        sys.exit(1)

    print("[OK] Conexion exitosa")
    print(f"  Estado de la cuenta : {account.status}")
    print(f"  Cash                : {account.cash}")
    print(f"  Buying power        : {account.buying_power}")
    print(f"  Portfolio value     : {account.portfolio_value}")

    positions = broker.list_positions()
    print(f"  Posiciones abiertas : {len(positions)}")
    for pos in positions:
        print(f"    - {pos.symbol}: qty={pos.qty}, P&L={pos.unrealized_pl}")


if __name__ == "__main__":
    main()
