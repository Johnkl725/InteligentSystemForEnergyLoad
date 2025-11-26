# 🚀 Guía de Configuración para Colaboradores

Esta guía te ayudará a configurar el proyecto **Energy Forecast Agent** en tu entorno local.

## 📋 Prerrequisitos

Antes de comenzar, asegúrate de tener instalado:

- **Docker Desktop** (v20.10 o superior)
- **Docker Compose** (v2.0 o superior)
- **Git** (v2.30 o superior)
- **10 GB de espacio en disco** libre
- **Al menos 8 GB de RAM** disponible

## 🔧 Configuración Inicial

### 1. Clonar el Repositorio

```bash
git clone https://github.com/Johnkl725/InteligentSystemForEnergyLoad.git
cd InteligentSystemForEnergyLoad
```

### 2. Configurar Variables de Entorno

Crea tu archivo `.env` a partir del ejemplo:

```bash
# En Windows PowerShell
Copy-Item .env.example .env

# En Linux/Mac
cp .env.example .env
```

**IMPORTANTE:** Edita el archivo `.env` y configura:

- `WEATHER_API_KEY`: Obtén una API key gratuita en [OpenWeatherMap](https://openweathermap.org/api)
- Si necesitas cambiar las credenciales de base de datos, edita:
  - `POSTGRES_USER`
  - `POSTGRES_PASSWORD`
  - `POSTGRES_DB`

### 3. ⚠️ CRÍTICO: Descargar Modelos Entrenados

Los modelos ML no están incluidos en el repositorio por su tamaño. Tienes **2 opciones**:

#### Opción A: Descargar modelos pre-entrenados (Recomendado)

Descarga los modelos desde [aquí](AÑADE_EL_LINK_A_GOOGLE_DRIVE_O_RELEASES) y colócalos en la carpeta `models/`:

```
models/
├── best_energy_model.pkl       (obligatorio)
├── features.pkl                 (obligatorio)
└── model_metadata.pkl           (obligatorio)
```

#### Opción B: Entrenar tu propio modelo

Si prefieres entrenar desde cero:

```bash
# Ejecuta el notebook de entrenamiento
jupyter notebook notebooks/train_model.ipynb
```

Esto generará los archivos `.pkl` necesarios en la carpeta `models/`.

### 4. Construir y Levantar los Servicios

```bash
docker-compose up -d --build
```

**Primera ejecución:** Puede tardar 5-10 minutos en descargar imágenes y construir contenedores.

### 5. Verificar que Todo Funciona

Espera 2-3 minutos para que todos los servicios inicien, luego verifica:

```bash
# Ver el estado de los contenedores
docker-compose ps

# Verificar logs (busca errores)
docker-compose logs api
docker-compose logs airflow-webserver
```

**Todos los contenedores deben estar en estado "Up (healthy)".**

## 🌐 Acceso a los Servicios

Una vez que todo esté corriendo:

| Servicio | URL | Credenciales |
|----------|-----|--------------|
| **Streamlit Dashboard** | http://localhost:8501 | - |
| **FastAPI Docs** | http://localhost:8000/docs | - |
| **Airflow Web UI** | http://localhost:8080 | admin / admin |
| **PostgreSQL** | localhost:5432 | energy_user / energy_pass |
| **Flower (Celery)** | http://localhost:5555 | - |

## 🧪 Probar el Sistema

### Prueba 1: Health Check de la API

```bash
curl http://localhost:8000/health
```

Deberías ver:
```json
{"status": "healthy", "model_loaded": true, "expected_features": 17}
```

### Prueba 2: Verificar Modelo Cargado

```bash
curl http://localhost:8000/model/info
```

### Prueba 3: Hacer una Predicción Manual

Ve a http://localhost:8501 y prueba la página **"🔮 Predecir Demanda"**.

### Prueba 4: Ejecutar DAG en Airflow

1. Abre http://localhost:8080 (admin / admin)
2. Busca el DAG `energy_forecast_daily`
3. Click en el botón ▶️ para ejecutarlo manualmente
4. Verifica que todas las tareas se completen (verde)

## 🐛 Solución de Problemas Comunes

### Error: "Model not found" en la API

**Causa:** Faltan los archivos `.pkl` en la carpeta `models/`

**Solución:**
1. Verifica que existan los 3 archivos en `models/`:
   ```bash
   ls models/
   ```
2. Si no existen, descárgalos (ver paso 3)
3. Reinicia el contenedor:
   ```bash
   docker-compose restart api
   ```

### Error: "Connection refused" en Airflow

**Causa:** La base de datos no está lista

**Solución:**
```bash
# Espera 30 segundos y reinicia
docker-compose restart airflow-webserver airflow-scheduler
```

### Error: "ModuleNotFoundError" en la API

**Causa:** Falta reconstruir la imagen

**Solución:**
```bash
docker-compose down
docker-compose up -d --build api
```

### Los contenedores se reinician constantemente

**Causa:** Falta de recursos (RAM/CPU)

**Solución:**
1. Aumenta recursos en Docker Desktop (Configuración → Resources)
2. Mínimo recomendado: 8 GB RAM, 4 CPUs
3. O desactiva servicios no esenciales:
   ```bash
   # Levantar solo servicios básicos
   docker-compose up -d db api streamlit
   ```

### Airflow DAGs no aparecen

**Causa:** Problemas de sincronización de volúmenes

**Solución:**
```bash
# Reinicia el scheduler
docker-compose restart airflow-scheduler

# Espera 30 segundos y refresca la página
```

## 📁 Estructura del Proyecto

```
EnergyForecastAgent/
├── api/                    # FastAPI backend
│   ├── main.py            # Endpoints principales
│   ├── dashboard.py       # Endpoints de dashboard
│   ├── ingestion.py       # Endpoints de ingesta
│   ├── database.py        # Utilidades de BD
│   └── Dockerfile
├── airflow/               # Airflow setup
│   ├── Dockerfile
│   └── requirements.txt
├── dags/                  # Airflow DAGs
│   ├── forecast_dag.py   # DAG principal
│   └── utils/
├── streamlit_app/        # Frontend web
│   ├── app.py           # Página principal
│   └── pages/           # Páginas adicionales
├── models/              # ⚠️ NO en Git (descargar aparte)
│   ├── best_energy_model.pkl
│   ├── features.pkl
│   └── model_metadata.pkl
├── sql/                 # Scripts SQL iniciales
│   └── init.sql
├── docker-compose.yml   # Orquestación de servicios
└── .env.example         # Plantilla de variables de entorno
```

## 🔄 Comandos Útiles

```bash
# Ver logs en tiempo real
docker-compose logs -f [servicio]

# Detener todo
docker-compose down

# Detener y eliminar volúmenes (⚠️ borra la BD)
docker-compose down -v

# Reconstruir un servicio específico
docker-compose up -d --build [servicio]

# Acceder a un contenedor
docker exec -it energy_forecast_api bash

# Ver uso de recursos
docker stats

# Limpiar imágenes no usadas
docker system prune -a
```

## 📊 Flujo de Trabajo Típico

1. **Desarrollo local:**
   ```bash
   # Hacer cambios en el código
   # Reconstruir solo el servicio modificado
   docker-compose up -d --build api
   ```

2. **Ejecutar predicciones:**
   - Opción 1: Usar Streamlit UI (http://localhost:8501)
   - Opción 2: Llamar directamente a la API
   - Opción 3: Esperar a que Airflow ejecute el DAG

3. **Monitorear:**
   - Dashboard Streamlit para visualizaciones
   - Airflow UI para ver ejecución de DAGs
   - API logs para debugging

## 🤝 Contribuir

1. Crea una rama para tu feature:
   ```bash
   git checkout -b feature/mi-nueva-funcionalidad
   ```

2. Haz tus cambios y prueba localmente

3. Commit y push:
   ```bash
   git add .
   git commit -m "Añade nueva funcionalidad X"
   git push origin feature/mi-nueva-funcionalidad
   ```

4. Abre un Pull Request en GitHub

## 📞 Soporte

Si encuentras problemas:

1. Revisa la sección "Solución de Problemas" arriba
2. Revisa los logs: `docker-compose logs [servicio]`
3. Abre un issue en GitHub con:
   - Descripción del problema
   - Logs relevantes
   - Sistema operativo y versión de Docker

## 📝 Notas Importantes

- **No subas tu archivo `.env` al repositorio** (está en `.gitignore` por seguridad)
- **Los modelos `.pkl` son grandes** (900 KB+) por eso no están en Git
- **Primera ejecución es lenta** (descarga imágenes Docker)
- **Airflow necesita 2-3 minutos** para inicializar la base de datos
- **El puerto 8080 debe estar libre** (Airflow lo usa)

## 🔐 Seguridad

Para producción, **DEBES cambiar**:

- Contraseñas de PostgreSQL
- Fernet key de Airflow
- Credenciales de admin de Airflow
- Secret key del webserver

---

✨ **¡Listo para empezar!** Si todo funciona, deberías ver el dashboard en http://localhost:8501
