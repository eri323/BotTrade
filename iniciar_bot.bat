@echo off
REM Arranca el bot de trading en modo paper (velas diarias).
REM Doble clic para ejecutar. Ctrl+C para detener.

cd /d "%~dp0"

echo ================================================
echo   BOT DE TRADING - MODO PAPER
echo   Ctrl+C para detener. Cerrar la ventana lo para.
echo ================================================
echo.

venv\Scripts\python.exe scripts\run_bot.py --paper --interval 86400

echo.
echo El bot se detuvo.
pause
