"""
API FastAPI - El "Cerebro" del Agente Racional

Este microservicio envuelve el modelo XGBRegressor y expone un endpoint /predict
que recibe las 17 features ya procesadas y retorna el pronóstico de demanda energética.

Arquitectura del Agente:
- Rol: Actuator (cerebro de decisión)
- Entrada: 17 features procesadas por el orquestador
- Salida: Pronóstico de carga eléctrica (MW) para 24 horas
"""

import os
import pickle
import logging
from typing import List, Dict, Any
from contextlib import asynccontextmanager

import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from ingestion import router as ingestion_router
from dashboard import router as dashboard_router

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variables globales para el modelo
model = None
expected_features = None
metadata = None


class FeaturesInput(BaseModel):
    """
    Modelo Pydantic que define las 17 features esperadas por el modelo XGBRegressor.
    
    Features Climáticas:
    - PRECTOT: Precipitación total
    - RH2M: Humedad relativa al 2m
    - T2M: Temperatura al 2m
    - ALLSKY: Radiación solar
    
    Features Calendáricas:
    - HOLIDAY: Indicador de día festivo (0 o 1)
    - IsWeekend: Indicador de fin de semana (0 o 1)
    
    Features Cíclicas (Codificación Sin/Cos):
    - Hour_sin, Hour_cos: Hora del día
    - Month_sin, Month_cos: Mes del año
    - DayOfWeek_sin, DayOfWeek_cos: Día de la semana
    
    Features Derivadas:
    - Temp_Range: Rango de temperatura calculado
    
    Features de Lag/Ventana:
    - ENERGY_lag1: Energía del período anterior
    - ENERGY_lag24: Energía de hace 24 períodos
    - ENERGY_rolling_mean_24: Media móvil de 24 períodos
    - ENERGY_rolling_std_24: Desviación estándar móvil de 24 períodos
    """
    
    # Features Climáticas
    PRECTOT: float = Field(..., description="Precipitación total")
    RH2M: float = Field(..., description="Humedad relativa al 2m (%)")
    T2M: float = Field(..., description="Temperatura al 2m (°C)")
    ALLSKY: float = Field(..., description="Radiación solar (W/m²)")
    
    # Features Calendáricas
    HOLIDAY: int = Field(..., ge=0, le=1, description="Es día festivo (0=No, 1=Sí)")
    IsWeekend: int = Field(..., ge=0, le=1, description="Es fin de semana (0=No, 1=Sí)")
    
    # Features Cíclicas
    Hour_sin: float = Field(..., ge=-1, le=1, description="Hora del día (componente seno)")
    Hour_cos: float = Field(..., ge=-1, le=1, description="Hora del día (componente coseno)")
    Month_sin: float = Field(..., ge=-1, le=1, description="Mes del año (componente seno)")
    Month_cos: float = Field(..., ge=-1, le=1, description="Mes del año (componente coseno)")
    DayOfWeek_sin: float = Field(..., ge=-1, le=1, description="Día de la semana (componente seno)")
    DayOfWeek_cos: float = Field(..., ge=-1, le=1, description="Día de la semana (componente coseno)")
    
    # Features Derivadas
    Temp_Range: float = Field(..., description="Rango de temperatura")
    
    # Features de Lag/Ventana
    ENERGY_lag1: float = Field(..., description="Energía del período anterior (MW)")
    ENERGY_lag24: float = Field(..., description="Energía de hace 24 períodos (MW)")
    ENERGY_rolling_mean_24: float = Field(..., description="Media móvil de 24 períodos (MW)")
    ENERGY_rolling_std_24: float = Field(..., description="Desviación estándar móvil de 24 períodos (MW)")

    class Config:
        json_schema_extra = {
            "example": {
                "PRECTOT": 0.5,
                "RH2M": 65.0,
                "T2M": 22.5,
                "ALLSKY": 450.0,
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
        }


class BatchFeaturesInput(BaseModel):
    """
    Modelo para predicción por lotes (batch) de 24 horas.
    """
    features: List[FeaturesInput] = Field(..., description="Lista de features para cada hora")
    
    @validator('features')
    def validate_batch_size(cls, v):
        if len(v) not in [1, 24]:
            raise ValueError('El batch debe contener 1 o 24 registros (predicción horaria o diaria)')
        return v


class PredictionResponse(BaseModel):
    """
    Respuesta del endpoint de predicción.
    """
    predictions: List[float] = Field(..., description="Predicciones de carga eléctrica (MW)")
    n_predictions: int = Field(..., description="Número de predicciones realizadas")
    model_version: str = Field(..., description="Versión del modelo utilizado")
    features_scaled: bool = Field(..., description="Indica si las features fueron escaladas")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager para cargar el modelo y scaler al inicio de la aplicación.
    """
    global model, scaler, expected_features, metadata
    
    logger.info("Inicializando el Cerebro del Agente...")
    
    # Cargar rutas desde variables de entorno
    model_path = os.getenv("MODEL_PATH", "/app/models/best_energy_model.pkl")
    features_path = os.getenv("FEATURES_PATH", "/app/models/features.pkl")
    metadata_path = os.getenv("METADATA_PATH", "/app/models/model_metadata.pkl")
    
    try:
        # Cargar el modelo XGBRegressor
        logger.info(f"Cargando modelo desde: {model_path}")
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
        logger.info("✓ Modelo cargado exitosamente")
        
        # Cargar las features esperadas
        logger.info(f"Cargando features desde: {features_path}")
        with open(features_path, 'rb') as f:
            expected_features = pickle.load(f)
        logger.info(f"✓ Features cargadas: {len(expected_features)} features esperadas")
        logger.info(f"  Features: {expected_features}")
        
        # Cargar metadatos
        logger.info(f"Cargando metadatos desde: {metadata_path}")
        with open(metadata_path, 'rb') as f:
            metadata = pickle.load(f)
        logger.info(f"✓ Metadatos cargados: {metadata}")
        
        logger.info("="*60)
        logger.info("🧠 CEREBRO DEL AGENTE INICIALIZADO")
        logger.info("="*60)
        
    except FileNotFoundError as e:
        logger.error(f"❌ Error: Archivo no encontrado - {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Error al cargar artefactos del modelo: {e}")
        raise
    
    yield
    
    # Cleanup (si es necesario)
    logger.info("Apagando el Cerebro del Agente...")


# Crear la aplicación FastAPI
app = FastAPI(
    title="Energy Forecast API - Cerebro del Agente",
    description="Microservicio que expone el modelo XGBRegressor para pronóstico de demanda energética",
    version="1.0.0",
    lifespan=lifespan
)

# Incluir router de ingestión
app.include_router(ingestion_router)

# Incluir router de dashboard
app.include_router(dashboard_router)


@app.get("/", tags=["Status"])
async def root():
    """
    Endpoint raíz con información del servicio.
    """
    return {
        "service": "Energy Forecast API",
        "role": "Cerebro del Agente Racional",
        "version": "1.0.0",
        "status": "operational",
        "model_loaded": model is not None
    }


@app.get("/health", tags=["Status"])
async def health_check():
    """
    Health check para Docker y orquestadores.
    """
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Modelo no cargado"
        )
    
    return {
        "status": "healthy",
        "model_loaded": True,
        "expected_features": len(expected_features) if expected_features else 0
    }


@app.get("/model/info", tags=["Model"])
async def model_info():
    """
    Información sobre el modelo y features esperadas.
    """
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Modelo no cargado"
        )
    
    return {
        "model_type": type(model).__name__,
        "expected_features": expected_features,
        "n_features": len(expected_features) if expected_features else 0,
        "metadata": metadata
    }


@app.post("/predict", response_model=PredictionResponse, tags=["Prediction"])
async def predict(data: BatchFeaturesInput):
    """
    Endpoint principal de predicción.
    
    Recibe un lote de features (1-24 horas) ya procesadas por el orquestador,
    aplica el scaler y retorna las predicciones.
    
    Flujo:
    1. Validar que el modelo esté cargado
    2. Convertir las features a DataFrame
    3. Validar que las columnas coincidan con expected_features
    4. Ejecutar model.predict()
    5. Retornar predicciones
    """
    
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Modelo no disponible"
        )
    
    try:
        # Convertir la lista de features a DataFrame
        features_list = [feat.dict() for feat in data.features]
        df = pd.DataFrame(features_list)
        
        logger.info(f"Predicción solicitada para {len(df)} registros")
        logger.info(f"Columnas recibidas: {df.columns.tolist()}")
        
        # Validar que las columnas coincidan con expected_features
        if expected_features is not None:
            missing_cols = set(expected_features) - set(df.columns)
            extra_cols = set(df.columns) - set(expected_features)
            
            if missing_cols:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Faltan columnas: {list(missing_cols)}"
                )
            
            if extra_cols:
                logger.warning(f"Columnas extra ignoradas: {list(extra_cols)}")
            
            # Reordenar columnas según expected_features
            df = df[expected_features]
        
        # Realizar predicción (sin scaling)
        logger.info("Ejecutando predicción...")
        predictions = model.predict(df)
        
        # Convertir a lista de floats nativos de Python
        predictions_list = [float(pred) for pred in predictions]
        
        logger.info(f"✓ Predicción exitosa: {len(predictions_list)} valores generados")
        logger.info(f"  Rango: [{min(predictions_list):.2f}, {max(predictions_list):.2f}] MW")
        
        return PredictionResponse(
            predictions=predictions_list,
            n_predictions=len(predictions_list),
            model_version=metadata.get("version", "1.0") if metadata else "1.0",
            features_scaled=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error durante la predicción: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error en la predicción: {str(e)}"
        )


@app.post("/predict/single", tags=["Prediction"])
async def predict_single(features: FeaturesInput):
    """
    Endpoint simplificado para predicción de un único registro.
    """
    batch = BatchFeaturesInput(features=[features])
    result = await predict(batch)
    
    return {
        "prediction": result.predictions[0],
        "model_version": result.model_version,
        "features_scaled": result.features_scaled
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
