# ============================================================================
# SCRIPT DE INICIO RÁPIDO - POWERSHELL
# Sistema Inteligente de Pronóstico de Demanda Energética
# ============================================================================

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "   SISTEMA INTELIGENTE DE PRONÓSTICO DE DEMANDA ENERGÉTICA" -ForegroundColor Cyan
Write-Host "   Script de Inicio Rápido" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# Función para verificar si un comando existe
function Test-Command {
    param($Command)
    try {
        if (Get-Command $Command -ErrorAction Stop) {
            return $true
        }
    }
    catch {
        return $false
    }
}

# Verificar prerequisitos
Write-Host "[1/8] Verificando prerequisitos..." -ForegroundColor Yellow
$allGood = $true

if (Test-Command docker) {
    $dockerVersion = docker --version
    Write-Host "  ✓ Docker instalado: $dockerVersion" -ForegroundColor Green
} else {
    Write-Host "  ✗ Docker NO instalado" -ForegroundColor Red
    $allGood = $false
}

if (Test-Command docker-compose) {
    $composeVersion = docker-compose --version
    Write-Host "  ✓ Docker Compose instalado: $composeVersion" -ForegroundColor Green
} else {
    Write-Host "  ✗ Docker Compose NO instalado" -ForegroundColor Red
    $allGood = $false
}

if (Test-Command python) {
    $pythonVersion = python --version
    Write-Host "  ✓ Python instalado: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "  ⚠ Python NO instalado (necesario para convertir Parquet)" -ForegroundColor Yellow
}

if (-not $allGood) {
    Write-Host ""
    Write-Host "❌ Faltan prerequisitos. Por favor instala Docker y Docker Compose primero." -ForegroundColor Red
    exit 1
}

Write-Host ""

# Verificar archivos del modelo
Write-Host "[2/8] Verificando archivos del modelo..." -ForegroundColor Yellow
$modelFiles = @(
    "models\best_energy_model.pkl",
    "models\features.pkl",
    "models\model_metadata.pkl"
)

$modelFilesOK = $true
foreach ($file in $modelFiles) {
    if (Test-Path $file) {
        $size = (Get-Item $file).Length / 1KB
        Write-Host "  ✓ $file ($([math]::Round($size, 2)) KB)" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $file NO ENCONTRADO" -ForegroundColor Red
        $modelFilesOK = $false
    }
}

if (-not $modelFilesOK) {
    Write-Host ""
    Write-Host "❌ Faltan archivos del modelo (.pkl)" -ForegroundColor Red
    Write-Host "   Por favor coloca los archivos en la carpeta models/" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Verificar archivo .env
Write-Host "[3/8] Verificando configuración (.env)..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Write-Host "  ⚠ Archivo .env NO encontrado" -ForegroundColor Yellow
    Write-Host "  Creando .env desde .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "  ✓ Archivo .env creado" -ForegroundColor Green
    Write-Host ""
    Write-Host "  ⚠ IMPORTANTE: Edita el archivo .env y configura tu WEATHER_API_KEY" -ForegroundColor Yellow
    Write-Host "     1. Abre .env con un editor de texto" -ForegroundColor Yellow
    Write-Host "     2. Reemplaza 'your_openweather_api_key_here' con tu API key real" -ForegroundColor Yellow
    Write-Host "     3. Obtén tu API key en: https://openweathermap.org/api" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "  Presiona Enter cuando hayas configurado la API key"
} else {
    Write-Host "  ✓ Archivo .env encontrado" -ForegroundColor Green
}

Write-Host ""

# Preguntar si quiere convertir Parquet a SQL
Write-Host "[4/8] Preparación de datos históricos" -ForegroundColor Yellow
Write-Host "  ¿Ya actualizaste sql/init.sql con tus datos del Parquet? (s/n): " -NoNewline
$response = Read-Host

if ($response -eq "n" -or $response -eq "N") {
    Write-Host ""
    Write-Host "  Necesitas convertir tu archivo Parquet a SQL INSERT" -ForegroundColor Yellow
    Write-Host "  Ejecuta: python scripts\parquet_to_sql.py" -ForegroundColor Cyan
    Write-Host "  Luego, copia el contenido generado a sql/init.sql" -ForegroundColor Cyan
    Write-Host ""
    Read-Host "  Presiona Enter cuando hayas actualizado init.sql"
} else {
    Write-Host "  ✓ Datos históricos listos" -ForegroundColor Green
}

Write-Host ""

