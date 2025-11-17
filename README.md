# 🤖 Sistema Inteligente Autónomo de Pronóstico de Demanda Energética

## 📋 Resumen Ejecutivo

**Agente Racional basado en el paradigma de Russell & Norvig** para pronóstico automático de demanda eléctrica utilizando Machine Learning (XGBoost) y orquestación con Apache Airflow.

### Características Principales

- ✅ **Arquitectura de Agente Racional**: Implementa el ciclo completo Percepción → Procesamiento → Decisión → Acción
- ✅ **Modelo ML Pre-entrenado**: XGBRegressor con 17 features de entrada (sin escalado requerido)
- ✅ **Orquestación Automática**: Ejecución diaria a las 5:00 AM con Airflow
- ✅ **Contenedorización Completa**: Docker Compose con todos los servicios
- ✅ **Feature Engineering Avanzado**: Lags, ventanas móviles, features cíclicas
- ✅ **API RESTful**: FastAPI para servir el modelo
- ✅ **Base de Datos Persistente**: PostgreSQL para datos históricos y pronósticos

---

## 🏗️ Arquitectura del Sistema

### Paradigma de Agente Racional

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AGENTE RACIONAL                               │
│                                                                       │
│  Objetivo: Minimizar error de pronóstico (RMSE/MAE)                 │
│  Entorno: Base de datos + API del clima + Calendario                │
└─────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌──────────────────┐       ┌──────────────────┐
│   SENSORES    │         │  CEREBRO (ML)    │       │   ACTUADORES     │
│  (Percepción) │         │   (Decisión)     │       │    (Acción)      │
├───────────────┤         ├──────────────────┤       ├──────────────────┤
│ • DB Query    │────────▶│ • FastAPI        │──────▶│ • DB Write       │
│ • Weather API │         │ • XGBRegressor   │       │ • Alertas        │
│ • Monitor     │         │ • 17 Features    │       │ • Dashboard      │
└───────────────┘         └──────────────────┘       └──────────────────┘
        │                           │                           │
        └───────────────────────────┴───────────────────────────┘
                                    │
                          ┌─────────▼──────────┐
                          │   ORQUESTADOR      │
                          │   Apache Airflow   │
                          │   (DAG Diario)     │
                          └────────────────────┘
```

### Componentes del Sistema

| Componente | Tecnología | Puerto | Rol en el Agente |
|------------|-----------|--------|------------------|
| **PostgreSQL** | postgres:15-alpine | 5432 | Entorno (Estado) |
| **FastAPI** | Python 3.10 + FastAPI | 8000 | Cerebro (Modelo ML) |
| **Airflow Webserver** | Apache Airflow 2.8.0 | 8080 | Orquestador |
| **Airflow Scheduler** | Apache Airflow 2.8.0 | - | Orquestador |
| **Airflow Worker** | Apache Airflow 2.8.0 | - | Ejecutor de Tareas |
| **Redis** | redis:7-alpine | 6379 | Cola de Tareas |
| **Flower** | Celery Flower | 5555 | Monitor de Tareas |

---

## 🧠 El Modelo: XGBRegressor

### Features de Entrada (17 en total)

#### 1. Features Climáticas (4)
- `PRECTOT`: Precipitación total (mm)
- `RH2M`: Humedad relativa al 2m (%)
- `T2M`: Temperatura al 2m (°C)
- `ALLSKY_SFC_SW_DWN`: Radiación solar (W/m²)

#### 2. Features Calendáricas (2)
- `HOLIDAY`: Indicador de día festivo (0/1)
- `IsWeekend`: Indicador de fin de semana (0/1)

#### 3. Features Cíclicas (6)
- `Hour_sin`, `Hour_cos`: Codificación cíclica de hora (0-23)
- `Month_sin`, `Month_cos`: Codificación cíclica de mes (1-12)
- `DayOfWeek_sin`, `DayOfWeek_cos`: Codificación cíclica de día de la semana (0-6)

#### 4. Features Derivadas (1)
- `Temp_Range`: Rango de temperatura del día (T_max - T_min)

#### 5. Features de Lag y Ventana (4)
- `ENERGY_lag1`: Energía del período anterior (1 hora)
- `ENERGY_lag24`: Energía de hace 24 horas (mismo hora del día anterior)
- `ENERGY_rolling_mean_24`: Media móvil de 24 horas
- `ENERGY_rolling_std_24`: Desviación estándar móvil de 24 horas

### Pipeline de Inferencia

```python
Datos Crudos → Feature Engineering → XGBRegressor → Pronóstico (MW)
```

**Nota Crítica**: El modelo **NO es un pipeline**. Espera recibir exactamente las 17 features ya procesadas (sin escalado requerido).

---

## 🔄 Flujo del Ciclo Percepción-Acción

### DAG de Airflow: `energy_forecast_daily`

**Schedule**: `0 5 * * *` (Todos los días a las 5:00 AM)

```
┌─────────────────────────────────────────────────────────────────┐
│                    CICLO DEL AGENTE                              │
└─────────────────────────────────────────────────────────────────┘

