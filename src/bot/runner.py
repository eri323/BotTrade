"""Loop principal en vivo (orquestador).

Flujo: obtener datos → calcular features → señal → pasar por risk → ejecutar →
registrar. Manejo robusto de errores (reconexión, rate limits, timeouts).

TODO (Fase 2): implementar el loop. Ver skills `trading-bot-conventions` y
`alpaca-integration`.
"""
