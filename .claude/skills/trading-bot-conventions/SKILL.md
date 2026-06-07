---
name: trading-bot-conventions
description: Convenciones generales, arquitectura, separación de capas, gestión de riesgo y criterios de go-live del trading bot. Usar SIEMPRE al inicio de cualquier tarea que toque la lógica central: estrategia, ejecución, riesgo, el loop del bot, o decisiones que afecten varias capas. Es la skill más importante del proyecto. Activar también ante dudas sobre el principio paper/live, qué capa puede importar qué, o cuándo el bot puede pasar a dinero real.
---

# Trading Bot — Convenciones Generales

## Objetivo del proyecto

Bot de trading algorítmico sobre cripto (BTC/USD, ETH/USD), velas diarias (swing). Opera en **paper trading** con Alpaca. El objetivo a largo plazo es migrar a live con dinero real SOLO tras cumplir los criterios de validación de §10 del plan (resumidos abajo en "Criterios de go-live").

**Filosofía:** el objetivo NO es ganar dinero rápido. Es construir un sistema verificable, instrumentado y testeable. El aprendizaje y el portafolio profesional son el valor garantizado. Las ganancias son el bonus, no la meta.

---

## Arquitectura en capas

### Mapa de responsabilidades

```
src/data/          → descarga de datos (histórico y stream en vivo)
src/features/      → indicadores técnicos (funciones puras)
src/strategy/      → generación de señales (reglas, luego ML)
src/risk/          → position sizing, stop-loss, circuit breaker
src/execution/     → wrapper de Alpaca (ÚNICA capa que conoce el broker)
src/persistence/   → SQLite: trades, métricas, estado del bot
src/backtest/      → backtester event-driven + métricas financieras
src/bot/           → loop principal en vivo (orquestador)
models/            → pipeline de entrenamiento + modelos .pkl guardados
tests/             → suite completa de pytest
config/settings.py → parámetros del bot, cargados desde .env
```

### Regla de dependencias (NO violar)

```
data/     puede importar: nada del proyecto
features/ puede importar: nada del proyecto (funciones puras)
strategy/ puede importar: features/
risk/     puede importar: nada del proyecto (recibe datos, devuelve decisiones)
execution/puede importar: SDK de Alpaca + config
bot/      puede importar: data, features, strategy, risk, execution, persistence
backtest/ puede importar: data, features, strategy, risk (NO execution)
```

**strategy/ y risk/ son agnósticas al broker.** Si alguna de ellas importa `alpaca`, es un bug de arquitectura.

---

## Los 7 principios no negociables

### 1. Separación de capas estricta
La lógica de estrategia y de riesgo es **pura y testeable** independientemente del broker. Solo `execution/broker.py` sabe de Alpaca. Esto garantiza que el backtester y el bot en vivo usen exactamente la misma lógica de decisión — si el backtest falla, el live también fallaría.

### 2. Un solo flag separa paper de live
`PAPER=true|false` en `.env`. El mismo código corre en ambos modos. Cambiar de paper a live = cambiar ese parámetro. Nunca duplicar lógica entre modos.

### 3. Cero look-ahead
Las features se calculan solo con datos **pasados**. Los labels se calculan con `close.shift(-1)` (precio del día siguiente). El backtester procesa velas en orden cronológico, una por una. Si en algún punto se necesitan datos futuros para calcular algo del presente, es un bug — detener y corregir antes de continuar.

### 4. Riesgo primero
**Ninguna orden llega a `execution/`** sin pasar por `risk/manager.py`. Stop-loss y circuit breaker son obligatorios incluso en paper. Esto entrena el sistema (y al desarrollador) a que las reglas de riesgo siempre estén activas.

### 5. Baseline antes de ML
No se introduce un modelo ML sin comparar contra:
  - Buy-and-hold del activo
  - La estrategia de reglas (RSI/EMA)

