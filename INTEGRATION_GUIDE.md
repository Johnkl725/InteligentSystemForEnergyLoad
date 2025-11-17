"""
GUÍA DE INTEGRACIÓN CON TU NOTEBOOK EXISTENTE

Este documento explica cómo integrar la lógica de feature engineering
de tu PipelineEnergy.ipynb con el sistema del agente.

==============================================================================
PASO 1: ANÁLISIS DE TU NOTEBOOK
==============================================================================

Abre tu PipelineEnergy.ipynb y busca estas secciones:

1. CARGA DE DATOS:
   - ¿De dónde vienen los datos históricos? (CSV, DB, API)
   - ¿Qué columnas tienen? (timestamp, ENERGY, T2M, etc.)

2. FEATURE ENGINEERING:
   - ¿Cómo se calculan las features cíclicas?
   - ¿Cómo se calculan los lags?
   - ¿Hay transformaciones especiales?

3. ESCALADO:
   - ¿Qué tipo de scaler usas? (StandardScaler, MinMaxScaler, etc.)
   - ¿Qué columnas se escalan?

4. MODELO:
   - ¿Qué hiperparámetros tiene tu XGBRegressor?
   - ¿Cuál es la métrica de performance?

==============================================================================
PASO 2: EXTRACCIÓN DE LA LÓGICA DE FEATURES
==============================================================================

El módulo `dags/utils/feature_engineering.py` YA IMPLEMENTA la lógica
estándar para las 17 features. 

Si tu notebook tiene lógica DIFERENTE, necesitas ajustar estas funciones:

1. create_cyclical_features():
   - Si usas una fórmula diferente para sin/cos
   - Si normalizas de manera diferente

2. create_lag_features():
   - Si usas lags diferentes (ej. lag6, lag12)
   - Si usas ventanas diferentes (ej. rolling 48h)

3. create_calendar_features():
   - Si tienes días festivos específicos de tu país
   - Si consideras más holidays

EJEMPLO DE PERSONALIZACIÓN:
```python
# En tu notebook
df['custom_feature'] = df['T2M'] * df['RH2M'] / 100

# Agregar a feature_engineering.py
def create_weather_derived_features(self, df):
    df = df.copy()
    # ... código existente ...
    
    # TU FEATURE CUSTOM
    df['custom_feature'] = df['T2M'] * df['RH2M'] / 100
    
    return df
```

==============================================================================
PASO 3: EXPORTAR EL SCALER
==============================================================================

Si aún no tienes scaler.pkl, créalo en tu notebook:

```python
import pickle
from sklearn.preprocessing import StandardScaler

# Supongamos que 'X_train' son tus features de entrenamiento
scaler = StandardScaler()
scaler.fit(X_train)

# Guardar el scaler
with open('scaler.pkl', 'wb') as f:
    pickle.dump(scaler, f)

print("✓ Scaler guardado")
```

==============================================================================
PASO 4: EXPORTAR METADATA
==============================================================================

Crear el archivo model_metadata.pkl:

```python
import pickle

metadata = {
    'version': '1.0',
    'model_type': 'XGBRegressor',
    'needs_scaling': True,  # ← MUY IMPORTANTE
    'features': [
        'PRECTOT', 'RH2M', 'T2M', 'ALLSKY_SFC_SW_DWN',
        'HOLIDAY', 'IsWeekend',
        'Hour_sin', 'Hour_cos', 'Month_sin', 'Month_cos',
        'DayOfWeek_sin', 'DayOfWeek_cos',
        'Temp_Range',
        'ENERGY_lag1', 'ENERGY_lag24',
        'ENERGY_rolling_mean_24', 'ENERGY_rolling_std_24'
    ],
    'trained_on': '2024-01-01',
    'train_samples': 10000,
    'performance': {
        'rmse': 250.5,
        'mae': 180.3,
        'r2': 0.95
    }
}

with open('model_metadata.pkl', 'wb') as f:
    pickle.dump(metadata, f)

print("✓ Metadata guardado")
```

==============================================================================
PASO 4: EXPORTAR LISTA DE FEATURES
==============================================================================

```python
import pickle

# Lista ordenada de features (DEBE COINCIDIR con el orden del entrenamiento)
features = [
    'PRECTOT', 'RH2M', 'T2M', 'ALLSKY_SFC_SW_DWN',
    'HOLIDAY', 'IsWeekend',
    'Hour_sin', 'Hour_cos', 'Month_sin', 'Month_cos',
    'DayOfWeek_sin', 'DayOfWeek_cos',
    'Temp_Range',
    'ENERGY_lag1', 'ENERGY_lag24',
    'ENERGY_rolling_mean_24', 'ENERGY_rolling_std_24'
]

with open('features.pkl', 'wb') as f:
    pickle.dump(features, f)

print("✓ Features guardado")
```

==============================================================================
PASO 5: VALIDACIÓN ANTES DEL DEPLOYMENT
==============================================================================

Antes de hacer docker-compose up, ejecuta este test:

```python
import pandas as pd
import numpy as np
import pickle
from datetime import datetime, timedelta

# 1. Cargar modelo
with open('best_energy_model.pkl', 'rb') as f:
    model = pickle.load(f)

with open('features.pkl', 'rb') as f:
    features = pickle.load(f)

print(f"✓ Modelo cargado: {type(model)}")
print(f"✓ Features: {len(features)}")

# 2. Crear datos de prueba (simular feature engineering)
test_data = pd.DataFrame({
    'PRECTOT': [0.5],
    'RH2M': [65.0],
    'T2M': [22.5],
    'ALLSKY_SFC_SW_DWN': [450.0],
    'HOLIDAY': [0],
    'IsWeekend': [0],
    'Hour_sin': [0.866],
    'Hour_cos': [0.5],
    'Month_sin': [0.0],
    'Month_cos': [1.0],
    'DayOfWeek_sin': [0.433],
    'DayOfWeek_cos': [0.9],
    'Temp_Range': [10.5],
    'ENERGY_lag1': [5500.0],
    'ENERGY_lag24': [5300.0],
    'ENERGY_rolling_mean_24': [5400.0],
    'ENERGY_rolling_std_24': [200.0]
})

# Asegurar el orden correcto
test_data = test_data[features]

print(f"✓ Test data creado: {test_data.shape}")

# 3. Predecir (sin escalado)
prediction = model.predict(test_data)
print(f"✓ Predicción: {prediction[0]:.2f} MW")

# 4. Validar predicción
if 3000 <= prediction[0] <= 8000:
    print("✅ PREDICCIÓN EN RANGO ESPERADO")
else:
    print("⚠️ PREDICCIÓN FUERA DE RANGO - REVISAR")
```

==============================================================================
PASO 6: TROUBLESHOOTING COMÚN
==============================================================================

PROBLEMA 1: "ValueError: X has 17 features, but model was trained with 18"
SOLUCIÓN: 
  - Verificar que features.pkl tenga EXACTAMENTE las features del modelo
  - Usar: print(model.get_booster().feature_names)

PROBLEMA 2: "El modelo predice valores muy diferentes"
SOLUCIÓN:
  - Verificar que las features se calculen igual que en el notebook
  - Verificar que el orden de las columnas sea correcto
  - Revisar los rangos de valores de entrada

PROBLEMA 3: "Features con valores None o NaN"
SOLUCIÓN:
  - Revisar que haya suficientes datos históricos (48h mínimo)
  - Implementar estrategia de imputación en feature_engineering.py

PROBLEMA 4: "Predicciones siempre iguales"
SOLUCIÓN:
  - Verificar que las features de lag estén calculándose correctamente
  - Verificar que los datos climáticos estén variando

==============================================================================
PASO 7: CHECKLIST FINAL
==============================================================================

Antes de deployar, verificar:

[ ] best_energy_model.pkl existe y es tu modelo entrenado
[ ] features.pkl contiene la lista correcta de features en el orden correcto
[ ] model_metadata.pkl NO contiene needs_scaling (o está en False)
[ ] El test de validación (Paso 5) funciona correctamente
[ ] Las predicciones están en el rango esperado (ej. 3000-8000 MW)
[ ] feature_engineering.py está ajustado si hay lógica custom
[ ] Los días festivos en FeatureEngineer.HOLIDAYS son correctos para tu país

==============================================================================
PASO 8: EJECUTAR EL SCRIPT DE ANÁLISIS
==============================================================================

```bash
cd notebooks/
python analyze_feature_engineering.py
```

Este script te ayudará a:
- Validar que el feature engineering funcione
- Comparar con las features esperadas por el modelo
- Detectar inconsistencias

==============================================================================
CONTACTO Y AYUDA
==============================================================================

Si tienes problemas con la integración:

1. Revisa los logs: docker-compose logs api
2. Ejecuta el test de validación (Paso 6)
3. Verifica que tu notebook y feature_engineering.py hagan lo mismo
4. Compara las features generadas manualmente vs. automáticamente

==============================================================================
"""

# Función auxiliar para comparar notebooks
def compare_notebook_with_module():
    """
    Función para comparar la lógica del notebook con el módulo.
    """
    print(__doc__)

if __name__ == "__main__":
    compare_notebook_with_module()
