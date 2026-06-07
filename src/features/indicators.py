"""Indicadores técnicos — funciones PURAS (sin estado, sin I/O, sin broker).

Fuente única de verdad de `build_features()`: el pipeline ML, el backtester y el
bot en vivo importan de aquí. Toda feature usa solo datos pasados o del momento
actual; nunca datos futuros (cero look-ahead).

TODO (Fase 1): implementar rsi(), ema(), bollinger(), atr(), pct_return() y
build_features(). Ver skill `ml-pipeline` (sección feature engineering).
"""
