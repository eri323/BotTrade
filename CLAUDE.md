# CLAUDE.md — Trading Bot (Paper → Live)

> Contrato de comportamiento del proyecto. Claude Code lee este archivo en cada sesión.
> El plan completo está en `PLAN_TRADING_BOT.md`. Las convenciones detalladas, en `.claude/skills/`.

## Qué es este proyecto

Bot de trading algorítmico con ML sobre **cripto** (BTC/USD, ETH/USD), **velas diarias** (estilo swing). Opera en **paper trading** vía Alpaca. Objetivo a largo plazo: pasar a **live con dinero real** SOLO tras cumplir los criterios de validación (ver §10 del plan).

**Filosofía:** el objetivo no es ganar dinero rápido, es construir un sistema verificable, instrumentado y testeado. El aprendizaje y el portafolio son el valor garantizado.

**Fase actual:** `Fase 0 — Setup`  ← actualizar a medida que avanza el proyecto.

## Stack

Python 3.11+ · alpaca-py · pandas / numpy · ta · scikit-learn · xgboost · joblib · pytest / pytest-mock · loguru · SQLite · ruff

## Comandos

```bash
pip install -r requirements.txt
pytest --cov=src                                  # tests + cobertura
ruff check . && ruff format .                     # lint + formato
python scripts/run_backtest.py --symbol BTC/USD   # correr backtest
python scripts/run_bot.py --paper                 # arrancar bot (paper)
python models/train.py --symbol BTC/USD           # entrenar modelo (fase 3)
```

## Principios NO negociables

1. **Separación de capas.** `strategy/` y `risk/` son puras y agnósticas al broker. Solo `execution/` importa Alpaca.
2. **Un flag separa paper de live.** `PAPER=true|false` en `.env`. Nunca dupliques lógica entre modos.
3. **Cero look-ahead.** Las features se calculan solo con datos pasados; los labels con `shift(-1)`. El backtester procesa velas en orden cronológico. Si necesitas el futuro para calcular el presente, es un bug — detente.
4. **Riesgo primero.** Ninguna orden se ejecuta sin pasar por `risk/manager.py`. Stop-loss y circuit breaker son obligatorios, incluso en paper.
5. **Baseline antes de ML.** No se introduce ML sin comparar contra buy-and-hold y la estrategia de reglas. Si el ML no les gana de forma robusta, no se promueve.
6. **Tests antes de avanzar.** No se pasa de una fase a la siguiente sin sus tests en verde.
7. **Cero secretos en el repo.** API keys solo en `.env` (gitignored). Verifica antes de cada commit.

## Arquitectura (dónde vive qué)

| Carpeta | Responsabilidad |
|---|---|
| `src/data/` | Descarga de datos (histórico + stream en vivo) |
| `src/features/` | Indicadores técnicos (funciones puras) |
| `src/strategy/` | Generación de señales (reglas, luego ML) |
| `src/risk/` | Position sizing, stop-loss, circuit breaker |
| `src/execution/` | Wrapper de Alpaca (ÚNICA capa que conoce el broker) |
| `src/persistence/` | SQLite (trades, métricas) |
| `src/backtest/` | Backtester event-driven + métricas |
| `src/bot/` | Loop principal en vivo |
| `models/` | Pipeline de entrenamiento + modelos `.pkl` |
| `tests/` | Suite de pytest |

## Convenciones de código

- Funciones de features y métricas: **puras**, tipadas, con docstring y su test correspondiente.
- Código y nombres en **inglés**; logs y mensajes de commit pueden ir en español.
- Commits atómicos con formato `tipo(scope): descripción` — ej. `feat(risk): add daily loss limit`.
- Formatea con `ruff` antes de cada commit.
- Parámetros configurables (símbolos, umbrales de riesgo) van en `config/settings.py` leyendo de `.env`, nunca hardcodeados.

## Skills del proyecto (`.claude/skills/`)

Lee la skill relevante ANTES de trabajar en su área:

- **trading-bot-conventions** → arquitectura, gestión de riesgo, criterios de go-live (leer primero, ante cualquier duda de diseño).
- **alpaca-integration** → SDK `alpaca-py`, paper vs live, datos de cripto, envío de órdenes, idempotencia.
- **ml-pipeline** → entrenamiento, split temporal, anti-leakage, walk-forward, métricas, reentrenamiento.
- **backtesting-engine** → backtester event-driven, simetría con el loop en vivo, métricas financieras.
- **testing-pytest** → patrones de test, mocks del API de Alpaca, qué cubrir.

## Qué NO hacer

- ❌ Usar `train_test_split` aleatorio en series temporales (rompe la dependencia temporal — usa split cronológico / walk-forward).
- ❌ Usar la librería deprecada `alpaca-trade-api`; usar `alpaca-py`.
- ❌ Commitear `.env`, `*.db` o modelos grandes.
- ❌ Saltarse la capa de riesgo "para probar rápido".
- ❌ Pasar a live sin cumplir TODOS los criterios de §10 del plan.
