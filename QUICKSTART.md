# 🚀 Guía de Inicio Rápido - Sistema de Pronóstico de Energía

## ⚡ Despliegue en 5 Minutos

### 1️⃣ Pre-requisitos
```bash
# Verificar Docker
docker --version  # Debe ser >= 20.10

# Verificar Docker Compose
docker-compose --version  # Debe ser >= 2.0
```

### 2️⃣ Configuración Inicial
```bash
# 1. Copiar archivo de configuración
cp .env.example .env

# 2. Editar .env y cambiar:
#    - WEATHER_API_KEY (obtener gratis en openweathermap.org)
#    - Coordenadas de ubicación (LOCATION_LAT, LOCATION_LON)
notepad .env  # Windows
nano .env     # Linux/Mac
```

### 3️⃣ Colocar Modelos
```bash
# Copiar los archivos del modelo a la carpeta models/
# Estructura requerida:
models/
├── best_energy_model.pkl    # ← TU MODELO XGBRegressor
├── features.pkl              # ← LISTA DE FEATURES
└── model_metadata.pkl        # ← METADATOS
```

### 4️⃣ Iniciar Sistema
```bash
# Construir imágenes
docker-compose build

# Iniciar todos los servicios
docker-compose up -d

# Verificar estado
docker-compose ps
```

### 5️⃣ Acceder a los Servicios

| Servicio | URL | Credenciales |
|----------|-----|--------------|
| **Airflow UI** | http://localhost:8080 | admin / admin |
| **API (Swagger)** | http://localhost:8000/docs | - |
| **Flower (Monitoring)** | http://localhost:5555 | - |

---

## ✅ Verificación del Deployment

### Verificar Base de Datos
```bash
docker-compose exec db psql -U energy_user -d energy_forecast -c "SELECT COUNT(*) FROM historical_energy;"
```
**Resultado esperado**: Al menos 48 registros (datos de ejemplo)

### Verificar API
```bash
curl http://localhost:8000/health
```
**Resultado esperado**: `{"status":"healthy","model_loaded":true,"scaler_loaded":true}`

### Verificar Modelo
```bash
curl http://localhost:8000/model/info
```
**Resultado esperado**: JSON con información del modelo y 17 features

---

## 🎯 Ejecutar el Primer Pronóstico

### Opción A: Desde Airflow UI
1. Ir a http://localhost:8080
2. Login: `admin` / `admin`
3. Buscar DAG: `energy_forecast_daily`
4. Activar el toggle (cambiar a ON)
5. Click en "▶️ Trigger DAG"
6. Monitorear en "Graph View"

### Opción B: Desde CLI
```bash
docker-compose exec airflow-scheduler airflow dags trigger energy_forecast_daily
```

---

## 📊 Ver Resultados

### Consultar Pronósticos Generados
```bash
docker-compose exec db psql -U energy_user -d energy_forecast -c "
SELECT 
    forecast_timestamp, 
    predicted_energy_mw, 
    created_at
FROM energy_forecasts
ORDER BY forecast_timestamp DESC
LIMIT 10;
"
```

### Ver Logs del DAG
```bash
# Logs del scheduler
docker-compose logs -f airflow-scheduler

# Logs de una tarea específica (desde Airflow UI)
# Airflow UI → DAG → Graph → Click en tarea → Logs
```

---

## 🔧 Comandos Útiles

### Reiniciar un Servicio
```bash
docker-compose restart api           # Reiniciar API
docker-compose restart airflow-scheduler  # Reiniciar Scheduler
```

### Ver Logs
```bash
docker-compose logs -f api           # Logs de API
docker-compose logs -f airflow-worker  # Logs de Worker
docker-compose logs --tail=100 airflow-scheduler  # Últimas 100 líneas
```

### Acceder a un Contenedor
```bash
docker-compose exec api bash         # Shell en API
docker-compose exec db psql -U energy_user -d energy_forecast  # PostgreSQL
```

### Detener Todo
```bash
docker-compose down                  # Detener sin borrar datos
docker-compose down -v               # Detener y borrar volúmenes (⚠️ BORRA DB)
```

---

## 🐛 Troubleshooting Rápido

### ❌ "API no carga el modelo"
```bash
# Verificar que los archivos .pkl estén presentes
docker-compose exec api ls -lh /app/models/

# Verificar logs de la API
docker-compose logs api | grep -i error

# Reiniciar API
docker-compose restart api
```

### ❌ "DAG no aparece en Airflow"
```bash
# Re-parsear DAGs
docker-compose exec airflow-scheduler airflow dags reserialize

# Verificar errores de sintaxis
docker-compose exec airflow-scheduler airflow dags list-import-errors
```

### ❌ "No hay datos históricos"
```bash
# Re-ejecutar script de inicialización
docker-compose exec db psql -U energy_user -d energy_forecast -f /docker-entrypoint-initdb.d/init.sql
```

### ❌ "Error de conexión a Weather API"
```bash
# Verificar API key en .env
grep WEATHER_API_KEY .env

# Probar la API manualmente
curl "https://api.openweathermap.org/data/2.5/weather?lat=-12.0464&lon=-77.0428&appid=TU_API_KEY"
```

---

## 📚 Próximos Pasos

1. **Personalizar Features**: Editar `dags/utils/feature_engineering.py`
2. **Ajustar Schedule**: Modificar `schedule_interval` en `dags/forecast_dag.py`
3. **Agregar Alertas**: Configurar SMTP en `.env`
4. **Actualizar Modelo**: Reemplazar archivos en `models/` y reiniciar API
5. **Monitorear Performance**: Consultar tabla `model_performance`

---

## 🆘 Obtener Ayuda

- **Documentación Completa**: Ver `README.md`
- **Logs Detallados**: `docker-compose logs -f [servicio]`
- **Estado de Servicios**: `docker-compose ps`
- **Health Checks**: 
  - API: `curl http://localhost:8000/health`
  - Airflow: `curl http://localhost:8080/health`

---

## 📝 Checklist de Deployment

- [ ] Docker y Docker Compose instalados
- [ ] Archivo `.env` configurado con API key del clima
- [ ] Archivos del modelo (.pkl) en carpeta `models/`
- [ ] `docker-compose build` ejecutado exitosamente
- [ ] `docker-compose up -d` ejecutado
- [ ] Todos los servicios en estado "healthy" (`docker-compose ps`)
- [ ] API responde en http://localhost:8000/health
- [ ] Airflow UI accesible en http://localhost:8080
- [ ] DAG `energy_forecast_daily` visible en Airflow
- [ ] DAG ejecutado manualmente con éxito
- [ ] Pronósticos almacenados en la base de datos

---

**¡Sistema Listo! 🎉**

El agente ahora ejecutará automáticamente el pronóstico todos los días a las 5:00 AM.
