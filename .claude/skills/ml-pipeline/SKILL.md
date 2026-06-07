---
name: ml-pipeline
description: Convenciones del pipeline de Machine Learning del trading bot. Usar siempre que se trabaje en models/train.py, feature engineering para el modelo, creación de labels, entrenamiento, validación, o la estrategia ML en strategy/ml_strategy.py. Activar ante dudas sobre split temporal, data leakage, walk-forward validation, qué métricas usar para evaluar el modelo, o la cadencia de reentrenamiento.
---

# Pipeline de Machine Learning — Convenciones

## Contexto pedagógico (Géron)

Este pipeline sigue el flujo del **Capítulo 2 de Géron** (end-to-end ML project), adaptado para series temporales financieras. Las diferencias críticas respecto al pipeline estándar están marcadas con ⚠️.

| Concepto del libro | Cómo se aplica aquí |
|---|---|
| Cap. 1 — Batch learning, model rot | Justifica el reentrenamiento periódico |
| Cap. 2 — Pipeline end-to-end, baseline | Estructura de `models/train.py` |
| Cap. 3 — Clasificación, precision/recall | Evaluación del modelo (tarea binaria) |
| Cap. 6–7 — RandomForest, XGBoost | Los modelos a usar |

---

## Flujo completo del pipeline

```
1. Descargar datos históricos (Alpaca)
        ↓
2. Feature engineering (indicadores técnicos)
        ↓
3. Crear label (¿sube el precio mañana?)
        ↓
4. Split temporal (NO aleatorio) ⚠️
        ↓
5. Entrenar modelo (RF → XGBoost)
        ↓
6. Evaluar: métricas de clasificación + métricas financieras ⚠️
        ↓
7. Comparar contra baseline (buy-hold + reglas) ⚠️
        ↓
8. Guardar modelo si supera al baseline
        ↓
9. El bot carga el modelo en producción
```

---

## Feature engineering

### Features a calcular (sobre las velas OHLCV diarias)

```python
import ta

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Momentum
    df["rsi_14"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()

    # Tendencia
    # adjust=False: la EMA depende solo del valor previo, NO del largo del historial.
    # Garantiza que la EMA sea idéntica en backtest y en el bot en vivo (misma fórmula recursiva).
    df["ema_9"]  = df["close"].ewm(span=9, adjust=False).mean()
    df["ema_21"] = df["close"].ewm(span=21, adjust=False).mean()
    df["ema_cross"] = (df["ema_9"] > df["ema_21"]).astype(int)

    # Volatilidad
    bb = ta.volatility.BollingerBands(df["close"], window=20)
    df["bb_pct"]  = bb.bollinger_pband()   # posición relativa en las bandas
    df["atr_14"]  = ta.volatility.AverageTrueRange(
        df["high"], df["low"], df["close"], window=14
    ).average_true_range()

    # Retornos pasados
    df["ret_1d"]  = df["close"].pct_change(1)
    df["ret_5d"]  = df["close"].pct_change(5)
    df["ret_20d"] = df["close"].pct_change(20)

    # Volumen relativo
    df["vol_ratio"] = df["volume"] / df["volume"].rolling(20).mean()

    return df.dropna()
```

**Regla de oro:** todas las features usan solo datos **pasados o del mismo momento** (open, high, low, close, volume del día actual y días anteriores). Nunca datos futuros.

> **Fuente única de verdad:** `build_features()` vive en `src/features/indicators.py` (funciones puras, según la arquitectura). El pipeline ML, el backtester y el bot en vivo **importan la misma función** — nunca se redefine. Si el backtest y el modelo calculan features distintas, las señales divergen entre validación y producción.

---

## Creación del label ⚠️

El label responde: *¿sube el precio más de X% al día siguiente?* (clasificación binaria).

```python
THRESHOLD = 0.01  # 1% — ajustable en settings

def create_label(df: pd.DataFrame, threshold: float = THRESHOLD) -> pd.DataFrame:
    df = df.copy()
    # shift(-1): precio de cierre del DÍA SIGUIENTE
    future_close = df["close"].shift(-1)

    # ⚠️ Cuidado: `(NaN > x)` es False, y `False.astype(int)` = 0 — NO es NaN.
    # Si casteáramos a int directamente, la última fila (sin día siguiente) recibiría
    # un label fantasma 0 y `dropna` NO la eliminaría. Forzamos NaN antes de castear.
    label = (future_close > df["close"] * (1 + threshold)).where(future_close.notna())
    df["label"] = label

    # Ahora sí: la última fila tiene label NaN y se elimina correctamente.
    df = df.dropna(subset=["label"])
    df["label"] = df["label"].astype(int)
    return df
```

