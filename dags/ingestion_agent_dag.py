"""
DAG de Agente de Ingesta Inteligente

Este DAG procesa datos nuevos ingresados por usuarios:
1. Valida la calidad de los datos
2. Calcula features derivadas
3. Actualiza estadísticas de la BD
4. Triggea reentrenamiento si es necesario

Trigger: API call (desde endpoint /ingestion/submit)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any

import pandas as pd
import numpy as np
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook

logger = logging.getLogger(__name__)

default_args = {
    'owner': 'ingestion_agent',
    'depends_on_past': False,
    'email_on_failure': True,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}


@dag(
    dag_id='ingestion_data_validator',
    default_args=default_args,
    description='Agente de Validación y Procesamiento de Datos Ingresados',
    schedule_interval=None,  # Trigger manual desde API
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['ingestion', 'validation', 'data-quality'],
)
def ingestion_validator_agent():
    
    @task(task_id='validate_new_records')
    def validate_new_records(**context) -> Dict[str, Any]:
        """
        Valida los nuevos registros ingresados en la última hora.
        """
        logger.info("="*60)
        logger.info("🔍 VALIDANDO REGISTROS NUEVOS")
        logger.info("="*60)
        
        pg_hook = PostgresHook(postgres_conn_id='postgres_energy')
        
        query = """
            SELECT *
            FROM historical_energy
            WHERE created_at >= NOW() - INTERVAL '1 hour'
            ORDER BY timestamp DESC
        """
        
        df = pg_hook.get_pandas_df(sql=query)
        
        if df.empty:
            logger.info("No hay registros nuevos para validar")
            return {'status': 'no_new_records'}
        
        logger.info(f"✓ Validando {len(df)} registros nuevos")
        
        # Validaciones
        issues = []
        
        # 1. Valores nulos
        null_counts = df.isnull().sum()
        if null_counts.any():
            issues.append(f"Valores nulos detectados: {null_counts[null_counts > 0].to_dict()}")
        
        # 2. Rangos anómalos
        if (df['ENERGY'] < 0).any():
            issues.append("Valores negativos en ENERGY")
        
        if (df['RH2M'] > 100).any() or (df['RH2M'] < 0).any():
            issues.append("Humedad fuera de rango [0, 100]")
        
        # 3. Outliers (usando IQR)
        Q1 = df['ENERGY'].quantile(0.25)
        Q3 = df['ENERGY'].quantile(0.75)
        IQR = Q3 - Q1
        outliers = df[(df['ENERGY'] < Q1 - 1.5*IQR) | (df['ENERGY'] > Q3 + 1.5*IQR)]
        
        if not outliers.empty:
            issues.append(f"Se detectaron {len(outliers)} outliers en ENERGY")
        
        return {
            'n_records': len(df),
            'validation_issues': issues,
            'has_issues': len(issues) > 0,
            'outliers_count': len(outliers)
        }
    
    @task(task_id='check_retraining_need')
    def check_retraining_need(**context) -> Dict[str, Any]:
        """
        Verifica si es necesario reentrenar el modelo.
        """
        logger.info("="*60)
        logger.info("🤔 EVALUANDO NECESIDAD DE REENTRENAMIENTO")
        logger.info("="*60)
        
        pg_hook = PostgresHook(postgres_conn_id='postgres_energy')
        
        # Contar registros desde el último entrenamiento
        query = """
            SELECT COUNT(*) as new_records
            FROM historical_energy
            WHERE created_at > COALESCE(
                (SELECT MAX(training_date) FROM model_training_history),
                '2020-01-01'
            )
        """
        
        result = pg_hook.get_first(sql=query)
        new_records = result[0] if result else 0
        
        should_retrain = new_records >= 100
        
        logger.info(f"Registros nuevos: {new_records}")
        logger.info(f"Reentrenamiento necesario: {should_retrain}")
        
        return {
            'new_records': new_records,
            'should_retrain': should_retrain,
            'threshold': 100
        }
    
    # Flujo
    validation = validate_new_records()
    retraining_check = check_retraining_need()
    
    validation >> retraining_check


ingestion_dag = ingestion_validator_agent()