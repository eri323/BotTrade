#!/usr/bin/env bash
# Arranca el bot de trading en modo paper (velas diarias).
# Uso en una terminal bash (Git Bash, Antigravity, etc.):  ./iniciar_bot.sh
# Detener: Ctrl+C

cd "$(dirname "$0")" || exit 1

echo "================================================"
echo "  BOT DE TRADING - MODO PAPER"
echo "  Ctrl+C para detener."
echo "================================================"

venv/Scripts/python.exe scripts/run_bot.py --paper --interval 86400