**El label usa `shift(-1)`.** Esto significa que se está prediciendo el futuro, lo cual es correcto. Lo que NO es correcto es usar datos del futuro como *features*. La diferencia: el label siempre mira al futuro (eso es la predicción); las features nunca deben hacerlo.

---

## Split temporal — ⚠️ NUNCA usar split aleatorio

`train_test_split` de scikit-learn con `shuffle=True` (default) **rompe la dependencia temporal** y produce data leakage. En series temporales siempre cortar cronológicamente.

```python
TRAIN_END   = "2022-12-31"
VAL_END     = "2023-12-31"
# TEST: todo lo posterior a VAL_END — se toca UNA SOLA VEZ al final

def temporal_split(df):
    train = df[df.index <= TRAIN_END]
    val   = df[(df.index > TRAIN_END) & (df.index <= VAL_END)]
    test  = df[df.index > VAL_END]     # NO tocar hasta evaluación final
    return train, val, test

FEATURE_COLS = ["rsi_14", "ema_cross", "bb_pct", "atr_14",
                "ret_1d", "ret_5d", "ret_20d", "vol_ratio"]

X_train, y_train = train[FEATURE_COLS], train["label"]
X_val,   y_val   = val[FEATURE_COLS],   val["label"]
X_test,  y_test  = test[FEATURE_COLS],  test["label"]
```

---

## Entrenamiento

### Paso 1: RandomForest (baseline ML)

```python
from sklearn.ensemble import RandomForestClassifier

modelo = RandomForestClassifier(
    n_estimators=200,
    max_depth=5,         # limitar profundidad reduce overfitting en mercados ruidosos
    min_samples_leaf=20, # requiere muestras suficientes en cada hoja
    class_weight="balanced",  # compensa desbalance de clases
    random_state=42
)
modelo.fit(X_train, y_train)
```

### Paso 2: XGBoost (sucesor si RF supera al baseline)

```python
from xgboost import XGBClassifier

modelo = XGBClassifier(
    n_estimators=200,
    max_depth=4,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    eval_metric="logloss",
    random_state=42
)
modelo.fit(
    X_train, y_train,
    eval_set=[(X_val, y_val)],
    verbose=False
)
```

---

## Evaluación — métricas DOBLES ⚠️

La **accuracy sola no basta** en trading. Evaluar siempre en dos dimensiones:

### 1. Métricas de clasificación (Géron Cap. 3)

```python
from sklearn.metrics import classification_report, confusion_matrix

preds_val = modelo.predict(X_val)
print(classification_report(y_val, preds_val))
print(confusion_matrix(y_val, preds_val))
```

Interpretar **precision y recall** por clase, no solo accuracy. Un modelo que siempre predice "sube" tiene accuracy alta en mercados alcistas pero no tiene valor.

### 2. Métricas financieras (la que realmente importa)

Simular la estrategia sobre el periodo de validación y calcular:
- Sharpe ratio
- Max drawdown
- Win rate
- Profit factor
- Comparativa contra buy-and-hold

```python
# El modelo se usa para generar señales y se corre sobre el backtester
# Ver skill: backtesting-engine
```

**Regla de promoción:** el modelo pasa a producción SOLO si en walk-forward:
1. Sharpe > 1.5
2. Vence al baseline buy-and-hold en al menos 3 de 4 ventanas de validación.

---

## Walk-forward validation ⚠️

K-fold estándar no aplica en series temporales porque mezcla futuro con pasado. Usar walk-forward:

# ⚠️ Pasar un FACTORY que construye el modelo con los MISMOS hiperparámetros
# que usarás en producción. Si usas `RandomForestClassifier()` con defaults aquí,
# validas un modelo distinto al que vas a promover (defaults => max_depth=None => overfit),
# y el Sharpe de walk-forward — el que decide el go-live — mide otra cosa.
def make_model():
    return RandomForestClassifier(
        n_estimators=200,
        max_depth=5,
        min_samples_leaf=20,
        class_weight="balanced",
        random_state=42,
    )

