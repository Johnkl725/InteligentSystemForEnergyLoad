# 🚀 GUÍA DE INICIO DEL PROYECTO

Esta guía te llevará paso a paso para iniciar el Sistema Inteligente de Pronóstico de Demanda Energética.

---

## ✅ PREREQUISITOS

Antes de comenzar, verifica que tengas instalado:

- ✅ Docker Desktop (versión 20.10 o superior)
- ✅ Docker Compose (versión 2.0 o superior)
- ✅ 8 GB RAM disponible
- ✅ 20 GB espacio en disco
- ✅ Python 3.10+ (para generar el SQL desde el Parquet)

---

## 📋 CHECKLIST DE ARCHIVOS NECESARIOS

Antes de iniciar Docker, asegúrate de tener estos 3 archivos en la carpeta `models/`:

```
models/
├── ✅ best_energy_model.pkl      # Tu modelo XGBRegressor entrenado
├── ✅ features.pkl                # Lista de features (17 features)
└── ✅ model_metadata.pkl          # Metadatos del modelo
```

**Ya confirmaste que los tienes, así que estamos listos para continuar.**

---

## 🔄 PASO 1: CONVERTIR PARQUET A SQL

Tu archivo Parquet contiene los datos de entrenamiento. Vamos a convertirlos en INSERT SQL:

### 1.1. Ejecuta el script de conversión

```powershell
# Navega al directorio del proyecto
cd "c:\Users\John\OneDrive - Universidad Nacional Mayor de San Marcos\Escritorio\Proyectos_Personales\ProyectosJupyter\EnergyForecastAgent"

# Ejecuta el script
python scripts/parquet_to_sql.py
```

### 1.2. Sigue las instrucciones del script

El script te preguntará:
1. ¿Qué archivo .parquet usar? (si hay varios)
2. ¿Cuántas filas exportar? (recomendado: últimas 168 horas = 7 días)

**💡 RECOMENDACIÓN:** Exporta solo las últimas 168-336 horas (7-14 días) para no sobrecargar la base de datos inicial.

### 1.3. El script generará un archivo SQL

Por ejemplo: `data_train_insert.sql` con contenido como:

```sql
INSERT INTO historical_energy (timestamp, energy_mw, temperature, humidity, precipitation, solar_radiation)
VALUES
    ('2024-01-01 00:00:00', 5234.50, 22.5, 65.0, 0.5, 450.0),
    ('2024-01-01 01:00:00', 5100.23, 21.8, 67.2, 0.3, 420.5),
    ...
```

---

## 📝 PASO 2: ACTUALIZAR init.sql

### 2.1. Abre el archivo generado

Abre `data_train_insert.sql` (o como se llame tu archivo generado)

### 2.2. Copia su contenido

Selecciona todo el contenido del archivo (especialmente la parte de INSERT)

### 2.3. Reemplaza en init.sql

Abre `sql/init.sql` y busca la sección:

```sql
-- ============================================================================
-- DATOS DE EJEMPLO (Para testing/desarrollo)
-- ============================================================================

-- Insertar datos históricos de ejemplo (últimas 48 horas)
INSERT INTO historical_energy (timestamp, energy_mw, temperature, humidity, precipitation, solar_radiation)
SELECT 
    timestamp_series AS timestamp,
    4500 + 1500 * SIN(...) + RANDOM() * 500 AS energy_mw,
    ...
```

**REEMPLAZA** todo ese bloque con el contenido del archivo SQL generado.

**IMPORTANTE:** Mantén las líneas anteriores (creación de tablas) y posteriores (GRANTS).

---

## 🔑 PASO 3: CONFIGURAR VARIABLES DE ENTORNO

### 3.1. Crea el archivo .env

```powershell
# Copia el template
Copy-Item .env.example .env
```

### 3.2. Edita el archivo .env

Abre `.env` con un editor de texto y configura:

```env
# API Key de OpenWeatherMap (OBLIGATORIO)
WEATHER_API_KEY=tu_api_key_aqui

# Base de Datos PostgreSQL
POSTGRES_USER=energy_user
POSTGRES_PASSWORD=energy_pass
POSTGRES_DB=energy_forecast

# Airflow
AIRFLOW_USER=admin
AIRFLOW_PASSWORD=admin
```

