"""
DAG de Airflow - Agente Racional para Pronóstico de Demanda Energética

Este DAG implementa el ciclo completo de Percepción-Acción del Agente:

CICLO DEL AGENTE:
1. PERCEPCIÓN (Sensores):
   - Percibir estado histórico de la base de datos
   - Percibir pronóstico climático de API externa
   
2. PROCESAMIENTO (Cerebro Interno):
   - Feature Engineering: Transformar datos crudos en las 17 features
   
3. DECISIÓN (Cerebro - Modelo ML):
   - Llamar a la API de FastAPI con el modelo XGBRegressor
   
4. ACCIÓN (Actuadores):
   - Almacenar el pronóstico en la base de datos
   - (Opcional) Generar alertas si hay anomalías

Schedule: Diariamente a las 5:00 AM
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any

import pandas as pd
import numpy as np
import requests
from airflow.decorators import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.models import Variable

# Importar el módulo de feature engineering
import sys
sys.path.insert(0, os.path.dirname(__file__))
from utils.feature_engineering import (
    FeatureEngineer, 
    create_future_timestamps,
    validate_historical_energy
)

# Configurar logging
logger = logging.getLogger(__name__)

# Configuración por defecto del DAG
default_args = {
    'owner': 'energy_forecast_agent',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}


@dag(
    dag_id='energy_forecast_daily',
    default_args=default_args,
    description='Agente Racional para Pronóstico Diario de Demanda Energética',
    schedule_interval='0 5 * * *',  # 5:00 AM todos los días
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['energy', 'forecasting', 'ml', 'agent'],
)
def energy_forecast_agent():
    """
    DAG principal que orquesta el Agente Racional.
    """
    
    @task(task_id='perceive_db_state')
    def perceive_database_state(**context) -> Dict[str, Any]:
        """
        SENSOR 1: Percibir el estado histórico de la base de datos.
        
        Este sensor consulta la base de datos PostgreSQL para obtener
        las últimas 48 horas de datos de carga energética.
        
        Esto es esencial para calcular las features de lag/ventana.
        
        Returns:
            Dict con los datos históricos de energía
        """
        logger.info("="*60)
        logger.info("SENSOR 1: PERCIBIENDO ESTADO DE LA BASE DE DATOS")
        logger.info("="*60)
        
        try:
            # Conectar a PostgreSQL usando el Hook de Airflow
            pg_hook = PostgresHook(postgres_conn_id='postgres_energy')
            
            # MODIFICADO: Como los datos históricos son 2016-2020, 
            # tomamos las últimas 48 horas disponibles en la BD
            # En producción, esto usaría datetime.now()
            
            # Query para obtener las últimas 48 horas de datos disponibles
            query = """
                SELECT 
                    timestamp,
                    energy
                FROM historical_energy
                WHERE energy IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 48
            """
            
            logger.info(f"Consultando últimas 48 horas de datos históricos disponibles")
            
            # Ejecutar query (sin parámetros ya que usamos LIMIT)
            df = pg_hook.get_pandas_df(sql=query)
            
            # Ordenar por timestamp ascendente (LIMIT trae DESC, necesitamos ASC para lag features)
            df = df.sort_values('timestamp', ascending=True).reset_index(drop=True)
            
            if df.empty:
                logger.error("❌ No se encontraron datos históricos en la base de datos")
                raise ValueError("Base de datos sin datos históricos")
            
            logger.info(f"✓ Datos históricos recuperados: {len(df)} registros")
            logger.info(f"  Rango: {df['timestamp'].min()} a {df['timestamp'].max()}")
            logger.info(f"  Energía promedio: {df['energy'].mean():.2f} MW")
            logger.info(f"  Energía min/max: [{df['energy'].min():.2f}, {df['energy'].max():.2f}] MW")
            
            # Convertir a diccionario para pasar entre tareas
            return {
                'timestamps': df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                'energy_values': df['energy'].tolist(),
                'n_records': len(df),
                'mean_energy': float(df['energy'].mean()),
                'perception_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error al percibir estado de la base de datos: {e}")
            raise
    
    @task(task_id='perceive_weather_forecast')
    def perceive_weather_forecast(**context) -> Dict[str, Any]:
        """
        SENSOR 2: Percibir el pronóstico climático de una API externa.
        
        Este sensor llama a la API de OpenWeatherMap (o similar) para obtener
        el pronóstico del clima para las próximas 24 horas.
        
        Returns:
            Dict con el pronóstico climático
        """
        logger.info("="*60)
        logger.info("SENSOR 2: PERCIBIENDO PRONÓSTICO CLIMÁTICO")
        logger.info("="*60)
        
        try:
            # Obtener API key desde las variables de Airflow
            api_key = Variable.get('WEATHER_API_KEY', default_var='your_api_key')
            
            # Coordenadas de la ubicación (ejemplo: Lima, Perú)
            # Estos valores deben ser configurados según la ubicación real
            lat = -12.0464
            lon = -77.0428
            
            # URL de la API (usando OpenWeatherMap como ejemplo)
            url = f"https://api.openweathermap.org/data/2.5/forecast"
            
            params = {
                'lat': lat,
                'lon': lon,
                'appid': api_key,
                'units': 'metric',  # Para obtener temperatura en Celsius
                'cnt': 24  # Próximas 24 horas
            }
            
            logger.info(f"Consultando API del clima para lat={lat}, lon={lon}")
            
            # Hacer la petición HTTP
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Parsear la respuesta
            weather_forecast = []
            
            for item in data.get('list', [])[:24]:  # Limitar a 24 horas
                timestamp = datetime.fromtimestamp(item['dt'])
                
                forecast_point = {
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'T2M': item['main']['temp'],  # Temperatura
                    'RH2M': item['main']['humidity'],  # Humedad
                    'PRECTOT': item.get('rain', {}).get('3h', 0) / 3,  # Precipitación por hora
                    'ALLSKY_SFC_SW_DWN': 500.0,  # Radiación solar (aproximado)
                    'T2M_max': item['main']['temp_max'],
                    'T2M_min': item['main']['temp_min']
                }
                
                weather_forecast.append(forecast_point)
            
            if not weather_forecast:
                logger.error("❌ No se obtuvo pronóstico climático de la API")
                raise ValueError("API del clima no devolvió datos")
            
            logger.info(f"✓ Pronóstico climático recuperado: {len(weather_forecast)} horas")
            logger.info(f"  Temperatura promedio: {np.mean([f['T2M'] for f in weather_forecast]):.2f}°C")
            logger.info(f"  Humedad promedio: {np.mean([f['RH2M'] for f in weather_forecast]):.2f}%")
            
            return {
                'forecast': weather_forecast,
                'n_hours': len(weather_forecast),
                'source': 'OpenWeatherMap',
                'perception_time': datetime.now().isoformat()
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error al consultar API del clima: {e}")
            
            # En caso de fallo, usar datos simulados (solo para desarrollo)
            logger.warning("⚠ Usando datos climáticos simulados (SOLO DESARROLLO)")
            
            future_timestamps = pd.date_range(
                start=datetime.now() + timedelta(hours=1),
                periods=24,
                freq='H'
            )
            
            weather_forecast = []
            for ts in future_timestamps:
                weather_forecast.append({
                    'timestamp': ts.strftime('%Y-%m-%d %H:%M:%S'),
                    'T2M': np.random.uniform(15, 30),
                    'RH2M': np.random.uniform(40, 80),
                    'PRECTOT': np.random.uniform(0, 5),
                    'ALLSKY_SFC_SW_DWN': np.random.uniform(200, 600),
                    'T2M_max': np.random.uniform(25, 35),
                    'T2M_min': np.random.uniform(10, 20)
                })
            
            return {
                'forecast': weather_forecast,
                'n_hours': len(weather_forecast),
                'source': 'SIMULATED',
                'perception_time': datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"❌ Error inesperado al percibir pronóstico climático: {e}")
            raise
    
    @task(task_id='feature_engineering')
    def feature_engineering(
        db_state: Dict[str, Any],
        weather_forecast: Dict[str, Any],
        **context
    ) -> Dict[str, Any]:
        """
        PROCESAMIENTO INTERNO: Ingeniería de Features.
        
        Esta es la tarea MÁS CRÍTICA del DAG. Aquí se transforman los datos
        crudos percibidos por los sensores en las 17 features que el modelo espera.
        
        Args:
            db_state: Datos históricos de energía (de perceive_db_state)
            weather_forecast: Pronóstico climático (de perceive_weather_forecast)
        
        Returns:
            Dict con las features procesadas listas para predicción
        """
        logger.info("="*60)
        logger.info("PROCESAMIENTO: FEATURE ENGINEERING")
        logger.info("="*60)
        
        try:
            # 1. Reconstruir la serie temporal de energía histórica
            timestamps = pd.to_datetime(db_state['timestamps'])
            energy_values = db_state['energy_values']
            
            historical_energy = pd.Series(
                data=energy_values,
                index=timestamps,
                name='ENERGY'
            )
            
            logger.info(f"1. Serie histórica reconstruida: {len(historical_energy)} puntos")
            
            # 2. Validar datos históricos
            if not validate_historical_energy(historical_energy, required_lookback=48):
                raise ValueError("Datos históricos insuficientes o inválidos")
            
            # 3. Reconstruir el DataFrame de pronóstico climático
            weather_data = weather_forecast['forecast']
            weather_df = pd.DataFrame(weather_data)
            weather_df['timestamp'] = pd.to_datetime(weather_df['timestamp'])
            weather_df.set_index('timestamp', inplace=True)
            
            logger.info(f"2. Pronóstico climático reconstruido: {len(weather_df)} horas")
            
            # 4. Crear timestamps futuros
            future_timestamps = weather_df.index
            
            # 5. Instanciar el Feature Engineer
            engineer = FeatureEngineer()
            
            # 6. Procesar todas las features (LA MAGIA OCURRE AQUÍ)
            features_df = engineer.process_features(
                future_timestamps=future_timestamps,
                weather_forecast=weather_df,
                historical_energy=historical_energy
            )
            
            logger.info(f"3. Features procesadas: {features_df.shape}")
            logger.info(f"   Columnas: {features_df.columns.tolist()}")
            
            # 7. Convertir a formato JSON para pasar entre tareas
            features_dict = {
                'timestamps': features_df.index.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                'features': features_df.to_dict(orient='records'),
                'n_records': len(features_df),
                'feature_names': features_df.columns.tolist(),
                'processing_time': datetime.now().isoformat()
            }
            
            logger.info("✓ Feature engineering completado exitosamente")
            
            return features_dict
            
        except Exception as e:
            logger.error(f"❌ Error durante feature engineering: {e}")
            raise
    
    @task(task_id='predict')
    def predict(features_data: Dict[str, Any], **context) -> Dict[str, Any]:
        """
        DECISIÓN: Llamar al Cerebro del Agente (Modelo ML).
        
        Esta tarea llama al endpoint /predict de la API de FastAPI,
        que contiene el modelo XGBRegressor.
        
        Args:
            features_data: Features procesadas (de feature_engineering)
        
        Returns:
            Dict con las predicciones
        """
        logger.info("="*60)
        logger.info("DECISIÓN: CONSULTANDO CEREBRO DEL AGENTE (MODELO ML)")
        logger.info("="*60)
        
        try:
            # URL de la API (desde variables de entorno o conexión de Airflow)
            api_url = os.getenv('AIRFLOW_CONN_API_ENERGY', 'http://api:8000')
            if api_url.startswith('http://'):
                api_base = api_url
            else:
                api_base = 'http://api:8000'
            
            predict_url = f"{api_base}/predict"
            
            logger.info(f"Llamando a la API: {predict_url}")
            
            # Preparar el payload
            payload = {
                'features': features_data['features']
            }
            
            logger.info(f"Payload: {len(payload['features'])} registros de features")
            
            # Hacer la petición POST
            response = requests.post(
                predict_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=60
            )
            
            response.raise_for_status()
            
            # Parsear la respuesta
            result = response.json()
            
            predictions = result['predictions']
            
            logger.info(f"✓ Predicciones recibidas: {len(predictions)} valores")
            logger.info(f"  Rango: [{min(predictions):.2f}, {max(predictions):.2f}] MW")
            logger.info(f"  Promedio: {np.mean(predictions):.2f} MW")
            logger.info(f"  Versión del modelo: {result.get('model_version', 'unknown')}")
            
            return {
                'timestamps': features_data['timestamps'],
                'predictions': predictions,
                'n_predictions': len(predictions),
                'model_version': result.get('model_version', 'unknown'),
                'features_scaled': result.get('features_scaled', True),
                'prediction_time': datetime.now().isoformat()
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error al llamar a la API de predicción: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"  Respuesta: {e.response.text}")
            raise
        
        except Exception as e:
            logger.error(f"❌ Error inesperado durante la predicción: {e}")
            raise
    
    @task(task_id='act_store_forecast')
    def act_store_forecast(predictions_data: Dict[str, Any], **context) -> Dict[str, Any]:
        """
        ACTUADOR: Almacenar el pronóstico en la base de datos.
        
        Esta tarea inserta las predicciones en la tabla de pronósticos
        de la base de datos PostgreSQL.
        
        Args:
            predictions_data: Predicciones del modelo (de predict)
        
        Returns:
            Dict con el resultado de la acción
        """
        logger.info("="*60)
        logger.info("ACTUADOR: ALMACENANDO PRONÓSTICO EN BASE DE DATOS")
        logger.info("="*60)
        
        try:
            # Conectar a PostgreSQL
            pg_hook = PostgresHook(postgres_conn_id='postgres_energy')
            
            timestamps = pd.to_datetime(predictions_data['timestamps'])
            predictions = predictions_data['predictions']
            
            # Preparar datos para inserción
            records = []
            for ts, pred in zip(timestamps, predictions):
                records.append({
                    'forecast_timestamp': ts,
                    'predicted_energy_mw': pred,
                    'model_version': predictions_data['model_version'],
                    'created_at': datetime.now()
                })
            
            logger.info(f"Preparando para insertar {len(records)} registros")
            
            # Crear DataFrame
            df = pd.DataFrame(records)
            
            # Insertar en la base de datos
            # Nota: Esto sobrescribe pronósticos existentes para las mismas fechas
            insert_query = """
                INSERT INTO energy_forecasts 
                (forecast_timestamp, predicted_energy_mw, model_version, created_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (forecast_timestamp) 
                DO UPDATE SET 
                    predicted_energy_mw = EXCLUDED.predicted_energy_mw,
                    model_version = EXCLUDED.model_version,
                    created_at = EXCLUDED.created_at
            """
            
            # Insertar registros
            conn = pg_hook.get_conn()
            cursor = conn.cursor()
            
            for _, row in df.iterrows():
                cursor.execute(insert_query, (
                    row['forecast_timestamp'],
                    row['predicted_energy_mw'],
                    row['model_version'],
                    row['created_at']
                ))
            
            conn.commit()
            cursor.close()
            
            logger.info(f"✓ Pronóstico almacenado exitosamente: {len(records)} registros")
            logger.info(f"  Rango temporal: {timestamps.min()} a {timestamps.max()}")
            
            return {
                'status': 'success',
                'records_inserted': len(records),
                'timestamp_range': [
                    timestamps.min().isoformat(),
                    timestamps.max().isoformat()
                ],
                'action_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error al almacenar pronóstico: {e}")
            raise
    
    @task(task_id='monitor_quality')
    def monitor_forecast_quality(
        predictions_data: Dict[str, Any],
        store_result: Dict[str, Any],
        **context
    ) -> Dict[str, Any]:
        """
        MONITOREO (Opcional): Monitorear la calidad del pronóstico.
        
        Esta tarea verifica si el pronóstico generado tiene anomalías o
        valores fuera de rango esperado.
        
        En un sistema de producción, aquí se podría:
        - Comparar con pronósticos anteriores
        - Detectar drift en las predicciones
        - Generar alertas si hay valores anómalos
        """
        logger.info("="*60)
        logger.info("MONITOR: VERIFICANDO CALIDAD DEL PRONÓSTICO")
        logger.info("="*60)
        
        try:
            predictions = predictions_data['predictions']
            
            # Calcular estadísticas
            mean_pred = np.mean(predictions)
            std_pred = np.std(predictions)
            min_pred = np.min(predictions)
            max_pred = np.max(predictions)
            
            logger.info(f"Estadísticas del pronóstico:")
            logger.info(f"  Media: {mean_pred:.2f} MW")
            logger.info(f"  Desv. Estándar: {std_pred:.2f} MW")
            logger.info(f"  Mín/Máx: [{min_pred:.2f}, {max_pred:.2f}] MW")
            
            # Verificar rangos esperados (estos valores deben ser configurados)
            EXPECTED_MIN = 80  # MW
            EXPECTED_MAX = 200  # MW
            
            anomalies = []
            
            if min_pred < EXPECTED_MIN:
                anomalies.append(f"Predicción mínima muy baja: {min_pred:.2f} MW")
                logger.warning(f"⚠ {anomalies[-1]}")
            
            if max_pred > EXPECTED_MAX:
                anomalies.append(f"Predicción máxima muy alta: {max_pred:.2f} MW")
                logger.warning(f"⚠ {anomalies[-1]}")
            
            # Verificar variabilidad extrema
            if std_pred > mean_pred * 0.3:  # Desviación > 30% de la media
                anomalies.append(f"Alta variabilidad detectada: {std_pred:.2f} MW")
                logger.warning(f"⚠ {anomalies[-1]}")
            
            if anomalies:
                logger.warning(f"⚠ Se detectaron {len(anomalies)} anomalías")
                # Aquí se podría enviar una alerta por email o Slack
            else:
                logger.info("✓ Pronóstico dentro de rangos esperados")
            
            return {
                'status': 'monitored',
                'statistics': {
                    'mean': float(mean_pred),
                    'std': float(std_pred),
                    'min': float(min_pred),
                    'max': float(max_pred)
                },
                'anomalies': anomalies,
                'n_anomalies': len(anomalies),
                'quality_score': 1.0 if not anomalies else 0.5,
                'monitor_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error durante el monitoreo: {e}")
            # No fallar el DAG por errores de monitoreo
            return {
                'status': 'error',
                'error': str(e),
                'monitor_time': datetime.now().isoformat()
            }
    
    # =========================================================================
    # DEFINIR EL FLUJO DEL AGENTE (Ciclo Percepción-Acción)
    # =========================================================================
    
    # 1. PERCEPCIÓN: Los sensores perciben el entorno en paralelo
    db_state = perceive_database_state()
    weather = perceive_weather_forecast()
    
    # 2. PROCESAMIENTO: Feature engineering (requiere ambas percepciones)
    features = feature_engineering(db_state, weather)
    
    # 3. DECISIÓN: Llamar al cerebro del agente (modelo ML)
    predictions = predict(features)
    
    # 4. ACCIÓN: Almacenar el pronóstico en la base de datos
    store_result = act_store_forecast(predictions)
    
    # 5. MONITOREO: Verificar la calidad del pronóstico (opcional)
    monitor_result = monitor_forecast_quality(predictions, store_result)
    
    # Definir dependencias explícitas
    [db_state, weather] >> features >> predictions >> store_result >> monitor_result


# Instanciar el DAG
energy_forecast_dag = energy_forecast_agent()
