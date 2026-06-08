# Comandos para correr el bot (sin ayuda)

> Ejecuta todo desde la raíz del proyecto:
> `C:\Users\USUARIO\Documents\Personal\Projects\Bot`

## 0. Requisito: tener el `.env` con tus keys

El archivo `.env` (en la raíz) debe tener tus keys paper de Alpaca:
```
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
PAPER=true
```

---

## La forma fácil y universal: activar el entorno primero

Activa el venv **según tu terminal** (solo una vez por ventana):

| Terminal | Comando para activar |
|---|---|
| **PowerShell** | `.\venv\Scripts\Activate.ps1` |
| **CMD** (símbolo del sistema) | `venv\Scripts\activate.bat` |
| **Bash / Git Bash** (la de Antigravity suele ser esta) | `source venv/Scripts/activate` |

Sabrás que está activado porque aparece `(venv)` al inicio de la línea.

**Después de activar, los comandos son IGUALES en cualquier terminal:**

```bash
python scripts/check_connection.py                              # verificar conexión
python scripts/run_backtest.py --symbol BTC/USD --start 2021-01-01   # backtest
python scripts/run_bot.py --paper --once                        # un ciclo de prueba
python scripts/run_bot.py --paper --interval 86400              # dejar operando (1x/día)
```

Para **detener** el bot: `Ctrl + C`.

---

## Sin activar el entorno (ruta directa al python del venv)

Si prefieres no activar, llama al python del venv directamente. **La barra cambia según la terminal:**

- **PowerShell / CMD** (barra invertida `\`):
  ```
  venv\Scripts\python.exe scripts\run_bot.py --paper --interval 86400
  ```
- **Bash / Git Bash** (barra normal `/`):
  ```
  venv/Scripts/python.exe scripts/run_bot.py --paper --interval 86400
  ```

> En PowerShell a veces hay que anteponer `.\` → `.\venv\Scripts\python.exe ...`

---

## Atajos de doble clic (no necesitas terminal)

- **`iniciar_bot.bat`** → doble clic en el Explorador de Windows. Arranca el bot en paper.
- **`iniciar_bot.sh`** → para terminales bash: `./iniciar_bot.sh`

---

## Notas

- El bot corre **solo mientras la terminal/ventana esté abierta**. Si la cierras o apagas el PC, se detiene. (Para 24/7 real → Fase 4: VPS.)
- Corre **una sola instancia** a la vez.
- Registra trades en `trading_bot.db` y todo en `logs/`.

## Mantenimiento (opcional, con el venv activado)

```bash
python -m pytest -q          # tests
ruff format . && ruff check . # formato + lint
```
