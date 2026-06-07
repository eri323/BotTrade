"""Estrategia basada en un modelo entrenado (.pkl).

Carga el modelo con joblib y devuelve señales con `model.predict()`. El modelo
nunca ejecuta órdenes: solo devuelve "BUY" | "HOLD".

TODO (Fase 3): implementar MLStrategy. Ver skill `ml-pipeline`.
"""