1. PERCEPCIÓN (Paralelo)
   ├─ task_perceive_db_state
   │  └─ Consulta PostgreSQL: últimas 48h de carga energética
   │
   └─ task_perceive_weather
      └─ Consulta OpenWeatherMap: pronóstico de 24h

2. PROCESAMIENTO INTERNO
   └─ task_feature_engineering
      ├─ Crear timestamps futuros (24h)
      ├─ Generar features calendáricas (HOLIDAY, IsWeekend)
      ├─ Generar features cíclicas (sin/cos de hora, mes, día)
      ├─ Calcular features derivadas (Temp_Range)
      └─ Calcular features de lag (lag1, lag24, rolling_mean, rolling_std)

3. DECISIÓN (Llamada al Cerebro)
   └─ task_predict
      ├─ POST http://api:8000/predict
      ├─ Payload: 17 features × 24 horas (sin escalado)
      └─ Response: 24 predicciones de carga (MW)

4. ACCIÓN
   └─ task_act_store_forecast
      └─ INSERT INTO energy_forecasts (PostgreSQL)

5. MONITOREO (Opcional)
   └─ task_monitor_quality
      ├─ Verificar rangos esperados
      ├─ Detectar anomalías
      └─ Generar alertas si es necesario
```

---

## 🚀 Instalación y Deployment

### Prerrequisitos

- Docker >= 20.10
- Docker Compose >= 2.0
- 8 GB RAM mínimo
- 20 GB espacio en disco

### Paso 1: Clonar y Configurar

```bash
# Clonar el repositorio
git clone <repository-url>
cd EnergyForecastAgent

# Copiar el archivo de configuración
cp .env.example .env

# Editar .env con tus credenciales
# IMPORTANTE: Cambiar WEATHER_API_KEY con tu API key de OpenWeatherMap
notepad .env  # Windows
nano .env     # Linux/Mac
```

### Paso 2: Colocar los Artefactos del Modelo

Coloca los siguientes archivos en la carpeta `models/`:

```
models/
├── best_energy_model.pkl      # Modelo XGBRegressor entrenado
├── features.pkl                # Lista de nombres de features
└── model_metadata.pkl          # Metadatos (version, performance, etc.)
```

### Paso 3: Construir e Iniciar los Servicios

```bash
# Construir las imágenes
docker-compose build

# Iniciar todos los servicios
docker-compose up -d

# Verificar que todos los contenedores estén corriendo
docker-compose ps
```

### Paso 4: Verificar el Deployment

```bash
# 1. Verificar la Base de Datos
docker-compose exec db psql -U energy_user -d energy_forecast -c "SELECT COUNT(*) FROM historical_energy;"

# 2. Verificar la API
curl http://localhost:8000/health

# 3. Acceder a Airflow
# Navegar a: http://localhost:8080
# Usuario: admin
# Contraseña: admin

# 4. Activar el DAG
# En la UI de Airflow, buscar "energy_forecast_daily" y activarlo (toggle ON)
```

---

## 🧪 Testing

### Probar la API de Predicción

```bash
# Test del endpoint /predict
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "features": [
      {
        "PRECTOT": 0.5,
        "RH2M": 65.0,
        "T2M": 22.5,
        "ALLSKY_SFC_SW_DWN": 450.0,
        "HOLIDAY": 0,
        "IsWeekend": 0,
        "Hour_sin": 0.866,
        "Hour_cos": 0.5,
        "Month_sin": 0.0,
        "Month_cos": 1.0,
        "DayOfWeek_sin": 0.433,
        "DayOfWeek_cos": 0.9,
        "Temp_Range": 10.5,
        "ENERGY_lag1": 5500.0,
        "ENERGY_lag24": 5300.0,
        "ENERGY_rolling_mean_24": 5400.0,
        "ENERGY_rolling_std_24": 200.0
      }
    ]
  }'
```

### Ejecutar el DAG Manualmente

1. Ir a http://localhost:8080
2. Encontrar el DAG `energy_forecast_daily`
3. Click en el botón "▶️ Trigger DAG"
4. Monitorear la ejecución en "Graph" o "Grid"

---

## 📊 Monitoreo y Logs

### Ver Logs de Airflow

```bash
# Logs del scheduler
docker-compose logs -f airflow-scheduler

# Logs del worker
docker-compose logs -f airflow-worker

