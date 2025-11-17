# Estructura del Proyecto - Sistema de Pronóstico de Energía

```
EnergyForecastAgent/
│
├── 📄 README.md                          # Documentación principal completa
├── 📄 QUICKSTART.md                      # Guía de inicio rápido (5 minutos)
├── 📄 INTEGRATION_GUIDE.md               # Guía de integración con tu notebook
├── 📄 docker-compose.yml                 # Orquestación de servicios Docker
├── 📄 .env.example                       # Template de variables de entorno
├── 📄 .gitignore                         # Archivos a ignorar en git
│
├── 📁 api/                               # 🧠 CEREBRO DEL AGENTE (FastAPI)
│   ├── 📄 main.py                        # Servidor FastAPI con modelo ML (sin escalado)
│   ├── 📄 Dockerfile                     # Imagen Docker de la API
│   └── 📄 requirements.txt               # Dependencias de Python
│
├── 📁 airflow/                           # 🤖 ORQUESTADOR DEL AGENTE
│   ├── 📄 Dockerfile                     # Imagen Docker de Airflow
│   └── 📄 requirements.txt               # Dependencias de Airflow
│
├── 📁 dags/                              # 📋 DAGs DE AIRFLOW
│   ├── 📄 forecast_dag.py                # ⭐ DAG PRINCIPAL (Ciclo Percepción-Acción)
│   └── 📁 utils/
│       ├── 📄 __init__.py
│       └── 📄 feature_engineering.py     # ⭐ LÓGICA CRÍTICA DE FEATURES
│
├── 📁 models/                            # 💾 ARTEFACTOS DEL MODELO ML
│   ├── 📄 best_energy_model.pkl          # ← COLOCAR TU MODELO AQUÍ
│   ├── 📄 features.pkl                   # ← COLOCAR LISTA DE FEATURES
│   └── 📄 model_metadata.pkl             # ← COLOCAR METADATOS
│
├── 📁 sql/                               # 🗄️ SCRIPTS DE BASE DE DATOS
│   └── 📄 init.sql                       # Inicialización de tablas PostgreSQL
│
├── 📁 config/                            # ⚙️ ARCHIVOS DE CONFIGURACIÓN
│   └── 📄 airflow.cfg                    # Configuración de Airflow
│
├── 📁 notebooks/                         # 📓 NOTEBOOKS DE ANÁLISIS
│   ├── 📄 analyze_feature_engineering.py # Script de validación
│   └── 📄 PipelineEnergy.ipynb          # ← TU NOTEBOOK ORIGINAL (referencia)
│
├── 📁 logs/                              # 📝 LOGS DE AIRFLOW (generados)
├── 📁 plugins/                           # 🔌 PLUGINS DE AIRFLOW (opcionales)
└── 📁 tests/                             # 🧪 TESTS (opcionales)

```

---

## 📊 Arquitectura de Servicios Docker

```
┌─────────────────────────────────────────────────────────────────┐
│                     DOCKER COMPOSE                               │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌──────────────┐      ┌──────────────────┐    ┌──────────────────┐
│ PostgreSQL   │      │   FastAPI        │    │   Airflow        │
│ :5432        │◄─────│   :8000          │◄───│   (Scheduler,    │
│              │      │                  │    │    Webserver,    │
│ • historical │      │ • Carga modelo   │    │    Worker)       │
│ • forecasts  │      │ • Endpoint       │    │   :8080          │
│ • metadata   │      │   /predict       │    │                  │
└──────────────┘      └──────────────────┘    └──────────────────┘
                               │                       │
                               └───────────────────────┘
                                         │
                                ┌────────▼────────┐
                                │   Redis :6379   │
                                │   (Message      │
                                │    Broker)      │
                                └─────────────────┘
```

---

## 🔄 Flujo de Ejecución del Agente

