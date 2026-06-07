# PLAN DE PROYECTO — Trading Bot con ML (Paper → Live)

> Documento de especificación para ejecutar con **Claude Code**.
> Léelo completo antes de empezar. Ejecuta **fase por fase**, sin saltarte los tests.

---

## 1. Objetivo

**Corto plazo (ahora):** construir un bot de trading algorítmico que opere en **paper trading** (dinero ficticio) sobre cripto, con una arquitectura limpia, instrumentada y testeada, que sirva como proyecto de aprendizaje de Machine Learning aplicado e ingeniería de software.

**Largo plazo (6–12+ meses):** migrar el mismo sistema a **live trading con dinero real** (monto inicial pequeño: USD 300–500 máx.), **solo si** el sistema demuestra métricas de éxito sostenidas en paper (ver §10).

**Principio rector:** el objetivo NO es ganar dinero rápido. Es construir un sistema verificable, instrumentado y testeable. Si el bot resulta rentable, es un bonus; el valor garantizado es el aprendizaje y el portafolio profesional.

---

## 2. Decisiones de diseño (ya tomadas)

| Decisión | Elección | Justificación |
|---|---|---|
| Mercado | **Cripto (BTC/USD, ETH/USD)** | 24/7, sin regla PDT, fraccional desde ~$10 |
| Temporalidad | **Swing — velas diarias (1D)** | Menos ruido, menos slippage, menos overfitting, mapea con ML tabular |
| Motor | **Progresión: reglas → ML → RL** | Baseline antes de ML (mentalidad científica/QA) |
| Lenguaje | **Python 3.11+** | Ecosistema ML, Alpaca SDK oficial |
| Broker/Datos | **Alpaca** (`alpaca-py`) | Paper gratis e ilimitado, mismo código para live |
| Persistencia | **SQLite** | Simple, suficiente, sin servidor |
| Testing | **pytest + pytest-mock** | Mocks del API, cobertura de lógica crítica |
| Versionado | **Git + GitHub** desde commit 0 | Historial, CI |
| Infra dev | **Local** | Aprender primero |
| Infra prod | **VPS (DigitalOcean ~$6/mes)** | 24/7 sin depender del PC |
| Dashboard | **Streamlit** (fase posterior) | Dashboard en Python puro, sin JS |

---

## 3. Stack tecnológico

```
# Core
python >= 3.11
alpaca-py            # SDK oficial de Alpaca (trading + market data)
pandas, numpy        # manipulación de datos
ta                   # indicadores técnicos (RSI, EMA, Bollinger, ATR...)

# Machine Learning
scikit-learn         # RandomForest, métricas, preprocessing
xgboost              # gradient boosting (Géron Cap. 7)
joblib               # persistencia de modelos (.pkl)

# Infraestructura
python-dotenv        # variables de entorno / secretos
loguru               # logging estructurado
SQLAlchemy           # ORM sobre SQLite (o sqlite3 directo)

# Testing y calidad
pytest
pytest-mock
pytest-cov           # cobertura
ruff                 # linter + formatter

# Visualización (backtest y, después, dashboard)
matplotlib           # gráficas de backtest
streamlit            # dashboard (fase 5)

# Futuro (RL — fase 6, NO instalar todavía)
# gymnasium, stable-baselines3, torch
```

---

## 4. Arquitectura y principios de diseño

### Principios NO negociables

1. **Separación de capas estricta.** La lógica de estrategia y de riesgo debe ser **pura, testeable y agnóstica al broker**. La capa de ejecución abstrae paper vs live.
2. **Un solo flag separa paper de live.** El mismo código corre en ambos modos. Cambiar de paper a live = cambiar `PAPER=true` a `PAPER=false` en `.env`. Nada más.
3. **Simetría backtest ↔ live.** El backtester procesa velas secuencialmente, igual que el loop en vivo. Esto evita look-ahead bias por diseño y hace que lo validado en backtest se comporte igual en vivo.
4. **Gestión de riesgo obligatoria desde el día uno**, incluso en paper (ver §7).
5. **Sin secretos en el repo. Jamás.** API keys solo en `.env` (gitignored).

### Diagrama de capas

