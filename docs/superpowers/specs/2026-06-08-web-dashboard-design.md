# Diseño — Dashboard web del trading bot

> Fecha: 2026-06-08
> Estado: aprobado en brainstorming, pendiente de plan de implementación.

## Objetivo

Construir una interfaz web local para operar el bot con botones (iniciar / detener) y
ver el estado, la cuenta, las posiciones, el historial de trades, las métricas y una
equity curve. Adelanta el dashboard respecto al orden del plan (que ponía el VPS
primero), pero se mantiene **solo en localhost** — sin exposición a internet, sin login.

## Alcance y decisiones tomadas

- **Dónde corre:** solo en la PC del usuario (`http://localhost`). Sin autenticación ni
  seguridad de red en esta fase. El acceso remoto queda para la fase de VPS.
- **Al detener el bot:** se pregunta cada vez. Si hay posiciones abiertas, un diálogo
  ofrece "Solo detener" o "Cerrar todo y detener".
- **Qué muestra:** estado del bot + cuenta, posiciones abiertas, historial + métricas, y
  equity curve.
- **Ciclo de vida del bot:** corre en un hilo dentro del proceso del servidor web
  (Opción A). Parada ordenada vía `threading.Event`.
- **Stack:** FastAPI (backend Python) + frontend sin build tooling (HTML + JS plano +
  Chart.js por CDN). Sin React/Node.

## Principios respetados (CLAUDE.md)

- **Separación de capas:** la capa web (`src/web/`) lee `Broker` y `Repository`; **no
  duplica** lógica de estrategia ni de riesgo. Solo `execution/` conoce Alpaca.
- **Un flag separa paper de live:** el arranque respeta `PAPER`. Si es live, exige
  confirmación explícita (equivalente al `--live` del CLI).
- **Riesgo primero:** no se altera el camino de riesgo del bot. El cierre de posiciones
  al detener es ordenado (no se mata el hilo a la fuerza).
- **Tests antes de avanzar:** la lógica nueva (manager, P&L, métricas diarias, endpoints)
  va con sus tests.

## Arquitectura y componentes

Carpeta nueva `src/web/`:

```
src/web/
  app.py          # FastAPI: monta rutas y sirve el frontend estático
  bot_manager.py  # ciclo de vida del bot (hilo + estado en memoria) — pieza clave
  routes.py       # endpoints JSON
  static/
    index.html    # dashboard de una sola página
    app.js        # fetch + polling + render
    style.css     # estilos (modo oscuro, sobrio)
scripts/run_dashboard.py   # arranca el servidor: python scripts/run_dashboard.py
```

### `bot_manager.py` (singleton)

Objeto único que gestiona el bot:

- **Estado en memoria:** `running | stopped`, modo (paper/live), último ciclo, próximo
  ciclo, último error, símbolos, número de posiciones.
- **`start()`:** arma el bot igual que `run_bot.py` (`Broker`, `RuleBasedStrategy`,
  `default_risk()`, `Repository`) y lanza el loop en un `threading.Thread`. Idempotente:
  si ya corre, no hace nada. Rechaza arranque en live sin confirmación explícita.
- **`stop(close_positions: bool)`:** activa el `threading.Event`, espera a que termine el
  ciclo en curso; si `close_positions=True`, recorre las posiciones llamando
  `broker.close_position(symbol)` y registra los cierres en la BD.
- **`status()`:** devuelve el estado para el endpoint.

### Cambio en `bot.run()`

Aceptar un `stop_event: threading.Event | None = None` opcional y revisarlo entre ciclos
(y durante la espera del intervalo, para que la parada sea reactiva). Sin evento =
comportamiento actual idéntico. El CLI `run_bot.py` no cambia su comportamiento.

## Iniciar / Detener

**Iniciar** (`POST /api/start`):
- Arma y lanza el bot en un hilo.
- Salvaguarda: si `PAPER=false`, rechaza salvo confirmación explícita.
- Idempotente.

**Detener** (flujo del frontend):
1. Click en "Detener" → `GET /api/positions` para saber si hay posiciones abiertas.
2. Sin posiciones → `POST /api/stop?close_positions=false` directo.
3. Con posiciones → diálogo: "Tienes N posiciones abiertas. ¿Qué hago?"
   - "Solo detener" → `POST /api/stop?close_positions=false`
   - "Cerrar todo y detener" → `POST /api/stop?close_positions=true`
