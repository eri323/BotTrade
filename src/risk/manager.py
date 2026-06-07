"""Gestión de riesgo — capa OBLIGATORIA. Ninguna orden se ejecuta sin pasar por aquí.

Pura y agnóstica al broker: recibe datos, devuelve decisiones. Implementa
position sizing, stop-loss, take-profit, límite de pérdida diaria, circuit
breaker y tope de posiciones concurrentes (§7 del plan).

TODO (Fase 2): implementar RiskManager con cobertura de tests EXHAUSTIVA.
Ver skills `trading-bot-conventions` y `testing-pytest`.
"""