```
┌─────────────────────────────────────────────────────┐
│                      bot/ (orquestador)              │
│         loop en vivo · paper o live según flag       │
└───┬─────────────┬──────────────┬─────────────┬───────┘
    │             │              │             │
    ▼             ▼              ▼             ▼
┌────────┐  ┌──────────┐  ┌───────────┐  ┌──────────┐
│ data/  │  │features/ │  │ strategy/ │  │  risk/   │
│ fetch  │  │ pure fns │  │ señales   │  │ stops,   │
│ datos  │  │ RSI,EMA  │  │ rule/ML   │  │ sizing   │
└────────┘  └──────────┘  └───────────┘  └──────────┘
                                │              │
                                ▼              ▼
                          ┌──────────────────────────┐
                          │      execution/          │
                          │  abstrae Alpaca paper/live│
                          └──────────────────────────┘
                                       │
                                       ▼
                          ┌──────────────────────────┐
                          │  persistence/ (SQLite)   │
                          │  trades, métricas, logs  │
                          └──────────────────────────┘

backtest/  →  usa data/ + features/ + strategy/ + risk/  (sin execution real)
models/    →  scripts de entrenamiento + modelos .pkl guardados
```

---

## 5. Estructura de carpetas

```
trading-bot/
├── .env.example              # plantilla de variables (SIN valores reales)
├── .gitignore                # incluye .env, *.pkl grandes, __pycache__, *.db
├── README.md
├── requirements.txt
├── pyproject.toml            # config de ruff, pytest
├── config/
│   └── settings.py           # carga .env, parámetros del bot (símbolos, riesgo)
├── src/
│   ├── data/
│   │   ├── historical.py     # descarga velas históricas (Alpaca)
│   │   └── live.py           # stream de datos en vivo (WebSocket)
│   ├── features/
│   │   └── indicators.py     # funciones puras: rsi(), ema(), bollinger()...
│   ├── strategy/
│   │   ├── base.py           # interfaz Strategy (método generate_signal)
│   │   ├── rule_based.py     # estrategia de reglas (RSI/EMA) — BASELINE
│   │   └── ml_strategy.py    # estrategia que usa un modelo .pkl (fase 3)
│   ├── risk/
│   │   └── manager.py        # position sizing, stop-loss, circuit breaker
│   ├── execution/
│   │   └── broker.py         # wrapper Alpaca: submit_order, get_positions...
│   ├── persistence/
│   │   ├── db.py             # conexión SQLite, esquema
│   │   └── repository.py     # guardar/leer trades y métricas
│   ├── backtest/
│   │   ├── engine.py         # backtester event-driven (procesa velas en orden)
│   │   └── metrics.py        # Sharpe, max drawdown, win rate, profit factor
│   └── bot/
│       └── runner.py         # loop principal en vivo
├── models/
│   ├── train.py              # pipeline de entrenamiento (Géron Cap. 2)
│   └── saved/                # modelos versionados: model_v1.pkl, model_v2.pkl
├── scripts/
│   ├── run_backtest.py       # CLI: corre un backtest
│   └── run_bot.py            # CLI: arranca el bot en paper/live
└── tests/
    ├── test_indicators.py
    ├── test_strategy.py
    ├── test_risk.py
    ├── test_backtest.py
    └── test_broker.py        # con mocks del API de Alpaca
```

---

## 6. Mapeo con los libros (Aurélien Géron)

El proyecto sigue deliberadamente la estructura del libro para reforzar tu aprendizaje:

| Concepto del libro | Dónde se aplica en el proyecto |
|---|---|
| **Cap. 1** — Batch vs online learning, *model rot / data drift* | Justifica el **reentrenamiento periódico** del modelo (§9, fase 3). El mercado evoluciona → el modelo envejece → se reentrena. |
| **Cap. 2** — Pipeline end-to-end, split correcto, baseline, métricas | Estructura de `models/train.py`. Split **temporal** (NO aleatorio). Baseline buy-and-hold a vencer. |
| **Cap. 3** — Clasificación, precision/recall, matriz de confusión | Evaluación del modelo: el bot predice "¿sube >X% mañana?" (clasificación binaria). |
| **Cap. 6–7** — Árboles, RandomForest, ensembles, XGBoost | El modelo de la fase 3: empezar con RandomForest, luego XGBoost. |
| **Cap. 10** — Redes neuronales con PyTorch | Versión futura del modelo (opcional). |
| **Cap. 18** — Reinforcement Learning | Fase 6, lejana. Agente que aprende por prueba y error. |

### Conceptos clave de finanzas (no están en Géron pero son críticos)

