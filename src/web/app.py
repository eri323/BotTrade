"""App FastAPI: monta la API en /api y sirve el dashboard estático en /."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.web.routes import router

_STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(title="Trading Bot Dashboard")
    app.include_router(router, prefix="/api")
    # check_dir=False: el directorio estático puede no existir aún en tests de la API.
    app.mount(
        "/", StaticFiles(directory=str(_STATIC_DIR), html=True, check_dir=False), name="static"
    )
    return app


app = create_app()
