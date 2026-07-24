"""CLI: arranca el dashboard web (FastAPI + uvicorn) SOLO en localhost.

Uso:
    python scripts/run_dashboard.py
Luego abre http://127.0.0.1:8000 en el navegador.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permite ejecutar el script directamente.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402


def main() -> None:
    # host 127.0.0.1 → accesible solo desde esta PC (sin exposición a la red/internet).
    uvicorn.run("src.web.app:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
