"""
DAG de Monitoreo Inteligente - Dashboard Agente

Este DAG analiza la performance del modelo de predicción y genera insights.

CICLO DEL AGENTE MONITOR:
1. PERCEPCIÓN: Leer predicciones vs realidad
2. ANÁLISIS: Calcular métricas de error (MAE, RMSE, MAPE)
3. APRENDIZAJE: Detectar patrones de error (por hora, día, condiciones)
4. RECOMENDACIÓN: Sugerir mejoras (reentrenamiento, ajuste de features)
5. ALERTA: Notificar si la performance se degrada

Schedule: Diariamente a las 6:00 AM (después del forecast_dag)
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
    'owner': 'dashboard_agent',
    'depends_on_past': False,
    'email_on_failure': True,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}


@dag(
    dag_id='monitor_dashboard_agent',
    default_args=default_args,
    description='Agente Inteligente de Monitoreo y Dashboard',
    schedule_interval='0 6 * * *',  # 6:00 AM (1 hora después del forecast)
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['monitoring', 'dashboard', 'ml-ops'],
)
def dashboard_monitoring_agent():
    
    @task(task_id='perceive_performance')
    def perceive_model_performance(**context) -> Dict[str, Any]:
        """
        PERCEPCIÓN: Leer métricas de performance del modelo.
        """
        logger.info("="*60)
        logger.info("🔍 PERCIBIENDO PERFORMANCE DEL MODELO")
        logger.info("="*60)
        
        pg_hook = PostgresHook(postgres_conn_id='postgres_energy')
        
        # Query para obtener métricas de los últimos 7 días
        query = """
            SELECT *
            FROM daily_forecast_metrics
            WHERE forecast_date >= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY forecast_date DESC
        """
        
        df_metrics = pg_hook.get_pandas_df(sql=query)
        
        logger.info(f"✓ Métricas recuperadas: {len(df_metrics)} días")
        logger.info(f"  MAE promedio: {df_metrics['mae'].mean():.2f} MW")
        logger.info(f"  RMSE promedio: {df_metrics['rmse'].mean():.2f} MW")
        logger.info(f"  MAPE promedio: {df_metrics['mape'].mean():.2f}%")
        
        return {
            'metrics': df_metrics.to_dict(orient='records'),
            'n_days': len(df_metrics),
            'avg_mae': float(df_metrics['mae'].mean()),
            'avg_rmse': float(df_metrics['rmse'].mean()),
            'avg_mape': float(df_metrics['mape'].mean()),
        }
    
    @task(task_id='analyze_error_patterns')
    def analyze_error_patterns(**context) -> Dict[str, Any]:
        """
        ANÁLISIS: Detectar patrones de error.
        """
        logger.info("="*60)
        logger.info("🧠 ANALIZANDO PATRONES DE ERROR")
        logger.info("="*60)
        
        pg_hook = PostgresHook(postgres_conn_id='postgres_energy')
        
        # Análisis 1: Error por hora del día
        query_by_hour = """
            SELECT 
                hour_of_day,
                COUNT(*) as n_predictions,
                AVG(absolute_error) as avg_error,
                AVG(percentage_error) as avg_pct_error
            FROM forecast_performance
            WHERE actual_energy_mw IS NOT NULL
              AND forecast_timestamp >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY hour_of_day
            ORDER BY hour_of_day
        """
        
        df_by_hour = pg_hook.get_pandas_df(sql=query_by_hour)
        
        # Detectar horas problemáticas (error > promedio + 1.5 * std)
        threshold = df_by_hour['avg_error'].mean() + 1.5 * df_by_hour['avg_error'].std()
        problematic_hours = df_by_hour[df_by_hour['avg_error'] > threshold]['hour_of_day'].tolist()
        
        logger.info(f"⚠ Horas con mayor error: {problematic_hours}")
        
        # Análisis 2: Error por día de la semana
        query_by_dow = """
            SELECT 
                day_of_week,
                COUNT(*) as n_predictions,
                AVG(absolute_error) as avg_error
            FROM forecast_performance
            WHERE actual_energy_mw IS NOT NULL
              AND forecast_timestamp >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY day_of_week
            ORDER BY day_of_week
        """
        
        df_by_dow = pg_hook.get_pandas_df(sql=query_by_dow)
        
        return {
            'error_by_hour': df_by_hour.to_dict(orient='records'),
            'error_by_day': df_by_dow.to_dict(orient='records'),
            'problematic_hours': problematic_hours,
        }
    
    @task(task_id='generate_recommendations')
    def generate_recommendations(
        performance: Dict[str, Any],
        patterns: Dict[str, Any],
        **context
    ) -> Dict[str, Any]:
        """
        RECOMENDACIÓN: Generar sugerencias de mejora.
        """
        logger.info("="*60)
        logger.info("💡 GENERANDO RECOMENDACIONES")
        logger.info("="*60)
        
        recommendations = []
        
        # Recomendación 1: Si MAPE > 15%, reentrenar modelo
        if performance['avg_mape'] > 15:
            recommendations.append({
                'priority': 'HIGH',
                'type': 'MODEL_RETRAINING',
                'message': f"MAPE alto ({performance['avg_mape']:.2f}%). Considerar reentrenar modelo.",
                'action': 'Ejecutar pipeline de reentrenamiento con datos recientes'
            })
        
        # Recomendación 2: Horas problemáticas
        if patterns['problematic_hours']:
            recommendations.append({
                'priority': 'MEDIUM',
                'type': 'FEATURE_ENGINEERING',
                'message': f"Mayor error en horas: {patterns['problematic_hours']}",
                'action': 'Añadir features específicas para estas horas (ej: picos de demanda)'
            })
        
        # Recomendación 3: Si MAE crece consistentemente
        metrics_df = pd.DataFrame(performance['metrics'])
        if len(metrics_df) >= 3:
            mae_trend = metrics_df['mae'].iloc[:3].is_monotonic_increasing
            if mae_trend:
                recommendations.append({
                    'priority': 'HIGH',
                    'type': 'MODEL_DRIFT',
                    'message': 'Degradación del modelo detectada (MAE creciente)',
                    'action': 'Investigar concept drift o cambios en los datos'
                })
        
        for rec in recommendations:
            logger.info(f"[{rec['priority']}] {rec['type']}: {rec['message']}")
        
        return {
            'recommendations': recommendations,
            'n_recommendations': len(recommendations),
            'timestamp': datetime.now().isoformat()
        }
    
    @task(task_id='store_monitoring_insights')
    def store_monitoring_insights(
        performance: Dict[str, Any],
        recommendations: Dict[str, Any],
        **context
    ) -> Dict[str, Any]:
        """
        ACTUADOR: Almacenar insights en BD para el dashboard.
        """
        logger.info("="*60)
        logger.info("💾 ALMACENANDO INSIGHTS DE MONITOREO")
        logger.info("="*60)
        
        pg_hook = PostgresHook(postgres_conn_id='postgres_energy')
        
        # Insertar recomendaciones en tabla de logs
        for rec in recommendations['recommendations']:
            insert_query = """
                INSERT INTO agent_logs 
                (agent_name, log_level, message, details, log_timestamp)
                VALUES (%s, %s, %s, %s, %s)
            """
            
            conn = pg_hook.get_conn()
            cursor = conn.cursor()
            
            cursor.execute(insert_query, (
                'dashboard_monitor',
                rec['priority'],
                rec['message'],
                rec['action'],
                datetime.now()
            ))
            
            conn.commit()
            cursor.close()
        
        logger.info(f"✓ {len(recommendations['recommendations'])} recomendaciones almacenadas")
        
        return {'status': 'success'}
    
    # Flujo del agente monitor
    perf = perceive_model_performance()
    patterns = analyze_error_patterns()
    recs = generate_recommendations(perf, patterns)
    store = store_monitoring_insights(perf, recs)
    
    perf >> patterns >> recs >> store


dashboard_agent = dashboard_monitoring_agent()