- **Data leakage:** nunca usar información del futuro como feature. Las features se calculan solo con datos *pasados*; el label se calcula con `shift(-1)` (precio del día siguiente). Esto se testea explícitamente.
- **Non-stationarity:** el mercado cambia de régimen. Por eso validamos en periodos de crisis y reentrenamos.
- **Walk-forward validation:** en series temporales NO se usa k-fold aleatorio. Se entrena en el pasado y se valida en el futuro, avanzando la ventana. (El k-fold clásico de Géron Cap. 2 rompe la dependencia temporal — aquí se adapta.)
- **Métricas reales:** accuracy NO basta. Lo que importa es **Sharpe ratio, max drawdown, profit factor, win rate**.

---

## 7. Especificación de gestión de riesgo (OBLIGATORIA)

La capa `risk/manager.py` debe implementar y **testear** estas reglas. El bot NUNCA ejecuta una orden sin pasar por aquí:

| Regla | Valor inicial | Descripción |
|---|---|---|
| Tamaño máx. por posición | 20% del capital | Nunca poner más del 20% en una sola operación |
| Stop-loss | −4% | Toda posición tiene stop-loss obligatorio |
| Take-profit (opcional) | +8% | Cerrar en ganancia si se alcanza |
| Límite de pérdida diaria | −5% | Si el día pierde 5%, el bot deja de operar hasta el día siguiente |
| **Circuit breaker (drawdown)** | −20% | Si el drawdown total supera 20%, el bot **se detiene y manda alerta**. Requiere intervención manual. |
| Posiciones concurrentes máx. | 2 | No más de 2 posiciones abiertas a la vez |

Todos estos valores van en `config/settings.py` para poder ajustarlos sin tocar código.

---

## 8. Plan por fases

> Cada fase tiene: **objetivo**, **tareas**, **entregable**, **criterio de "done"**. No se avanza de fase sin tests pasando.

### FASE 0 — Setup del proyecto
- **Objetivo:** repo funcional con esqueleto y CI.
- **Tareas:**
  1. Crear cuenta **paper** en alpaca.markets (sin fondear). Obtener API key + secret del entorno *paper*.
  2. Inicializar repo Git + GitHub. Crear `.gitignore` (incluir `.env`, `*.db`, `models/saved/*.pkl`).
  3. Crear estructura de carpetas (§5) y `requirements.txt`.
  4. `.env.example` con las variables (§Anexo A). El `.env` real (con keys) NO se commitea.
  5. Configurar `ruff` y `pytest` en `pyproject.toml`.
  6. GitHub Actions: workflow que corre `pytest` y `ruff` en cada push.
- **Entregable:** repo que clona, instala dependencias y corre `pytest` (aunque sea 1 test dummy) en verde.
- **Done:** CI pasando, secretos fuera del repo.

### FASE 1 — Datos, indicadores y backtester
- **Objetivo:** poder backtestear una estrategia de reglas contra datos históricos reales.
- **Tareas:**
  1. `data/historical.py`: descargar 3–5 años de velas diarias de BTC/USD y ETH/USD vía `CryptoHistoricalDataClient`.
  2. `features/indicators.py`: funciones **puras** — `rsi()`, `ema()`, `bollinger()`, `atr()`, `pct_return()`. Cada una con tests.
  3. `strategy/base.py`: interfaz `Strategy` con método `generate_signal(df) -> "BUY"|"SELL"|"HOLD"`.
  4. `strategy/rule_based.py`: estrategia baseline. Ej.: comprar si EMA(9) cruza arriba de EMA(21) y RSI < 70; vender si cruza abajo o RSI > 75.
  5. `backtest/engine.py`: backtester **event-driven** (procesa velas una por una, en orden cronológico — esto evita look-ahead por diseño).
  6. `backtest/metrics.py`: `sharpe_ratio()`, `max_drawdown()`, `win_rate()`, `profit_factor()`, `total_return()`.
  7. `scripts/run_backtest.py`: CLI que corre el backtest y muestra métricas + gráfica de equity curve.
- **Entregable:** backtest reproducible con métricas y gráfica.
- **Done:** tests de indicadores y backtester en verde. Baseline **buy-and-hold** calculado como referencia a vencer.