Si el ML no vence a ambos de forma robusta en walk-forward validation, **no se promueve** — sin importar cuánto tiempo costó entrenarlo.

### 6. Tests antes de avanzar de fase
No se pasa de una fase a la siguiente sin los tests de esa fase en verde. Sin excepciones.

### 7. Cero secretos en el repo
API keys y secretos solo en `.env` (gitignored). Verificar `.gitignore` antes de cada commit. Usar `.env.example` como plantilla sin valores reales.

---

## Gestión de riesgo — especificación completa

Todos estos valores viven en `config/settings.py`, cargados desde `.env`. Son ajustables sin tocar código.

| Regla | Valor por defecto | Descripción |
|---|---|---|
| `MAX_POSITION_PCT` | 0.20 | Máx. 20% del capital por posición |
| `STOP_LOSS_PCT` | 0.04 | Stop-loss en −4% por posición |
| `TAKE_PROFIT_PCT` | 0.08 | Take-profit en +8% (opcional) |
| `DAILY_LOSS_LIMIT_PCT` | 0.05 | Si el día pierde 5%, el bot deja de operar hasta el siguiente |
| `CIRCUIT_BREAKER_DRAWDOWN_PCT` | 0.20 | Si drawdown total > 20%, el bot se detiene y lanza alerta |
| `MAX_CONCURRENT_POSITIONS` | 2 | Máx. 2 posiciones abiertas simultáneas |

### Circuit breaker — comportamiento esperado
Cuando el drawdown total supera `CIRCUIT_BREAKER_DRAWDOWN_PCT`:
1. El bot cierra todas las posiciones abiertas al precio de mercado.
2. Registra el evento en la base de datos con timestamp y drawdown actual.
3. Envía alerta (Telegram / email).
4. Se detiene completamente. **No reanuda automáticamente** — requiere intervención manual.

Este comportamiento debe estar testeado explícitamente en `tests/test_risk.py`.

---

## Progresión de estrategias

```
Fase 1–2: Reglas simples (RSI + EMA)
   → Baseline determinístico, fácil de testear, punto de referencia.

Fase 3: Modelo ML (RandomForest → XGBoost)
   → Se introduce SOLO si supera al baseline en walk-forward.

Fase 6 (futuro): Reinforcement Learning (Gymnasium + PyTorch)
   → No antes de que el sistema ML esté sólido y validado.
```

---

## Criterios de go-live (§10 del plan — NO negociar)

El bot pasa a dinero real SOLO cuando se cumple TODO:

- [ ] Mínimo **6 meses** (idealmente 12) en paper trading continuo.
- [ ] **Sharpe ratio neto > 1.5** (después de comisiones y slippage simulado).
- [ ] **Max drawdown < 20%**.
- [ ] Mínimo **100 operaciones** completadas (muestra estadísticamente relevante).
- [ ] Sobrevivió al menos **un cambio de régimen** de mercado (corrección significativa).
- [ ] La estrategia ML **supera al baseline buy-and-hold** de forma consistente.
- [ ] Circuit breaker y stop-loss se **activaron y funcionaron** en paper al menos una vez.

**Regla de apagado (escrita y firme):**
*"Si el drawdown en live supera 25%, apago el bot, retiro el capital restante y no vuelvo a fondear hasta identificar y corregir la causa raíz con evidencia documentada."*

Capital inicial en live: máximo USD 300–500 (monto cuya pérdida total sea indiferente).

---

## Convenciones de código

- Funciones de features y métricas: **puras**, tipadas con type hints, con docstring.
- Parámetros configurables: siempre en `config/settings.py`, nunca hardcodeados.
- Nombres en inglés para código; logs y commits en español está bien.
- Commits: `tipo(scope): descripción` — ej. `feat(risk): add circuit breaker`, `test(strategy): add rsi signal tests`.
- `ruff check . && ruff format .` antes de cada commit.
- Cada módulo de lógica tiene su test. Sin test, el módulo no existe.
