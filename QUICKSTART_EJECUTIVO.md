# ⚡ INICIO RÁPIDO - RESUMEN EJECUTIVO

## 📋 TU SITUACIÓN ACTUAL

✅ **Archivos del modelo (.pkl)** → YA LOS TIENES en `models/`
❓ **Datos históricos** → Tienes un archivo `.parquet` que necesita convertirse a SQL
❓ **Iniciar el proyecto** → Necesitas seguir los pasos

---

## 🚀 INICIO EN 3 PASOS

### PASO 1: Convertir Parquet a SQL (5 minutos)

```powershell
# Ubica tu archivo .parquet en alguna carpeta del proyecto
# Por ejemplo: data/train_data.parquet

# Ejecuta el script de conversión
python scripts/parquet_to_sql.py
```

El script te preguntará:
1. ¿Qué archivo .parquet usar?
2. ¿Cuántas filas exportar?

**💡 RECOMENDACIÓN:** Exporta las **últimas 168-336 horas** (7-14 días) para tener suficiente historia sin sobrecargar.

El script generará un archivo como `train_data_insert.sql`

---

### PASO 2: Actualizar init.sql (2 minutos)

1. Abre el archivo SQL generado (`train_data_insert.sql`)
2. Copia todo el contenido del INSERT
3. Abre `sql/init.sql`
4. Busca la sección que dice:

```sql
-- ============================================================================
-- DATOS DE EJEMPLO (Para testing/desarrollo)
-- ============================================================================

-- Insertar datos históricos de ejemplo (últimas 48 horas)
INSERT INTO historical_energy (timestamp, energy_mw, temperature, humidity, precipitation, solar_radiation)
SELECT 
    timestamp_series AS timestamp,
    4500 + 1500 * SIN(...
```

5. **REEMPLAZA** desde `INSERT INTO historical_energy...` hasta `ON CONFLICT (timestamp) DO NOTHING;`

   Con el contenido del archivo generado

6. Guarda `sql/init.sql`

**✅ LISTO:** Ahora tienes datos reales en lugar de datos sintéticos.

---

### PASO 3: Iniciar el Proyecto (10 minutos)

#### Opción A: Script Automático (Recomendado)

```powershell
# Ejecuta el script de inicio
.\scripts\start_project.ps1
```

El script hará todo automáticamente:
- ✅ Verifica prerequisitos
- ✅ Verifica archivos .pkl
- ✅ Crea .env si no existe
- ✅ Construye imágenes Docker
- ✅ Inicia servicios
- ✅ Verifica que todo esté funcionando

#### Opción B: Manual

```powershell
# 1. Crear archivo de configuración
Copy-Item .env.example .env

# 2. Editar .env y agregar tu API key de OpenWeatherMap
notepad .env

# 3. Construir imágenes Docker
docker-compose build

# 4. Iniciar servicios
docker-compose up -d

# 5. Verificar estado
docker-compose ps
```

---

## 🎯 VERIFICACIÓN RÁPIDA

Una vez iniciado, verifica que todo funcione:

### 1. Base de Datos

```powershell
docker-compose exec db psql -U energy_user -d energy_forecast -c "SELECT COUNT(*) FROM historical_energy;"
```

Deberías ver el número de registros que insertaste.

### 2. API

```powershell
curl http://localhost:8000/health
```

Deberías ver: `{"status":"healthy","model_loaded":true}`

### 3. Airflow

Abre http://localhost:8080 en tu navegador
- Usuario: `admin`
- Contraseña: `admin`

Deberías ver el DAG `energy_forecast_daily`

---

## 🎮 PRIMERA EJECUCIÓN