### FASE 2 — Bot en vivo (paper, reglas)
- **Objetivo:** el bot opera en paper trading 24/7 con la estrategia de reglas.
- **Tareas:**
  1. `execution/broker.py`: wrapper sobre `TradingClient(paper=True)`. Métodos: `submit_order()`, `get_position()`, `get_account()`, `close_position()`. **Idempotencia**: no duplicar órdenes.
  2. `risk/manager.py`: implementar todas las reglas de §7.
  3. `persistence/db.py` + `repository.py`: SQLite con tablas `trades` y `daily_metrics`.
  4. `bot/runner.py`: loop principal — obtener datos → calcular features → señal → pasar por risk → ejecutar → registrar. Manejo robusto de errores (reconexión, rate limits, timeouts).
  5. `scripts/run_bot.py`: CLI para arrancar (`--paper` por defecto).
  6. Logging estructurado con `loguru` (a archivo + consola).
- **Entregable:** bot corriendo en paper localmente, registrando trades en SQLite.
- **Done:** `test_broker.py` con **mocks** del API en verde. `test_risk.py` cubriendo todos los límites. Bot corre 1 semana sin crashear.

### FASE 3 — Modelo ML
- **Objetivo:** reemplazar (o complementar) las reglas con un modelo entrenado, y demostrar que **vence al baseline**.
- **Tareas:**
  1. `models/train.py` — pipeline estilo Géron Cap. 2:
     - Descargar histórico → feature engineering → crear label (`close.shift(-1) > close * (1+umbral)`).
     - **Split temporal**: train (años viejos) / validation / test (año más reciente, se toca 1 vez).
     - Entrenar `RandomForestClassifier` (luego `XGBClassifier`).
     - Evaluar: precision, recall, matriz de confusión (Cap. 3) **y** métricas financieras backtesteadas.
     - **Walk-forward validation** para estimar robustez.
     - Análisis de **feature importance**.
     - Guardar `models/saved/model_vN.pkl` con `joblib`.
  2. `strategy/ml_strategy.py`: carga el `.pkl` y genera señales con `model.predict()`.
  3. Comparar en backtest: **buy-and-hold vs reglas vs ML**. El ML solo se promueve si supera a ambos de forma robusta (no solo en un periodo afortunado).
  4. Documentar la **cadencia de reentrenamiento** (ej.: mensual) — conecta con *model rot* (Cap. 1).
- **Entregable:** modelo entrenado + comparativa documentada de las 3 estrategias.
- **Done:** tests de `train.py` (sin leakage — test explícito de que no se usan datos futuros). ML supera baseline en walk-forward.

### FASE 4 — Hardening + despliegue en VPS
- **Objetivo:** bot 24/7 en la nube, robusto y monitoreado.
- **Tareas:**
  1. `Dockerfile` para contenerizar el bot.
  2. Provisionar VPS (DigitalOcean droplet ~$6/mes). SSH con llaves, firewall básico.
  3. `systemd` o `supervisor` para mantener el proceso vivo y reiniciar si cae.
  4. **Alertas**: integración con Telegram o email para notificar cada trade, errores y activación del circuit breaker.
  5. Backups automáticos de la base SQLite.
- **Entregable:** bot corriendo 24/7 en paper en el VPS, con alertas funcionando.
- **Done:** sobrevive reinicio del servidor (auto-restart). Alertas llegan al celular.

### FASE 5 — Dashboard (opcional, recomendado)
- **Objetivo:** interfaz visual para monitorear sin SSH.
- **Tareas:**
  1. `dashboard/app.py` con **Streamlit**: lee de SQLite y muestra equity curve, P&L, historial de trades, Sharpe y drawdown actuales.
  2. Botón de start/stop del bot (vía flag en DB o señal).
  3. Servir el dashboard en el VPS (puerto protegido).
- **Entregable:** dashboard accesible desde el browser (PC/celular).
- **Done:** el dashboard refleja en tiempo real lo que hace el bot. *(El bot sigue corriendo aunque el dashboard esté cerrado — son procesos independientes.)*

### FASE 6 — Futuro lejano (NO ahora)
- Modelo con **PyTorch / red neuronal** (Géron Cap. 10).
- Agente de **Reinforcement Learning** con Gymnasium (Cap. 18).
- **Migración a LIVE** — solo tras cumplir los criterios de §10.

---

## 9. Instrucciones para Claude Code