**🔑 OBTENER API KEY DE OPENWEATHERMAP:**
1. Ve a: https://openweathermap.org/api
2. Regístrate gratis
3. Ve a "API Keys" en tu perfil
4. Copia tu API key y pégala en `.env`

---

## 🐳 PASO 4: CONSTRUIR E INICIAR DOCKER

### 4.1. Construye las imágenes Docker

```powershell
docker-compose build
```

Esto tomará 5-10 minutos la primera vez.

### 4.2. Inicia todos los servicios

```powershell
docker-compose up -d
```

### 4.3. Verifica que todos los contenedores estén corriendo

```powershell
docker-compose ps
```

Deberías ver algo como:

```
NAME                                      STATUS
energy_forecast_db                        Up (healthy)
energy_forecast_api                       Up (healthy)
energy_forecast_redis                     Up (healthy)
energy_forecast_airflow_webserver         Up (healthy)
energy_forecast_airflow_scheduler         Up
energy_forecast_airflow_worker            Up
energy_forecast_airflow_flower            Up
```

### 4.4. Espera a que Airflow se inicialice

```powershell
# Ver logs del webserver
docker-compose logs -f airflow-webserver
```

Espera hasta ver: `"Airflow Webserver ready"` (aprox 2-3 minutos)

Presiona `Ctrl+C` para salir de los logs.

---

## ✅ PASO 5: VERIFICAR LA INSTALACIÓN

### 5.1. Verificar la Base de Datos

```powershell
# Conectar a PostgreSQL
docker-compose exec db psql -U energy_user -d energy_forecast

# Dentro de psql, ejecuta:
SELECT COUNT(*) FROM historical_energy;
SELECT MIN(timestamp), MAX(timestamp) FROM historical_energy;

# Salir de psql
\q
```

Deberías ver la cantidad de registros que insertaste (ej: 168 registros si exportaste 7 días).

### 5.2. Verificar la API

```powershell
# Health check
curl http://localhost:8000/health

# Información del modelo
curl http://localhost:8000/model/info
```

Deberías ver:

```json
{
  "status": "healthy",
  "model_loaded": true,
  "expected_features": 17
}
```

### 5.3. Verificar Airflow

Abre tu navegador y ve a: **http://localhost:8080**

- **Usuario:** `admin`
- **Contraseña:** `admin`

Deberías ver el dashboard de Airflow con el DAG `energy_forecast_daily`.

---

## 🎮 PASO 6: EJECUTAR EL DAG MANUALMENTE (Primera Prueba)

### 6.1. En la UI de Airflow

1. Busca el DAG `energy_forecast_daily`
2. Actívalo con el toggle (switch a la izquierda del nombre)
3. Click en el botón ▶️ "Trigger DAG" (arriba a la derecha)

### 6.2. Monitorear la ejecución

1. Click en el nombre del DAG
2. Ve a la pestaña "Graph"
3. Observa cómo se ejecutan las tareas en orden:
   - `perceive_db_state` (verde = éxito)
   - `perceive_weather_forecast` (paralelo con el anterior)
   - `feature_engineering`
   - `predict`
   - `act_store_forecast`
   - `monitor_quality`

### 6.3. Ver los logs de cada tarea

- Click en cualquier tarea (cuadro en el grafo)
- Click en "Log"
- Revisa los logs para ver el proceso detallado

---

## 🔍 PASO 7: VERIFICAR EL PRONÓSTICO GENERADO

### 7.1. Consultar los pronósticos en la base de datos

```powershell
docker-compose exec db psql -U energy_user -d energy_forecast -c "
SELECT 
    forecast_timestamp, 
    predicted_energy_mw, 
    model_version,
    created_at
FROM energy_forecasts
ORDER BY forecast_timestamp ASC
LIMIT 24;
"
```

Deberías ver 24 registros con pronósticos para las próximas 24 horas.

### 7.2. Verificar estadísticas

```powershell
docker-compose exec db psql -U energy_user -d energy_forecast -c "
SELECT 
    COUNT(*) as total_forecasts,
    ROUND(AVG(predicted_energy_mw), 2) as avg_forecast,
    ROUND(MIN(predicted_energy_mw), 2) as min_forecast,
    ROUND(MAX(predicted_energy_mw), 2) as max_forecast
FROM energy_forecasts;
"
```

---

