# Trading Bot (Paper → Live)

Bot de trading algorítmico con ML sobre cripto (BTC/USD, ETH/USD), velas diarias
(swing). Opera en **paper trading** vía Alpaca. El objetivo es construir un sistema
verificable, instrumentado y testeado; el paso a dinero real solo ocurre tras cumplir
los criterios de validación (§10 del plan).

> Fase actual: **Fase 0 — Setup**. Ver `PLAN_TRADING_BOT.md` para el plan completo y
> `.claude/skills/` para las convenciones por área.

## Setup

```bash
python -m venv venv
# Windows:  venv\Scripts\activate
# Unix:     source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # y rellena tus keys de Alpaca (entorno paper)
```

> El `.env` real (con keys) **no se commitea** — está en `.gitignore`.

## Comandos

```bash
pytest --cov=src                  # tests + cobertura
ruff check . && ruff format .     # lint + formato

# (disponibles a partir de fases posteriores)
python scripts/run_backtest.py --symbol BTC/USD
python scripts/run_bot.py --paper
python models/train.py --symbol BTC/USD
```

## Arquitectura

| Carpeta | Responsabilidad |
|---|---|
| `config/` | Parámetros del bot, cargados desde `.env` |
| `src/data/` | Descarga de datos (histórico + stream en vivo) |
| `src/features/` | Indicadores técnicos (funciones puras) |
| `src/strategy/` | Generación de señales (reglas, luego ML) |
| `src/risk/` | Position sizing, stop-loss, circuit breaker |
| `src/execution/` | Wrapper de Alpaca (única capa que conoce el broker) |
| `src/persistence/` | SQLite (trades, métricas) — `sqlite3` directo |
| `src/backtest/` | Backtester event-driven + métricas |
| `src/bot/` | Loop principal en vivo |
| `models/` | Pipeline de entrenamiento + modelos `.pkl` |
| `tests/` | Suite de pytest |