1. **Trabaja fase por fase.** No empieces la fase N+1 hasta que los tests de la fase N estén en verde.
2. **Tests primero o junto al código.** Cada módulo de lógica (indicadores, estrategia, riesgo, backtester) necesita su test antes de avanzar.
3. **Commits atómicos y descriptivos.** Un commit por unidad lógica de trabajo. Mensajes claros (ej.: `feat(risk): add stop-loss enforcement`).
4. **Nunca hardcodees secretos.** Todo va por `.env` y `config/settings.py`. Verifica que `.env` esté en `.gitignore`.
5. **Respeta la abstracción paper/live.** La capa `execution/` es la única que sabe de Alpaca. Estrategia y riesgo no deben importar nada de Alpaca.
6. **Mocks para tests del broker.** `test_broker.py` no debe llamar al API real; usa `pytest-mock`.
7. **El backtester procesa velas en orden cronológico**, una por una. Si en algún punto necesitas datos futuros para calcular algo del presente, es un bug de look-ahead — detente y corrígelo.
8. **Documenta en el README** cómo instalar, configurar el `.env`, correr un backtest y arrancar el bot.
9. Antes de cada fase, **resume qué vas a hacer y espera confirmación** si hay decisiones ambiguas.
10. **Usa `ruff` para formatear** antes de cada commit.

---

## 10. Métricas de éxito y criterios de "go-live"

El bot **NO pasa a dinero real** hasta cumplir TODO esto en paper trading:

- [ ] **Mínimo 6 meses** (idealmente 12) corriendo en paper de forma continua.
- [ ] **Sharpe ratio neto > 1.5** (después de comisiones y slippage simulado).
- [ ] **Max drawdown < 20%**.
- [ ] **Mínimo 100 operaciones** registradas (muestra estadísticamente relevante).
- [ ] Haber **sobrevivido al menos un cambio de régimen** de mercado (una corrección fuerte).
- [ ] La estrategia ML **supera al baseline buy-and-hold** de forma consistente.
- [ ] Circuit breaker y stop-loss **probados en condiciones reales de paper** (que de verdad se hayan activado y funcionado).

**Si se cumple todo:** fondear con USD 300–500 (monto cuya pérdida total te sea indiferente), manteniendo el paper corriendo en paralelo como control.

**Regla de apagado (escrita y firmada):** *"Si el drawdown en live supera 25%, apago el bot, retiro el capital restante y no vuelvo a fondear hasta identificar y corregir la causa raíz con evidencia documentada."*

---

## 11. Seguridad

- API keys solo en `.env` (gitignored). Usa el `.env.example` como plantilla.
- En Alpaca, considera usar keys con permisos mínimos necesarios.
- En el VPS: acceso solo por llave SSH (no password), firewall (`ufw`) cerrando todo menos lo necesario.
- El dashboard (fase 5) detrás de autenticación básica o túnel; nunca expuesto abierto a internet.
- Cobertura SIPC de Alpaca protege contra fraude del broker, **NO contra pérdidas de trading**. No la confundas con un seguro.

---

## Anexo A — Variables de entorno (`.env.example`)

```bash
# Alpaca — entorno PAPER (cambiar a live solo tras cumplir §10)
ALPACA_API_KEY=tu_key_aqui
ALPACA_SECRET_KEY=tu_secret_aqui
PAPER=true                      # true=paper, false=live

# Parámetros de trading
SYMBOLS=BTC/USD,ETH/USD
TIMEFRAME=1Day

# Gestión de riesgo
MAX_POSITION_PCT=0.20
STOP_LOSS_PCT=0.04
TAKE_PROFIT_PCT=0.08
DAILY_LOSS_LIMIT_PCT=0.05
CIRCUIT_BREAKER_DRAWDOWN_PCT=0.20
MAX_CONCURRENT_POSITIONS=2

# Alertas (fase 4)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Base de datos
DATABASE_PATH=./trading_bot.db
```

## Anexo B — Comandos útiles

```bash
# Setup inicial
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Correr tests + cobertura
pytest --cov=src

# Linter
ruff check . && ruff format .

# Correr un backtest
python scripts/run_backtest.py --symbol BTC/USD --start 2020-01-01

# Arrancar el bot en paper
python scripts/run_bot.py --paper

# Entrenar el modelo (fase 3)
python models/train.py --symbol BTC/USD
```

---

## Anexo C — Consejo de Géron a tener presente

> *"No te lances a aguas profundas demasiado rápido: aunque el deep learning es una de las áreas más emocionantes del ML, debes dominar primero los fundamentos. La mayoría de los problemas se resuelven bastante bien con técnicas más simples como los random forests y los métodos de ensemble."*

Aplica literal a este proyecto: **reglas y RandomForest antes que redes neuronales y RL.** No te saltes el baseline.