```
HORA 5:00 AM (Diariamente)
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ Airflow Scheduler: Dispara DAG "energy_forecast_daily"         │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ FASE 1: PERCEPCIÓN (Sensores) - Paralelo                       │
├─────────────────────────────────────────────────────────────────┤
│ Task 1a: perceive_db_state                                      │
│   └─ Query PostgreSQL → últimas 48h de datos de energía        │
│                                                                  │
│ Task 1b: perceive_weather_forecast                              │
│   └─ API OpenWeatherMap → pronóstico 24h                       │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ FASE 2: PROCESAMIENTO (Feature Engineering)                    │
├─────────────────────────────────────────────────────────────────┤
│ Task 2: feature_engineering                                     │
│   ├─ Crear timestamps futuros (24h)                            │
│   ├─ Features climáticas: PRECTOT, RH2M, T2M, ALLSKY           │
│   ├─ Features calendáricas: HOLIDAY, IsWeekend                 │
│   ├─ Features cíclicas: Hour_sin/cos, Month_sin/cos, etc.      │
│   ├─ Features derivadas: Temp_Range                            │
│   └─ Features de lag: lag1, lag24, rolling_mean, rolling_std   │
│                                                                  │
│   OUTPUT: DataFrame con 17 features × 24 horas                 │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ FASE 3: DECISIÓN (Cerebro ML)                                  │
├─────────────────────────────────────────────────────────────────┤
│ Task 3: predict                                                 │
│   └─ POST http://api:8000/predict                              │
│       ├─ Payload: 17 features × 24 registros                   │
│       ├─ API aplica scaler.transform()                         │
│       ├─ API ejecuta model.predict()                           │
│       └─ Retorna: [pred_hour1, pred_hour2, ..., pred_hour24]  │
│                                                                  │
│   OUTPUT: Lista de 24 predicciones (MW)                        │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ FASE 4: ACCIÓN (Actuadores)                                    │
├─────────────────────────────────────────────────────────────────┤
│ Task 4: act_store_forecast                                      │
│   └─ INSERT INTO energy_forecasts (PostgreSQL)                 │
│       ├─ 24 registros con timestamp + predicción               │
│       ├─ Upsert (actualiza si ya existe)                       │
│       └─ Metadatos: model_version, created_at                  │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ FASE 5: MONITOREO (Opcional)                                   │
├─────────────────────────────────────────────────────────────────┤
│ Task 5: monitor_quality                                         │
│   ├─ Verificar rangos esperados (3000-8000 MW)                │
│   ├─ Calcular estadísticas (mean, std, min, max)              │
│   ├─ Detectar anomalías                                        │
│   └─ Generar alertas (si es necesario)                        │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ ✅ DAG COMPLETADO                                               │
│ Pronóstico de 24 horas almacenado en la base de datos          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📂 Archivos Clave y Su Propósito

| Archivo | Propósito | Importancia |
|---------|-----------|-------------|
| `dags/forecast_dag.py` | Define el ciclo Percepción-Acción del agente | ⭐⭐⭐⭐⭐ |
| `dags/utils/feature_engineering.py` | Lógica crítica para generar las 17 features | ⭐⭐⭐⭐⭐ |
| `api/main.py` | Servidor que expone el modelo ML | ⭐⭐⭐⭐⭐ |
| `docker-compose.yml` | Orquesta todos los servicios | ⭐⭐⭐⭐⭐ |
| `sql/init.sql` | Crea tablas y datos iniciales | ⭐⭐⭐⭐ |
| `.env` | Configuración de credenciales y API keys | ⭐⭐⭐⭐ |
| `models/*.pkl` | Artefactos del modelo (tu modelo entrenado) | ⭐⭐⭐⭐⭐ |
| `README.md` | Documentación completa del sistema | ⭐⭐⭐ |
| `QUICKSTART.md` | Guía de inicio rápido | ⭐⭐⭐⭐ |
| `INTEGRATION_GUIDE.md` | Cómo integrar tu notebook | ⭐⭐⭐⭐ |

---

## 🎯 Personalización del Sistema

### Para Modificar el Feature Engineering
**Archivo**: `dags/utils/feature_engineering.py`
- Ajustar la clase `FeatureEngineer`
- Modificar métodos: `create_lag_features()`, `create_cyclical_features()`, etc.

### Para Cambiar el Schedule
**Archivo**: `dags/forecast_dag.py`
- Línea: `schedule_interval='0 5 * * *'`
- Cambiar a tu horario preferido (formato cron)

### Para Agregar Más Features
**Archivos**:
1. `dags/utils/feature_engineering.py` - Agregar lógica de cálculo
2. `api/main.py` - Actualizar `FeaturesInput` con la nueva feature
3. `models/features.pkl` - Re-exportar con la nueva lista

### Para Cambiar el Modelo
**Pasos**:
1. Entrenar nuevo modelo en notebook
2. Exportar: `best_energy_model.pkl`, `scaler.pkl`, `features.pkl`, `model_metadata.pkl`
3. Copiar a carpeta `models/`
4. Reiniciar: `docker-compose restart api`

---

## 🔍 Endpoints de la API

```
GET  /                    # Info del servicio
GET  /health              # Health check
GET  /model/info          # Información del modelo
POST /predict             # Predicción batch (24 horas)
POST /predict/single      # Predicción única
GET  /docs                # Documentación interactiva (Swagger)
```

---

## 📊 Tablas de la Base de Datos

```sql
historical_energy         -- Datos históricos de consumo
  ├─ timestamp (PK)
  ├─ energy_mw
  └─ metadatos climáticos

energy_forecasts          -- Pronósticos generados
  ├─ forecast_timestamp (PK)
  ├─ predicted_energy_mw
  ├─ model_version
  ├─ actual_energy_mw (llenado después)
  └─ error_mw (calculado después)

model_performance         -- Métricas de performance
  ├─ evaluation_date (PK)
  ├─ rmse, mae, mape, r2
  └─ drift_detected

agent_logs                -- Logs de ejecuciones del agente
  ├─ dag_run_id
  ├─ execution_date
  └─ status de cada fase
```

---

## 🚀 Comandos Más Usados

```bash
# Iniciar sistema
docker-compose up -d

# Ver logs
docker-compose logs -f [servicio]

# Reiniciar servicio
docker-compose restart [servicio]

# Detener sistema
docker-compose down

# Rebuild después de cambios
docker-compose up -d --build

# Ejecutar DAG manualmente
docker-compose exec airflow-scheduler airflow dags trigger energy_forecast_daily

# Consultar pronósticos
docker-compose exec db psql -U energy_user -d energy_forecast -c "SELECT * FROM energy_forecasts LIMIT 10;"
```

---

**Sistema diseñado como Agente Racional basado en Russell & Norvig**
