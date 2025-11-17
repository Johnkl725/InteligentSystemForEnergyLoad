"""
DAG para cargar datos históricos en la tabla historical_energy
Este DAG se ejecuta una sola vez (run_once) para poblar la base de datos
con los datos históricos procesados desde building_energy_data.csv
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
import logging

# Configuración del logger
logger = logging.getLogger(__name__)

# Argumentos por defecto del DAG
default_args = {
    'owner': 'energy_forecast_agent',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}


def load_historical_data(**context):
    """
    Lee el archivo SQL generado por csv_to_sql.py y ejecuta los INSERT
    en la tabla historical_energy de PostgreSQL
    """
    import os
    
    # Path al archivo SQL generado (está en el mismo directorio que los DAGs)
    sql_file_path = '/opt/airflow/dags/data_insert_20251116_162237.sql'
    
    logger.info(f"Iniciando carga de datos históricos desde: {sql_file_path}")
    
    # Verificar que el archivo existe
    if not os.path.exists(sql_file_path):
        raise FileNotFoundError(f"Archivo SQL no encontrado: {sql_file_path}")
    
    logger.info(f"✓ Archivo encontrado: {sql_file_path}")
    
    # Leer el contenido del archivo SQL
    with open(sql_file_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    logger.info(f"Archivo SQL leído: {len(sql_content)} caracteres")
    
    # Conectar a PostgreSQL usando el hook de Airflow
    postgres_hook = PostgresHook(postgres_conn_id='postgres_energy')
    
    try:
        # Ejecutar el INSERT en batch
        # Nota: Para archivos muy grandes, considera dividir en chunks
        logger.info("Ejecutando INSERT en base de datos...")
        
        # Ejecutar el SQL completo
        postgres_hook.run(sql_content)
        
        # Verificar cantidad de registros insertados
        count_query = "SELECT COUNT(*) FROM historical_energy;"
        records = postgres_hook.get_first(count_query)
        total_records = records[0] if records else 0
        
        logger.info(f"✅ Carga completada exitosamente: {total_records} registros en historical_energy")
        
        # Verificar rango de fechas
        date_range_query = """
        SELECT 
            MIN(timestamp) as min_date,
            MAX(timestamp) as max_date,
            COUNT(*) as total
        FROM historical_energy;
        """
        date_info = postgres_hook.get_first(date_range_query)
        
        if date_info:
            logger.info(f"Rango de datos: {date_info[0]} a {date_info[1]}")
            logger.info(f"Total de registros: {date_info[2]}")
        
        # Guardar metadata en XCom para siguientes tareas
        context['ti'].xcom_push(key='total_records', value=total_records)
        context['ti'].xcom_push(key='min_date', value=str(date_info[0]) if date_info else None)
        context['ti'].xcom_push(key='max_date', value=str(date_info[1]) if date_info else None)
        
        return {
            'status': 'success',
            'total_records': total_records,
            'min_date': str(date_info[0]) if date_info else None,
            'max_date': str(date_info[1]) if date_info else None
        }
        
    except Exception as e:
        logger.error(f"❌ Error durante la carga de datos: {str(e)}")
        raise

def log_completion(**context):
    """
    Registra la finalización exitosa en la tabla agent_logs
    """
    postgres_hook = PostgresHook(postgres_conn_id='postgres_energy')
    
    # Obtener metadata de tareas anteriores
    ti = context['ti']
    total_records = ti.xcom_pull(task_ids='load_historical_data', key='total_records')
    min_date = ti.xcom_pull(task_ids='load_historical_data', key='min_date')
    max_date = ti.xcom_pull(task_ids='load_historical_data', key='max_date')
    
    log_message = f"Datos históricos cargados: {total_records} registros desde {min_date} hasta {max_date}"
    
    insert_log = f"""
    INSERT INTO agent_logs (log_timestamp, agent_phase, status, message)
    VALUES (NOW(), 'DATA_LOAD', 'SUCCESS', '{log_message}');
    """
    
    postgres_hook.run(insert_log)
    logger.info(f"✅ Log registrado: {log_message}")
    
    return {'status': 'logged', 'message': log_message}


# Definición del DAG
with DAG(
    dag_id='load_historical_data',
    default_args=default_args,
    description='Carga única de datos históricos (2016-2020) en historical_energy',
    schedule_interval=None,  # Manual trigger only (run once)
    start_date=datetime(2025, 11, 16),
    catchup=False,
    tags=['data-load', 'historical', 'one-time'],
) as dag:
    
    # Tarea 1: Cargar datos desde SQL file
    load_data_task = PythonOperator(
        task_id='load_historical_data',
        python_callable=load_historical_data,
        provide_context=True,
        doc_md="""
        ### Cargar Datos Históricos
        Lee el archivo `data_insert_20251116_162237.sql` y ejecuta los INSERT
        en la tabla `historical_energy`.
        
        **Entrada:** Archivo SQL con ~43,800 registros (2016-2020)
        **Salida:** Datos cargados en PostgreSQL
        """
    )
    
    # Tarea 3: Registrar completación en agent_logs
    log_task = PythonOperator(
        task_id='log_completion',
        python_callable=log_completion,
        provide_context=True,
        doc_md="""
        ### Registrar Completación
        Guarda un log en la tabla `agent_logs` confirmando la carga exitosa.
        """
    )
    
    # Definir dependencias (pipeline lineal)
    load_data_task >> log_task