# Construir imágenes Docker
Write-Host "[5/8] Construyendo imágenes Docker..." -ForegroundColor Yellow
Write-Host "  Esto puede tomar 5-10 minutos la primera vez..." -ForegroundColor Yellow
docker-compose build

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Imágenes construidas exitosamente" -ForegroundColor Green
} else {
    Write-Host "  ✗ Error al construir imágenes" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Iniciar servicios
Write-Host "[6/8] Iniciando servicios Docker..." -ForegroundColor Yellow
docker-compose up -d

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Servicios iniciados" -ForegroundColor Green
} else {
    Write-Host "  ✗ Error al iniciar servicios" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Esperar a que los servicios estén listos
Write-Host "[7/8] Esperando a que los servicios estén listos..." -ForegroundColor Yellow
Write-Host "  Esto puede tomar 2-3 minutos..." -ForegroundColor Yellow

Start-Sleep -Seconds 30

$maxAttempts = 20
$attempt = 0
$dbReady = $false

while ($attempt -lt $maxAttempts -and -not $dbReady) {
    $attempt++
    Write-Host "  Verificando PostgreSQL (intento $attempt/$maxAttempts)..." -ForegroundColor Gray
    
    try {
        $result = docker-compose exec -T db pg_isready -U energy_user -d energy_forecast 2>&1
        if ($result -match "accepting connections") {
            $dbReady = $true
            Write-Host "  ✓ PostgreSQL listo" -ForegroundColor Green
        } else {
            Start-Sleep -Seconds 5
        }
    } catch {
        Start-Sleep -Seconds 5
    }
}

if (-not $dbReady) {
    Write-Host "  ⚠ PostgreSQL tardó demasiado en estar listo" -ForegroundColor Yellow
    Write-Host "  Continúa de todas formas..." -ForegroundColor Yellow
}

# Esperar a que Airflow esté listo
Start-Sleep -Seconds 30

Write-Host ""

# Verificar estado de servicios
Write-Host "[8/8] Verificando estado de servicios..." -ForegroundColor Yellow
docker-compose ps

Write-Host ""
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host "✅ SISTEMA INICIADO CORRECTAMENTE" -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "📊 SERVICIOS DISPONIBLES:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  • Airflow UI:     http://localhost:8080" -ForegroundColor White
Write-Host "                    Usuario: admin / Contraseña: admin" -ForegroundColor Gray
Write-Host ""
Write-Host "  • API (Swagger):  http://localhost:8000/docs" -ForegroundColor White
Write-Host "  • API Health:     http://localhost:8000/health" -ForegroundColor White
Write-Host ""
Write-Host "  • Flower:         http://localhost:5555" -ForegroundColor White
Write-Host ""
Write-Host "  • PostgreSQL:     localhost:5432" -ForegroundColor White
Write-Host "                    Usuario: energy_user / DB: energy_forecast" -ForegroundColor Gray
Write-Host ""

Write-Host "🔍 PRÓXIMOS PASOS:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  1. Abre Airflow UI: http://localhost:8080" -ForegroundColor Yellow
Write-Host "  2. Busca el DAG 'energy_forecast_daily'" -ForegroundColor Yellow
Write-Host "  3. Actívalo con el toggle (switch)" -ForegroundColor Yellow
Write-Host "  4. Click en el botón ▶️ 'Trigger DAG' para ejecutar manualmente" -ForegroundColor Yellow
Write-Host "  5. Monitorea la ejecución en la vista 'Graph'" -ForegroundColor Yellow
Write-Host ""

Write-Host "📚 DOCUMENTACIÓN:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  • Guía completa:  START_PROJECT.md" -ForegroundColor White
Write-Host "  • README:         README.md" -ForegroundColor White
Write-Host "  • Integración:    INTEGRATION_GUIDE.md" -ForegroundColor White
Write-Host ""

Write-Host "🛠️ COMANDOS ÚTILES:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Ver logs:         docker-compose logs -f" -ForegroundColor White
Write-Host "  Detener:          docker-compose down" -ForegroundColor White
Write-Host "  Reiniciar:        docker-compose restart" -ForegroundColor White
Write-Host "  Estado:           docker-compose ps" -ForegroundColor White
Write-Host ""

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host ""

# Preguntar si quiere abrir Airflow
Write-Host "¿Deseas abrir Airflow UI en el navegador? (s/n): " -NoNewline
$openBrowser = Read-Host

if ($openBrowser -eq "s" -or $openBrowser -eq "S") {
    Start-Process "http://localhost:8080"
}

Write-Host ""
Write-Host "¡Listo! El sistema está en funcionamiento. 🎉" -ForegroundColor Green