1. En Airflow UI (http://localhost:8080)
2. Busca el DAG `energy_forecast_daily`
3. **Actívalo** con el toggle (switch azul)
4. Click en **▶️ "Trigger DAG"**
5. Ve a la vista **"Graph"** para ver el progreso
6. Espera 3-5 minutos hasta que todo esté verde ✅

### Ver el Resultado

```powershell
docker-compose exec db psql -U energy_user -d energy_forecast -c "
SELECT 
    forecast_timestamp, 
    predicted_energy_mw 
FROM energy_forecasts 
ORDER BY forecast_timestamp 
LIMIT 10;
"
```

Deberías ver 24 pronósticos para las próximas 24 horas! 🎉

---

## 📂 ESTRUCTURA DE ARCHIVOS IMPORTANTE

```
EnergyForecastAgent/
├── models/                          ✅ YA TIENES ESTO
│   ├── best_energy_model.pkl
│   ├── features.pkl
│   └── model_metadata.pkl
│
├── sql/
│   └── init.sql                     ⚠️ NECESITAS ACTUALIZAR ESTO (Paso 2)
│
├── scripts/
│   ├── parquet_to_sql.py           🆕 USA ESTO (Paso 1)
│   └── start_project.ps1           🆕 USA ESTO (Paso 3)
│
├── .env                             ⚠️ NECESITAS CREAR/EDITAR ESTO
├── START_PROJECT.md                 📖 Guía completa detallada
└── README.md                        📖 Documentación del sistema
```

---

## 🔑 API KEY DE OPENWEATHERMAP

**IMPORTANTE:** Necesitas una API key gratuita para obtener datos climáticos.

1. Ve a: https://openweathermap.org/api
2. Click en "Sign up" (crear cuenta)
3. Verifica tu email
4. Ve a tu perfil → "API Keys"
5. Copia tu API key
6. Pégala en el archivo `.env`:

```env
WEATHER_API_KEY=tu_api_key_aqui
```

---

## 🛑 COMANDOS ÚTILES

```powershell
# Ver logs en tiempo real
docker-compose logs -f

# Ver logs solo de un servicio
docker-compose logs -f api
docker-compose logs -f airflow-scheduler

# Reiniciar un servicio
docker-compose restart api

# Detener todo
docker-compose down

# Detener y eliminar todo (incluyendo datos)
docker-compose down -v

# Ver estado de servicios
docker-compose ps

# Ver uso de recursos
docker stats
```

---

## 🐛 PROBLEMAS COMUNES

### "No se encuentra el archivo .parquet"

```powershell
# Verifica dónde está tu archivo
Get-ChildItem -Recurse -Filter "*.parquet"

# Copia el parquet al proyecto
Copy-Item "ruta\a\tu\archivo.parquet" .\data\
```

### "API key inválida"

Verifica que hayas copiado correctamente la API key en `.env` sin espacios ni comillas extra.

### "El DAG no aparece en Airflow"

```powershell
# Reinicia el scheduler
docker-compose restart airflow-scheduler

# Espera 30 segundos
Start-Sleep -Seconds 30

# Refresca la página de Airflow
```

### "PostgreSQL no está listo"

```powershell
# Verificar que esté corriendo
docker-compose ps db

# Ver logs
docker-compose logs db

# Reiniciar si es necesario
docker-compose restart db
```

---

## 📞 AYUDA

Si tienes problemas:

1. Lee la **guía completa**: `START_PROJECT.md`
2. Revisa los **logs**: `docker-compose logs -f`
3. Consulta la documentación: `README.md` e `INTEGRATION_GUIDE.md`

---

## ✅ CHECKLIST FINAL

Antes de considerar el proyecto "listo":

- [ ] Archivo .parquet convertido a SQL
- [ ] `sql/init.sql` actualizado con datos reales
- [ ] Archivo `.env` creado y configurado con API key
- [ ] Archivos .pkl en `models/` (best_energy_model.pkl, features.pkl, model_metadata.pkl)
- [ ] Docker y Docker Compose instalados
- [ ] Servicios Docker corriendo (`docker-compose ps` muestra todos "Up")
- [ ] API responde en http://localhost:8000/health
- [ ] Airflow accesible en http://localhost:8080
- [ ] DAG ejecutado manualmente al menos una vez con éxito
- [ ] Pronósticos visibles en la base de datos

---

**🎉 ¡Eso es todo! Tu sistema estará listo en menos de 20 minutos siguiendo estos 3 pasos.**