## 📊 PASO 8: ACCEDER A LOS SERVICIOS

Una vez que todo esté funcionando:

| Servicio | URL | Credenciales |
|----------|-----|--------------|
| **Airflow UI** | http://localhost:8080 | admin / admin |
| **API Docs (Swagger)** | http://localhost:8000/docs | - |
| **Flower (Celery Monitor)** | http://localhost:5555 | - |
| **PostgreSQL** | localhost:5432 | energy_user / energy_pass |

---

## 🔄 PASO 9: CONFIGURAR EJECUCIÓN AUTOMÁTICA

El DAG ya está configurado para ejecutarse automáticamente todos los días a las 5:00 AM.

Para verificar el schedule:

1. En Airflow UI, ve al DAG
2. En "Details" verás: `Schedule: 0 5 * * *`

Si quieres cambiar el horario:
1. Edita `dags/forecast_dag.py`
2. Busca: `schedule_interval='0 5 * * *'`
3. Cámbialo (formato cron)
4. Reinicia Airflow: `docker-compose restart airflow-scheduler`

---

## 🧪 PASO 10: TEST DE PREDICCIÓN MANUAL (Opcional)

Para hacer una predicción manual desde la línea de comandos:

```powershell
# Crear archivo test_prediction.json
@"
{
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
}
"@ | Out-File -Encoding utf8 test_prediction.json

# Hacer la predicción
curl -X POST http://localhost:8000/predict `
  -H "Content-Type: application/json" `
  -d "@test_prediction.json"
```

---

## 🛑 COMANDOS ÚTILES

### Ver logs en tiempo real

```powershell
# Todos los servicios
docker-compose logs -f

# Solo API
docker-compose logs -f api

# Solo Airflow Scheduler
docker-compose logs -f airflow-scheduler

# Solo Base de Datos
docker-compose logs -f db
```

### Reiniciar un servicio específico

```powershell
docker-compose restart api
docker-compose restart airflow-scheduler
```

### Detener todos los servicios

```powershell
docker-compose down
```

### Detener y eliminar todo (incluyendo volúmenes)

```powershell
docker-compose down -v
```

### Ver uso de recursos

```powershell
docker stats
```

---

## 🐛 TROUBLESHOOTING

### Problema: El API no carga el modelo

```powershell
# Verificar que los archivos .pkl existan
docker-compose exec api ls -lh /app/models/

# Ver logs del API
docker-compose logs api | Select-String -Pattern "error" -Context 3
```

### Problema: El DAG no se ejecuta

```powershell
# Verificar que el DAG esté activo
# En Airflow UI, el toggle debe estar en ON (azul)

# Re-parsear DAGs
docker-compose exec airflow-scheduler airflow dags reserialize
```

### Problema: No hay datos históricos

```powershell
# Verificar la tabla
docker-compose exec db psql -U energy_user -d energy_forecast -c "SELECT COUNT(*) FROM historical_energy;"

# Si está vacía, reiniciar la base de datos
docker-compose down -v
docker-compose up -d db
# Espera 30 segundos
docker-compose up -d
```

### Problema: Error de conexión a PostgreSQL

```powershell
# Verificar que PostgreSQL esté corriendo
docker-compose ps db

# Verificar health check
docker-compose exec db pg_isready -U energy_user -d energy_forecast
```

---

## 📚 PRÓXIMOS PASOS

Una vez que el sistema esté funcionando:

1. **Monitorear** las ejecuciones diarias en Airflow
2. **Validar** los pronósticos comparándolos con datos reales:
   ```sql
   SELECT * FROM validate_forecast();
   ```
3. **Analizar** el performance del modelo:
   ```sql
   SELECT * FROM forecast_accuracy LIMIT 7;
   ```
4. **Ajustar** el feature engineering si es necesario
5. **Re-entrenar** el modelo periódicamente con datos nuevos

---

## 📞 SOPORTE

Si tienes problemas:

1. Revisa los logs: `docker-compose logs -f`
2. Verifica que todos los servicios estén "healthy": `docker-compose ps`
3. Consulta la documentación completa en `README.md`
4. Revisa `INTEGRATION_GUIDE.md` para problemas con el modelo

---

**¡LISTO! Tu Sistema Inteligente de Pronóstico de Demanda Energética está en funcionamiento! 🎉**