def walk_forward_validation(df, model_factory=make_model, n_splits=4):
    """
    Divide el dataset en n_splits ventanas temporales.
    En cada ventana: entrena en el pasado, valida en el futuro inmediato.
    model_factory: callable SIN argumentos que devuelve un modelo ya configurado.
    """
    results = []
    window_size = len(df) // (n_splits + 1)

    for i in range(n_splits):
        train_end = window_size * (i + 1)
        val_end   = window_size * (i + 2)

        train = df.iloc[:train_end]
        val   = df.iloc[train_end:val_end]

        modelo = model_factory()   # mismos hiperparámetros que en producción
        modelo.fit(train[FEATURE_COLS], train["label"])
        preds = modelo.predict(val[FEATURE_COLS])

        # Sharpe de esta ventana: las preds alimentan el backtester event-driven
        # (ver skill `backtesting-engine`) que devuelve la equity curve, y de ahí el Sharpe.
        sharpe = calcular_sharpe_estrategia(val, preds)
        results.append(sharpe)

    return results  # lista de Sharpes por ventana
```

Si el Sharpe promedio de walk-forward es < 1.5, el modelo no se promueve.

---

## Feature importance

```python
import pandas as pd
import matplotlib.pyplot as plt

importances = pd.Series(
    modelo.feature_importances_,
    index=FEATURE_COLS
).sort_values(ascending=False)

importances.plot(kind="bar")
plt.title("Feature Importance")
plt.tight_layout()
plt.savefig("models/feature_importance.png")
```

Revisar que las features más importantes tengan sentido económico. Si una feature con peso alto es sospechosa (ej.: `vol_ratio` domina abrumadoramente), investigar posible leakage.

---

## Guardar y versionar el modelo

```python
import joblib
from datetime import datetime

VERSION = datetime.now().strftime("%Y%m%d")
path = f"models/saved/model_v{VERSION}.pkl"

joblib.dump(modelo, path)
print(f"Modelo guardado en {path}")
```

**Guardar también los metadatos del modelo:**

```python
import json

metadata = {
    "version": VERSION,
    "symbol": "BTC/USD",
    "train_period": f"{TRAIN_END}",
    "features": FEATURE_COLS,
    "threshold": THRESHOLD,
    "val_sharpe": round(val_sharpe, 3),
    "val_drawdown": round(val_drawdown, 3),
}

with open(f"models/saved/metadata_v{VERSION}.json", "w") as f:
    json.dump(metadata, f, indent=2)
```

---

## Uso del modelo en producción

```python
# strategy/ml_strategy.py
import joblib
import pandas as pd

class MLStrategy:
    def __init__(self, model_path: str):
        self.model = joblib.load(model_path)

    def generate_signal(self, df: pd.DataFrame) -> str:
        features = build_features(df).tail(1)[FEATURE_COLS]
        prediction = self.model.predict(features)[0]

        if prediction == 1:
            return "BUY"
        return "HOLD"   # sin señal de SELL explícita — el stop-loss lo maneja risk/
```

El modelo nunca ejecuta órdenes directamente. Solo devuelve `"BUY"` o `"HOLD"`. La ejecución siempre pasa por `risk/` y `execution/`.

---

## Cadencia de reentrenamiento

El mercado evoluciona — el modelo se deteriora con el tiempo (**model rot**, Géron Cap. 1).

**Cadencia recomendada:** reentrenar mensualmente con los últimos 3–5 años de datos.

Flujo de reentrenamiento:
1. Descargar datos actualizados.
2. Correr `models/train.py`.
3. Comparar nuevo modelo vs modelo actual en los últimos 3 meses.
4. Si el nuevo supera al actual → reemplazar `models/saved/model_latest.pkl`.
5. Commitear el nuevo modelo y sus metadatos.
6. Reiniciar el bot para que cargue el nuevo modelo.

---

## Test anti-leakage (obligatorio)

Incluir en `tests/test_ml_pipeline.py`:

```python
def test_no_data_leakage(sample_ohlcv):
    """
    Verifica que el label de hoy no usa el precio de cierre de hoy.
    El label debe depender solo de datos del DÍA SIGUIENTE.

    Usa el fixture compartido `sample_ohlcv` (definido en conftest.py — ver skill
    `testing-pytest`). El test exacto fila-a-fila vive en `test_label_uses_future_price`;
    este es el chequeo estadístico complementario.
    """
    df_features = build_features(sample_ohlcv)
    df_labeled  = create_label(df_features)

    # El label[i] debe correlacionar con close[i+1], no con close[i]
    corr_futuro  = df_labeled["label"].corr(df_labeled["close"].shift(-1))
    corr_presente = df_labeled["label"].corr(df_labeled["close"])

    assert abs(corr_futuro)   > 0.3, "El label no tiene relación con el precio futuro"
    assert abs(corr_presente) < abs(corr_futuro), "Posible leakage: label correlaciona con precio presente"
```
