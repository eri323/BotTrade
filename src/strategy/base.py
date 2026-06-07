"""Interfaz `Strategy` — contrato común de toda estrategia.

Una estrategia recibe el historial disponible y devuelve "BUY" | "SELL" | "HOLD".
Es agnóstica al broker: nunca importa Alpaca. La ejecución siempre pasa por
`risk/` y `execution/`.

TODO (Fase 1): definir la clase base `Strategy` con `generate_signal(df) -> str`.
"""
