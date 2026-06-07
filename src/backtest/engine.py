"""Backtester event-driven — procesa velas una por una, en orden cronológico.

Cero look-ahead por diseño y simetría con el loop en vivo. Usa la misma
estrategia y el mismo RiskManager que producción.

TODO (Fase 1): implementar BacktestEngine. Ver skill `backtesting-engine`.
"""