4. El manager hace parada ordenada y, si corresponde, cierra posiciones y las registra.

## Endpoints

| Endpoint | Devuelve | Fuente |
|---|---|---|
| `GET /api/status` | running/stopped, modo, último/próximo ciclo, error, # posiciones | `bot_manager` (memoria) |
| `GET /api/account` | valor portafolio, efectivo, P&L total y del día | Alpaca vía `Broker` |
| `GET /api/positions` | posiciones abiertas y su P&L | Alpaca vía `Broker` |
| `GET /api/trades` | historial de operaciones | `trading_bot.db` (`Repository`) |
| `GET /api/metrics` | win rate, profit factor, Sharpe, max drawdown, retorno total | `metrics.py` sobre la BD |
| `GET /api/equity` | serie de valor del portafolio en el tiempo | tabla `daily_metrics` |
| `POST /api/start` | arranca el bot | `bot_manager` |
| `POST /api/stop?close_positions=bool` | detiene el bot | `bot_manager` |

El frontend hace **polling** cada pocos segundos. Sin websockets (innecesario para velas
diarias).

## Arreglos de datos (parte del trabajo)

Dos huecos del código base que el dashboard hace visibles y necesarios:

1. **P&L real por trade.** Hoy `runner._record` guarda `pnl=0` siempre. Al cerrar una
   posición (por señal o stop-loss), capturar el P&L realizado a partir de la posición de
   Alpaca (`unrealized_pl`) en el momento del cierre y guardarlo en el trade de venta.
   Cambio acotado en `src/bot/runner.py`. Sin esto, win rate y profit factor no significan
   nada.

2. **Poblar `daily_metrics`.** Hoy nadie llama `save_daily_metric`, la tabla está vacía y
   no hay equity curve. Al final de cada ciclo del bot, guardar una fila: valor del
   portafolio (de Alpaca), P&L del día y drawdown. La equity curve se construye sola
   mientras el bot corre.

## Frontend (una sola página)

Layout, modo oscuro, sobrio, indicadores verde/rojo para P&L:

```
┌────────────────────────────────────────────────────────────┐
│  🤖 Trading Bot       [● PAPER]      ⬤ Detenido             │
│                              [ ▶ Iniciar ]  [ ■ Detener ]    │
├────────────────────────────────────────────────────────────┤
│  Portafolio   Efectivo   P&L hoy   P&L total                │
├────────────────────────────────────────────────────────────┤
│  Equity curve (Chart.js)                                     │
├──────────────────────────────┬─────────────────────────────┤
│  Posiciones abiertas         │  Métricas                    │
├──────────────────────────────┴─────────────────────────────┤
│  Historial de trades (tabla)                                 │
└────────────────────────────────────────────────────────────┘
```

- Cabecera: estado, modo paper/live visible, botones. El de detener dispara el diálogo de
  cierre de posiciones.
- Tarjetas de cuenta arriba, equity curve debajo, posiciones + métricas lado a lado,
  historial abajo.

## Tests (según skill `testing-pytest`)

- `bot_manager`: arranque/parada, idempotencia, transiciones de estado, cierre de
  posiciones al detener (broker y bot mockeados, sin Alpaca real).
- Cambio en `bot.run()`: el loop para cuando se activa el `stop_event`.
- Cálculo de P&L al cierre y guardado de `daily_metrics`.
- Endpoints: `TestClient` de FastAPI con broker y repository mockeados.
- Frontend (HTML/JS): validación manual en el navegador, sin test automático.

## Dependencias nuevas

- `fastapi`, `uvicorn` (servidor). Chart.js se carga por CDN, no es dependencia de Python.

## Fuera de alcance (YAGNI)

- Autenticación / login.
- Exposición a internet o configuración de red (es de la fase VPS).
- Websockets / streaming en tiempo real.
- Frameworks de frontend con build (React/Vue/Vite).
- Edición de parámetros de riesgo o estrategia desde la web.
```

## Notas

- El bot sigue corriendo solo mientras el servidor web esté abierto (mismo límite que hoy;
  el 24/7 real es la fase VPS).
- Una sola instancia del bot a la vez (garantizado por el manager singleton).