# Logs de una tarea específica (desde Airflow UI)
# Airflow UI → DAGs → energy_forecast_daily → Graph → Click en tarea → Logs
```

### Ver Logs de la API

```bash
docker-compose logs -f api
```

### Consultar Pronósticos Generados

```bash
docker-compose exec db psql -U energy_user -d energy_forecast -c "
SELECT 
    forecast_timestamp, 
    predicted_energy_mw, 
    model_version,
    created_at
FROM energy_forecasts
ORDER BY forecast_timestamp DESC
LIMIT 10;
"
```

---

## 🔧 Mantenimiento

### Actualizar el Modelo

```bash
# 1. Detener la API
docker-compose stop api

# 2. Reemplazar los archivos en models/
cp /path/to/new_model.pkl models/best_energy_model.pkl
cp /path/to/new_scaler.pkl models/scaler.pkl

# 3. Reiniciar la API
docker-compose start api

# 4. Verificar la nueva versión
curl http://localhost:8000/model/info
```

### Limpiar Pronósticos Antiguos

```sql
-- Eliminar pronósticos de más de 30 días
DELETE FROM energy_forecasts 
WHERE forecast_timestamp < NOW() - INTERVAL '30 days';

-- Vacuum para liberar espacio
VACUUM FULL energy_forecasts;
```

### Re-entrenar el Modelo

El re-entrenamiento del modelo debe hacerse en un notebook/script separado:

1. Extraer datos de `historical_energy`
2. Entrenar nuevo modelo
3. Evaluar performance
4. Actualizar archivos .pkl
5. Deployar según "Actualizar el Modelo"

---

## 🔒 Seguridad

### Consideraciones de Producción

1. **Cambiar credenciales por defecto**:
   - Passwords de PostgreSQL
   - Fernet key de Airflow
   - Usuario/password de Airflow UI

2. **Usar secrets management**:
   - Docker Secrets
   - HashiCorp Vault
   - AWS Secrets Manager

3. **Configurar HTTPS**:
   - Nginx reverse proxy
   - Certificados SSL/TLS

4. **Limitar acceso a puertos**:
   - Exponer solo puertos necesarios
   - Firewall rules

---

## 📈 Escalabilidad

### Escalar Workers de Airflow

```bash
docker-compose up -d --scale airflow-worker=3
```

### Optimizar PostgreSQL

```sql
-- Ajustar parámetros de performance
ALTER SYSTEM SET shared_buffers = '2GB';
ALTER SYSTEM SET effective_cache_size = '6GB';
ALTER SYSTEM SET maintenance_work_mem = '512MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
```

---

## 🐛 Troubleshooting

### Problema: El DAG no ejecuta

**Solución**:
```bash
# Verificar que el scheduler esté corriendo
docker-compose ps airflow-scheduler

# Verificar logs del scheduler
docker-compose logs airflow-scheduler | tail -50

# Re-parsear DAGs
docker-compose exec airflow-scheduler airflow dags reserialize
```

### Problema: La API no responde

**Solución**:
```bash
# Verificar logs de la API
docker-compose logs api | tail -50

# Verificar que los modelos estén cargados
docker-compose exec api ls -lh /app/models/

# Reiniciar la API
docker-compose restart api
```

### Problema: No hay datos históricos

**Solución**:
```bash
# Verificar la tabla
docker-compose exec db psql -U energy_user -d energy_forecast -c "SELECT COUNT(*) FROM historical_energy;"

# Re-ejecutar el script de inicialización
docker-compose exec db psql -U energy_user -d energy_forecast -f /docker-entrypoint-initdb.d/init.sql
```

### Problema: Referencias a scaler.pkl

**Solución**: El modelo NO requiere escalado. Asegúrate de que `model_metadata.pkl` NO incluya `needs_scaling: True`.

---

## 📚 Referencias

- **Russell & Norvig**: *Artificial Intelligence: A Modern Approach* (Capítulo 2: Intelligent Agents)
- **XGBoost Documentation**: https://xgboost.readthedocs.io/
- **Apache Airflow**: https://airflow.apache.org/docs/
- **FastAPI**: https://fastapi.tiangolo.com/
- **OpenWeatherMap API**: https://openweathermap.org/api

---

## 📝 Licencia

Este proyecto es de código abierto y está disponible bajo la licencia MIT.

---

## 👨‍💻 Autor

Diseñado como un **Sistema Inteligente Autónomo** basado en el paradigma de **Agente Racional** de Russell & Norvig.

**Contacto**: [Tu email]

---

## 🎯 Roadmap Futuro

- [ ] Implementar modelo ensemble (XGBoost + LSTM)
- [ ] Agregar confidence intervals a las predicciones
- [ ] Dashboard de visualización con Grafana
- [ ] Detección automática de drift del modelo
- [ ] Re-entrenamiento automático basado en performance
- [ ] Integración con sistemas SCADA reales
- [ ] Multi-model serving (A/B testing)
- [ ] Explicabilidad del modelo (SHAP values)
