"""Interfaz `Strategy` — contrato común de toda estrategia.

`generate_signal(df)` recibe un DataFrame que YA contiene las columnas de
features (las produce `features.indicators.build_features`) y decide a partir de
la última fila. Devuelve "BUY" | "SELL" | "HOLD".

La estrategia es agnóstica al broker: nunca importa Alpaca. La ejecución siempre
pasa por `risk/` y `execution/`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

BUY = "BUY"
SELL = "SELL"
HOLD = "HOLD"


class Strategy(ABC):
    """Contrato de una estrategia de trading."""

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame) -> str:
        """Devuelve "BUY", "SELL" o "HOLD" a partir del historial con features."""
        raise NotImplementedError
