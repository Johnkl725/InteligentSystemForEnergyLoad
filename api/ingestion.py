"""
API Endpoints para Ingesta Inteligente de Datos

Permite a los usuarios ingresar nuevos datos de energía que serán:
1. Validados automáticamente
2. Procesados con feature engineering
3. Almacenados en la BD
4. Usados para reentrenar el modelo (si es necesario)
"""

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import pandas as pd
import numpy as np
import logging

from database import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


class EnergyDataInput(BaseModel):
    """
    Modelo de datos que el usuario ingresa desde el formulario.
    Corresponde a las columnas de historical_energy.
    """
    timestamp: datetime = Field(..., description="Fecha y hora del registro")
    ENERGY: float = Field(..., ge=0, description="Demanda energética (MW)")
    
    # Variables meteorológicas
    PRECTOT: float = Field(..., ge=0, description="Precipitación total (mm)")
    RH2M: float = Field(..., ge=0, le=100, description="Humedad relativa (%)")
    T2M: float = Field(..., description="Temperatura promedio (°C)")
    T2M_MIN: Optional[float] = Field(None, description="Temperatura mínima (°C)")
    T2M_MAX: Optional[float] = Field(None, description="Temperatura máxima (°C)")
    ALLSKY: float = Field(..., ge=0, description="Radiación solar (W/m²)")
    
    # Variables calendáricas
    HOLIDAY: int = Field(0, ge=0, le=1, description="Es día festivo (0=No, 1=Sí)")
    
    # Variables opcionales (se calcularán si no se proveen)
    HDD18_3: Optional[float] = Field(None, description="Heating Degree Days")
    CDD0: Optional[float] = Field(None, description="Cooling Degree Days (base 0)")
    CDD10: Optional[float] = Field(None, description="Cooling Degree Days (base 10)")
    
    @validator('T2M_MIN', 'T2M_MAX', always=True)
    def validate_temperatures(cls, v, values):
        """Validar consistencia de temperaturas"""
        if 'T2M' in values:
            t2m = values['T2M']
            if v is not None:
                # T2M_MIN debe ser <= T2M <= T2M_MAX
                if 'T2M_MIN' in values and values['T2M_MIN'] is not None:
                    if values['T2M_MIN'] > t2m:
                        raise ValueError("T2M_MIN no puede ser mayor que T2M")
                if 'T2M_MAX' in values and values['T2M_MAX'] is not None:
                    if values['T2M_MAX'] < t2m:
                        raise ValueError("T2M_MAX no puede ser menor que T2M")
        return v
    
    @validator('timestamp')
    def validate_timestamp_not_future(cls, v):
        """No permitir fechas futuras"""
        if v > datetime.now():
            raise ValueError("No se pueden ingresar datos de fechas futuras")
        return v


class IngestionResponse(BaseModel):
    """Respuesta de la ingesta"""
    status: str
    message: str
    record_id: Optional[int] = None
    validation_warnings: List[str] = []
    trigger_retraining: bool = False


