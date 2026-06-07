"""Pipeline de entrenamiento ML (estilo Géron Cap. 2).

Flujo: descargar histórico → feature engineering → crear label (shift(-1)) →
split temporal → entrenar (RF → XGBoost) → evaluar (clasificación + financieras)
→ walk-forward → comparar contra baseline → guardar .pkl + metadatos.

TODO (Fase 3): implementar el pipeline. Ver skill `ml-pipeline`.
"""
