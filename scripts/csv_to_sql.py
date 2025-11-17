"""
Script para convertir CSV a SQL pasando por Parquet y aplicando Feature Engineering.

Este script:
1. Lee el CSV building_energy_data.csv (2016-2020)
2. Aplica feature engineering para generar las 17 features que espera el modelo
3. Guarda como Parquet (backup intermedio)
4. Genera el archivo SQL con INSERT INTO historical_energy

Las 17 features finales son:
- Climáticas (4): PRECTOT, RH2M, T2M, ALLSKY
- Calendáricas (2): HOLIDAY, IsWeekend
- Cíclicas (6): Hour_sin, Hour_cos, Month_sin, Month_cos, DayOfWeek_sin, DayOfWeek_cos
- Derivadas (1): Temp_Range
- Lags (4): ENERGY_lag1, ENERGY_lag24, ENERGY_rolling_mean_24, ENERGY_rolling_std_24

Uso:
    python scripts/csv_to_sql.py
"""

import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import sys

def apply_feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica feature engineering al DataFrame para generar las 17 features.
    
    Args:
        df: DataFrame con columnas DATE, ENERGY, y columnas climáticas del CSV
    
    Returns:
        DataFrame con las 17 features procesadas
    """
    print("\n" + "="*70)
    print("APLICANDO FEATURE ENGINEERING")
    print("="*70)
    
    # 1. Parsear fecha
    print("\n1. Procesando timestamps...")
    df['DATE'] = pd.to_datetime(df['DATE'])
    df = df.sort_values('DATE').reset_index(drop=True)
    print(f"   ✓ Rango: {df['DATE'].min()} a {df['DATE'].max()}")
    print(f"   ✓ Total: {len(df)} registros")
    
    # 2. Extraer componentes temporales
    print("\n2. Extrayendo componentes temporales...")
    df['hour'] = df['DATE'].dt.hour
    df['month'] = df['DATE'].dt.month
    df['dayofweek'] = df['DATE'].dt.dayofweek
    df['date_only'] = df['DATE'].dt.date
    
    # 3. Features cíclicas (6)
    print("\n3. Creando features cíclicas...")
    df['Hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
    df['Hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
    df['Month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
    df['Month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
    df['DayOfWeek_sin'] = np.sin(2 * np.pi * df['dayofweek'] / 7)
    df['DayOfWeek_cos'] = np.cos(2 * np.pi * df['dayofweek'] / 7)
    print("   ✓ Hour_sin, Hour_cos, Month_sin, Month_cos, DayOfWeek_sin, DayOfWeek_cos")
    
    # 4. Features calendáricas (2)
    print("\n4. Creando features calendáricas...")
    # IsWeekend
    df['IsWeekend'] = (df['dayofweek'].isin([5, 6])).astype(int)
    
    # HOLIDAY - Ya existe en el CSV, solo verificar
    if 'HOLIDAY' not in df.columns:
        print("   ⚠ Columna HOLIDAY no encontrada, creando con valor 0")
        df['HOLIDAY'] = 0
    
    print(f"   ✓ IsWeekend: {df['IsWeekend'].sum()} registros de fin de semana")
    print(f"   ✓ HOLIDAY: {df['HOLIDAY'].sum()} registros de días festivos")
    
    # 5. Features climáticas (4) - Ya existen en el CSV
    print("\n5. Verificando features climáticas...")
    climate_features = ['PRECTOT', 'RH2M', 'T2M']
    
    # Mapear ALLSKY_SFC_SW_DWN a ALLSKY si existe
    if 'ALLSKY_SFC_SW_DWN' in df.columns:
        df['ALLSKY'] = df['ALLSKY_SFC_SW_DWN']
    elif 'ALLSKY' not in df.columns:
        print("   ⚠ Columna ALLSKY no encontrada")
        df['ALLSKY'] = 0
    
    for feat in climate_features:
        if feat not in df.columns:
            print(f"   ⚠ Columna {feat} no encontrada, creando con valor 0")
            df[feat] = 0
        else:
            print(f"   ✓ {feat}: rango [{df[feat].min():.2f}, {df[feat].max():.2f}]")
    
    print(f"   ✓ ALLSKY: rango [{df['ALLSKY'].min():.2f}, {df['ALLSKY'].max():.2f}]")
    
    # 6. Features derivadas (1)
    print("\n6. Creando features derivadas...")
    if 'T2M_MAX' in df.columns and 'T2M_MIN' in df.columns:
        df['Temp_Range'] = df['T2M_MAX'] - df['T2M_MIN']
    else:
        # Calcular rango diario aproximado
        daily_range = df.groupby('date_only')['T2M'].agg(['min', 'max'])
        daily_range['Temp_Range'] = daily_range['max'] - daily_range['min']
        df = df.merge(daily_range[['Temp_Range']], left_on='date_only', right_index=True, how='left')
        df['Temp_Range'] = df['Temp_Range'].fillna(10.0)  # Default si falla
    
    print(f"   ✓ Temp_Range: rango [{df['Temp_Range'].min():.2f}, {df['Temp_Range'].max():.2f}]")
    
    # 7. Features de lag y ventana (4)
    print("\n7. Creando features de lag y ventana temporal...")
    df = df.sort_values('DATE').reset_index(drop=True)
    
    # ENERGY_lag1: valor de hace 1 hora
    df['ENERGY_lag1'] = df['ENERGY'].shift(1)
    
    # ENERGY_lag24: valor de hace 24 horas
    df['ENERGY_lag24'] = df['ENERGY'].shift(24)
    
    # ENERGY_rolling_mean_24: promedio móvil últimas 24 horas
    df['ENERGY_rolling_mean_24'] = df['ENERGY'].rolling(window=24, min_periods=1).mean()
    
    # ENERGY_rolling_std_24: desviación estándar móvil últimas 24 horas
    df['ENERGY_rolling_std_24'] = df['ENERGY'].rolling(window=24, min_periods=1).std()
    
    # Rellenar NaN en las primeras filas (donde no hay suficiente historia)
    df['ENERGY_lag1'] = df['ENERGY_lag1'].fillna(df['ENERGY'].mean())
    df['ENERGY_lag24'] = df['ENERGY_lag24'].fillna(df['ENERGY'].mean())
    df['ENERGY_rolling_std_24'] = df['ENERGY_rolling_std_24'].fillna(0)
    
    print("   ✓ ENERGY_lag1, ENERGY_lag24, ENERGY_rolling_mean_24, ENERGY_rolling_std_24")
    print(f"     Lag1: [{df['ENERGY_lag1'].min():.2f}, {df['ENERGY_lag1'].max():.2f}]")
    print(f"     Lag24: [{df['ENERGY_lag24'].min():.2f}, {df['ENERGY_lag24'].max():.2f}]")
    
    # 8. Seleccionar solo las columnas finales
    final_columns = [
        'DATE', 'ENERGY',
        'PRECTOT', 'RH2M', 'T2M', 'ALLSKY',
        'HOLIDAY', 'IsWeekend',
        'Hour_sin', 'Hour_cos', 'Month_sin', 'Month_cos',
        'DayOfWeek_sin', 'DayOfWeek_cos',
        'Temp_Range',
        'ENERGY_lag1', 'ENERGY_lag24',
        'ENERGY_rolling_mean_24', 'ENERGY_rolling_std_24'
    ]
    
    df_final = df[final_columns].copy()
    
    print("\n" + "="*70)
    print("✓ FEATURE ENGINEERING COMPLETADO")
    print("="*70)
    print(f"Dataset final: {df_final.shape[0]} filas × {df_final.shape[1]} columnas")
    print(f"Columnas: {df_final.columns.tolist()}")
    
    return df_final


def csv_to_parquet_to_sql(csv_path: str, max_rows: int = None):
    """
    Pipeline completo: CSV → Feature Engineering → Parquet → SQL
    
    Args:
        csv_path: Ruta al archivo CSV
        max_rows: Número máximo de filas a procesar (None = todas)
    """
    print("="*70)
    print("CONVERTIDOR CSV → PARQUET → SQL")
    print("="*70)
    
    # 1. Leer CSV
    print(f"\n[1/4] Leyendo archivo CSV: {csv_path}")
    try:
        df = pd.read_csv(csv_path)
        print(f"   ✓ Archivo cargado: {df.shape[0]} filas, {df.shape[1]} columnas")
        print(f"   ✓ Columnas: {df.columns.tolist()}")
    except Exception as e:
        print(f"   ✗ Error al leer CSV: {e}")
        return
    
    # Limitar filas si se especificó
    if max_rows and max_rows < len(df):
        print(f"\n   Limitando a {max_rows} filas (de {len(df)})")
        df = df.head(max_rows)
    
    # 2. Aplicar feature engineering
    print(f"\n[2/4] Aplicando feature engineering...")
    try:
        df_processed = apply_feature_engineering(df)
    except Exception as e:
        print(f"\n   ✗ Error en feature engineering: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 3. Guardar como Parquet
    parquet_file = 'data_processed.parquet'
    print(f"\n[3/4] Guardando como Parquet: {parquet_file}")
    try:
        df_processed.to_parquet(parquet_file, index=False)
        print(f"   ✓ Archivo Parquet guardado exitosamente")
    except Exception as e:
        print(f"   ✗ Error al guardar Parquet: {e}")
        return
    
    # 4. Generar SQL INSERT
    sql_file = f'data_insert_{datetime.now().strftime("%Y%m%d_%H%M%S")}.sql'
    print(f"\n[4/4] Generando archivo SQL: {sql_file}")
    
    try:
        with open(sql_file, 'w', encoding='utf-8') as f:
            # Header
            f.write("-- ============================================================================\n")
            f.write("-- INSERT DE DATOS HISTÓRICOS (2016-2020)\n")
            f.write(f"-- Generado desde: {csv_path}\n")
            f.write(f"-- Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"-- Registros: {len(df_processed)}\n")
            f.write("-- ============================================================================\n\n")
            
            # Columnas para INSERT
            insert_columns = [
                'timestamp', 'ENERGY', 'PRECTOT', 'RH2M', 'T2M', 'ALLSKY', 
                'HOLIDAY', 'IsWeekend',
                'Hour_sin', 'Hour_cos', 'Month_sin', 'Month_cos', 
                'DayOfWeek_sin', 'DayOfWeek_cos', 'Temp_Range',
                'ENERGY_lag1', 'ENERGY_lag24', 
                'ENERGY_rolling_mean_24', 'ENERGY_rolling_std_24'
            ]
            
            f.write("INSERT INTO historical_energy (\n")
            f.write("    " + ", ".join(insert_columns) + "\n")
            f.write(")\nVALUES\n")
            
            # Generar cada fila
            total_rows = len(df_processed)
            for idx, row in df_processed.iterrows():
                # Timestamp
                ts = row['DATE'].strftime('%Y-%m-%d %H:%M:%S')
                
                # Valores
                values = [f"'{ts}'"]
                values.append(f"{row['ENERGY']:.2f}")
                values.append(f"{row['PRECTOT']:.4f}")
                values.append(f"{row['RH2M']:.2f}")
                values.append(f"{row['T2M']:.2f}")
                values.append(f"{row['ALLSKY']:.2f}")
                values.append(str(int(row['HOLIDAY'])))
                values.append(str(int(row['IsWeekend'])))
                values.append(f"{row['Hour_sin']:.6f}")
                values.append(f"{row['Hour_cos']:.6f}")
                values.append(f"{row['Month_sin']:.6f}")
                values.append(f"{row['Month_cos']:.6f}")
                values.append(f"{row['DayOfWeek_sin']:.6f}")
                values.append(f"{row['DayOfWeek_cos']:.6f}")
                values.append(f"{row['Temp_Range']:.2f}")
                values.append(f"{row['ENERGY_lag1']:.2f}")
                values.append(f"{row['ENERGY_lag24']:.2f}")
                values.append(f"{row['ENERGY_rolling_mean_24']:.2f}")
                values.append(f"{row['ENERGY_rolling_std_24']:.2f}")
                
                # Escribir la fila
                line = f"    ({', '.join(values)})"
                
                # Añadir coma o punto y coma
                if idx < total_rows - 1:
                    line += ","
                else:
                    line += ";"
                
                f.write(line + "\n")
                
                # Progreso cada 1000 filas
                if (idx + 1) % 1000 == 0:
                    print(f"   Procesadas {idx + 1}/{total_rows} filas...")
            
            # Footer
            f.write("\n-- ============================================================================\n")
            f.write(f"-- Total de registros insertados: {len(df_processed)}\n")
            f.write("-- Para evitar duplicados al re-ejecutar, añade al final:\n")
            f.write("-- ON CONFLICT (timestamp) DO NOTHING;\n")
            f.write("-- ============================================================================\n")
        
        print(f"   ✓ Archivo SQL generado exitosamente")
        
    except Exception as e:
        print(f"   ✗ Error al generar SQL: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Resumen final
    print("\n" + "="*70)
    print("✓ PROCESO COMPLETADO EXITOSAMENTE")
    print("="*70)
    print(f"\nArchivos generados:")
    print(f"1. {parquet_file} - Backup con features procesadas")
    print(f"2. {sql_file} - INSERT SQL para PostgreSQL")
    print(f"\nDatos procesados:")
    print(f"- Registros: {len(df_processed)}")
    print(f"- Rango temporal: {df_processed['DATE'].min()} a {df_processed['DATE'].max()}")
    print(f"- Features: 17 (las que espera el modelo)")
    print(f"\n📋 PRÓXIMOS PASOS:")
    print(f"1. Revisa el archivo: {sql_file}")
    print(f"2. Copia su contenido a sql/init.sql (reemplaza el INSERT de ejemplo)")
    print(f"3. Reinicia Docker: docker-compose down -v && docker-compose up -d")
    print("="*70)


if __name__ == '__main__':
    # Buscar archivos CSV
    csv_files = list(Path('.').glob('*.csv'))
    
    if not csv_files:
        print("❌ No se encontró ningún archivo .csv en el directorio actual")
        print("\nBuscando en directorios padre...")
        csv_files = list(Path('..').glob('*.csv'))
        
        if not csv_files:
            print("❌ Tampoco se encontraron archivos .csv en el directorio padre")
            sys.exit(1)
    
    # Si hay múltiples, mostrar opciones
    if len(csv_files) > 1:
        print(f"\n📁 Se encontraron {len(csv_files)} archivos .csv:")
        for i, f in enumerate(csv_files, 1):
            print(f"   {i}. {f.name}")
        
        choice = input("\nSelecciona el archivo (número): ")
        try:
            csv_path = str(csv_files[int(choice) - 1])
        except (ValueError, IndexError):
            print("❌ Selección inválida")
            sys.exit(1)
    else:
        csv_path = str(csv_files[0])
    
    print(f"\n✓ Usando archivo: {csv_path}")
    
    # Preguntar cuántas filas procesar
    print(f"\n¿Cuántas filas quieres procesar?")
    print(f"  - Presiona ENTER para TODAS las filas")
    print(f"  - O escribe un número (ej: 168 = 7 días, 8760 = 1 año)")
    
    max_rows_input = input("\nNúmero de filas: ").strip()
    max_rows = int(max_rows_input) if max_rows_input else None
    
    # Ejecutar pipeline
    csv_to_parquet_to_sql(csv_path, max_rows)