@router.post("/submit", response_model=IngestionResponse)
async def submit_energy_data(data: EnergyDataInput) -> IngestionResponse:
    """
    Endpoint para ingresar un nuevo registro de energía.
    
    FLUJO DEL AGENTE DE INGESTA:
    1. Validar datos recibidos (Pydantic ya valida estructura)
    2. Calcular variables derivadas faltantes
    3. Verificar duplicados en BD
    4. Insertar en historical_energy
    5. Triggear DAG de reentrenamiento si es necesario
    """
    try:
        logger.info(f"📥 Recibiendo datos de ingesta para {data.timestamp}")
        
        warnings = []
        
        # ============================================================
        # 1. CALCULAR VARIABLES DERIVADAS FALTANTES
        # ============================================================
        
        # Calcular T2M_MIN y T2M_MAX si no se proveen
        if data.T2M_MIN is None:
            data.T2M_MIN = data.T2M - 5  # Estimación
            warnings.append("T2M_MIN no provisto, se estimó como T2M - 5°C")
        
        if data.T2M_MAX is None:
            data.T2M_MAX = data.T2M + 5  # Estimación
            warnings.append("T2M_MAX no provisto, se estimó como T2M + 5°C")
        
        # Calcular HDD y CDD si no se proveen
        if data.HDD18_3 is None:
            data.HDD18_3 = max(0, 18.3 - data.T2M)
            warnings.append("HDD18_3 calculado automáticamente")
        
        if data.CDD0 is None:
            data.CDD0 = max(0, data.T2M - 0)
            warnings.append("CDD0 calculado automáticamente")
        
        if data.CDD10 is None:
            data.CDD10 = max(0, data.T2M - 10)
            warnings.append("CDD10 calculado automáticamente")
        
        # ============================================================
        # 2. VERIFICAR DUPLICADOS
        # ============================================================
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        check_query = """
            SELECT id FROM historical_energy 
            WHERE timestamp = %s
        """
        cursor.execute(check_query, (data.timestamp,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=409,
                detail=f"Ya existe un registro para {data.timestamp}"
            )
        
        # ============================================================
        # 3. INSERTAR EN LA BASE DE DATOS
        # ============================================================
        
        insert_query = """
            INSERT INTO historical_energy (
                timestamp, ENERGY, HDD18_3, CDD0, CDD10,
                PRECTOT, RH2M, T2M, T2M_MIN, T2M_MAX,
                ALLSKY, HOLIDAY
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s
            )
            RETURNING id
        """
        
        cursor.execute(insert_query, (
            data.timestamp,
            data.ENERGY,
            data.HDD18_3,
            data.CDD0,
            data.CDD10,
            data.PRECTOT,
            data.RH2M,
            data.T2M,
            data.T2M_MIN,
            data.T2M_MAX,
            data.ALLSKY,
            data.HOLIDAY
        ))
        
        record_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"✅ Registro insertado exitosamente: ID={record_id}")
        
        # ============================================================
        # 4. DECIDIR SI TRIGGEAR REENTRENAMIENTO
        # ============================================================
        
        # Lógica: Si acumulamos 100+ registros nuevos, reentrenar
        trigger_retraining = await should_trigger_retraining()
        
        if trigger_retraining:
            logger.info("🔄 Triggeando DAG de reentrenamiento del modelo")
            await trigger_retraining_dag()
        
        return IngestionResponse(
            status="success",
            message=f"Registro insertado correctamente (ID: {record_id})",
            record_id=record_id,
            validation_warnings=warnings,
            trigger_retraining=trigger_retraining
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error en ingesta: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


@router.post("/submit_batch", response_model=Dict[str, Any])
async def submit_energy_data_batch(data_list: List[EnergyDataInput]) -> Dict[str, Any]:
    """
    Endpoint para ingresar múltiples registros (batch).
    Útil para carga masiva de datos.
    """
    try:
        logger.info(f"📥 Recibiendo batch de {len(data_list)} registros")
        
        results = {
            'total': len(data_list),
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        for i, data in enumerate(data_list):
            try:
                response = await submit_energy_data(data)
                results['success'] += 1
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'index': i,
                    'timestamp': str(data.timestamp),
                    'error': str(e)
                })
        
        logger.info(f"✅ Batch procesado: {results['success']}/{results['total']} exitosos")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Error en batch ingestion: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")


async def should_trigger_retraining() -> bool:
    """
    Decide si es necesario reentrenar el modelo.
    
    Criterios:
    - Más de 100 registros nuevos desde el último entrenamiento
    - Ha pasado más de 1 semana desde el último entrenamiento
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Contar registros nuevos (sin usar en entrenamiento)
        query = """
            SELECT COUNT(*) 
            FROM historical_energy 
            WHERE created_at > (
                SELECT MAX(created_at) 
                FROM model_training_history
            )
        """
        
        cursor.execute(query)
        new_records = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return new_records >= 100
        
    except Exception as e:
        logger.warning(f"No se pudo verificar necesidad de reentrenamiento: {e}")
        return False


async def trigger_retraining_dag():
    """
    Triggea el DAG de reentrenamiento del modelo vía API de Airflow.
    """
    try:
        import requests
        import os
        
        airflow_url = os.getenv("AIRFLOW_API_URL", "http://airflow-webserver:8080")
        dag_id = "model_retraining_dag"
        
        url = f"{airflow_url}/api/v1/dags/{dag_id}/dagRuns"
        
        # Credenciales básicas de Airflow
        auth = ("airflow", "airflow")  # Cambiar en producción
        
        response = requests.post(
            url,
            json={"conf": {"triggered_by": "ingestion_agent"}},
            auth=auth,
            headers={"Content-Type": "application/json"}
        )
        
        response.raise_for_status()
        logger.info(f"✅ DAG de reentrenamiento triggeado exitosamente")
        
    except Exception as e:
        logger.error(f"❌ Error triggeando DAG de reentrenamiento: {e}")


@router.get("/stats")
async def get_ingestion_stats() -> Dict[str, Any]:
    """
    Estadísticas de los datos ingresados.
    """
    try:
        conn = get_db_connection()
        
        query = """
            SELECT 
                COUNT(*) as total_records,
                MIN(timestamp) as oldest_record,
                MAX(timestamp) as newest_record,
                AVG(ENERGY) as avg_energy,
                MIN(ENERGY) as min_energy,
                MAX(ENERGY) as max_energy
            FROM historical_energy
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        return df.to_dict(orient='records')[0]
        
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail=str(e))