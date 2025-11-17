"""
Script de Análisis del Notebook PipelineEnergy.ipynb

Este script ayuda a extraer y analizar la lógica de feature engineering
del notebook original para validar la implementación.

Úsalo para:
1. Comparar las features generadas con las del notebook
2. Verificar que la implementación en feature_engineering.py sea correcta
3. Debuggear problemas de inconsistencia
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Agregar el directorio de utils al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'dags', 'utils'))

from feature_engineering import FeatureEngineer, create_future_timestamps, validate_historical_energy


def analyze_notebook_features(notebook_path: str):
    """
    Analiza el notebook PipelineEnergy.ipynb para extraer información
    sobre las features utilizadas.
    
    Args:
        notebook_path: Ruta al notebook PipelineEnergy.ipynb
    """
    print("="*70)
    print("ANÁLISIS DEL NOTEBOOK PipelineEnergy.ipynb")
    print("="*70)
    
    try:
        import nbformat
        from nbformat import read
        
        # Leer el notebook
        with open(notebook_path, 'r', encoding='utf-8') as f:
            nb = read(f, as_version=4)
        
        print(f"\n✓ Notebook cargado: {len(nb.cells)} celdas")
        
        # Buscar celdas que mencionen feature engineering
        relevant_cells = []
        
        for i, cell in enumerate(nb.cells):
            if cell.cell_type == 'code':
                source = cell.source.lower()
                
                # Buscar keywords relacionadas con feature engineering
                keywords = [
                    'feature', 'lag', 'rolling', 'sin', 'cos', 
                    'holiday', 'weekend', 'temp_range', 'cyclic'
                ]
                
                if any(keyword in source for keyword in keywords):
                    relevant_cells.append((i, cell))
        
        print(f"✓ Celdas relevantes encontradas: {len(relevant_cells)}")
        
        # Imprimir celdas relevantes
        for idx, (cell_num, cell) in enumerate(relevant_cells[:10]):  # Limitar a 10
            print(f"\n--- Celda {cell_num} ---")
            print(cell.source[:500])  # Primeros 500 caracteres
            print("...")
        
        print("\n" + "="*70)
        print("RECOMENDACIONES:")
        print("="*70)
        print("1. Revisa las celdas anteriores para entender la lógica")
        print("2. Compara con feature_engineering.py")
        print("3. Verifica que todas las transformaciones estén implementadas")
        
    except ImportError:
        print("❌ Error: Instalar nbformat con: pip install nbformat")
    except FileNotFoundError:
        print(f"❌ Error: Notebook no encontrado en {notebook_path}")
    except Exception as e:
        print(f"❌ Error al analizar notebook: {e}")


def test_feature_engineering():
    """
    Test completo del módulo de feature engineering.
    """
    print("\n" + "="*70)
    print("TEST DE FEATURE ENGINEERING")
    print("="*70)
    
    # 1. Crear datos de prueba
    print("\n1. Creando datos de prueba...")
    
    future_timestamps = create_future_timestamps(
        start_time=datetime.now() + timedelta(hours=1),
        hours=24
    )
    
    # Datos climáticos simulados
    weather_forecast = pd.DataFrame({
        'PRECTOT': np.random.uniform(0, 5, 24),
        'RH2M': np.random.uniform(40, 80, 24),
        'T2M': np.random.uniform(15, 30, 24),
        'ALLSKY_SFC_SW_DWN': np.random.uniform(200, 600, 24),
        'T2M_max': np.random.uniform(25, 35, 24),
        'T2M_min': np.random.uniform(10, 20, 24)
    }, index=future_timestamps)
    
    # Datos históricos simulados
    historical_timestamps = pd.date_range(
        end=datetime.now(),
        periods=48,
        freq='H'
    )
    historical_energy = pd.Series(
        4500 + 1500 * np.sin(historical_timestamps.hour * 2 * np.pi / 24) + np.random.normal(0, 200, 48),
        index=historical_timestamps
    )
    
    print(f"   ✓ Timestamps futuros: {len(future_timestamps)}")
    print(f"   ✓ Pronóstico climático: {weather_forecast.shape}")
    print(f"   ✓ Datos históricos: {len(historical_energy)}")
    
    # 2. Validar datos históricos
    print("\n2. Validando datos históricos...")
    is_valid = validate_historical_energy(historical_energy, required_lookback=48)
    print(f"   {'✓' if is_valid else '❌'} Validación: {'OK' if is_valid else 'FALLO'}")
    
    if not is_valid:
        return
    
    # 3. Procesar features
    print("\n3. Procesando features...")
    engineer = FeatureEngineer()
    
    try:
        features_df = engineer.process_features(
            future_timestamps=future_timestamps,
            weather_forecast=weather_forecast,
            historical_energy=historical_energy
        )
        
        print(f"   ✓ Features generadas exitosamente")
        print(f"   ✓ Shape: {features_df.shape}")
        print(f"   ✓ Columnas: {features_df.columns.tolist()}")
        
        # 4. Validar features
        print("\n4. Validando features generadas...")
        
        expected_features = [
            'PRECTOT', 'RH2M', 'T2M', 'ALLSKY_SFC_SW_DWN',
            'HOLIDAY', 'IsWeekend',
            'Hour_sin', 'Hour_cos', 'Month_sin', 'Month_cos',
            'DayOfWeek_sin', 'DayOfWeek_cos',
            'Temp_Range',
            'ENERGY_lag1', 'ENERGY_lag24',
            'ENERGY_rolling_mean_24', 'ENERGY_rolling_std_24'
        ]
        
        missing = set(expected_features) - set(features_df.columns)
        extra = set(features_df.columns) - set(expected_features)
        
        if missing:
            print(f"   ❌ Features faltantes: {missing}")
        else:
            print(f"   ✓ Todas las features esperadas están presentes")
        
        if extra:
            print(f"   ⚠ Features extra: {extra}")
        
        # 5. Verificar rangos
        print("\n5. Verificando rangos de valores...")
        
        checks = [
            ('Hour_sin', -1, 1),
            ('Hour_cos', -1, 1),
            ('Month_sin', -1, 1),
            ('Month_cos', -1, 1),
            ('DayOfWeek_sin', -1, 1),
            ('DayOfWeek_cos', -1, 1),
            ('HOLIDAY', 0, 1),
            ('IsWeekend', 0, 1),
        ]
        
        for feature, min_val, max_val in checks:
            actual_min = features_df[feature].min()
            actual_max = features_df[feature].max()
            
            if actual_min < min_val or actual_max > max_val:
                print(f"   ❌ {feature}: rango [{actual_min:.3f}, {actual_max:.3f}] "
                      f"fuera de [{min_val}, {max_val}]")
            else:
                print(f"   ✓ {feature}: rango OK [{actual_min:.3f}, {actual_max:.3f}]")
        
        # 6. Mostrar estadísticas
        print("\n6. Estadísticas de features:")
        print(features_df.describe())
        
        # 7. Verificar valores nulos
        print("\n7. Verificando valores nulos...")
        null_count = features_df.isnull().sum().sum()
        if null_count > 0:
            print(f"   ❌ Se encontraron {null_count} valores nulos:")
            print(features_df.isnull().sum()[features_df.isnull().sum() > 0])
        else:
            print(f"   ✓ No hay valores nulos")
        
        print("\n" + "="*70)
        print("✓ TEST COMPLETADO EXITOSAMENTE")
        print("="*70)
        
        return features_df
        
    except Exception as e:
        print(f"\n❌ ERROR durante el procesamiento:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def compare_with_model_features(features_pkl_path: str):
    """
    Compara las features generadas con las esperadas por el modelo.
    
    Args:
        features_pkl_path: Ruta al archivo features.pkl del modelo
    """
    print("\n" + "="*70)
    print("COMPARACIÓN CON FEATURES DEL MODELO")
    print("="*70)
    
    try:
        import pickle
        
        # Cargar features esperadas
        with open(features_pkl_path, 'rb') as f:
            expected_features = pickle.load(f)
        
        print(f"\n✓ Features del modelo cargadas: {len(expected_features)}")
        print(f"\nFeatures esperadas por el modelo:")
        for i, feat in enumerate(expected_features, 1):
            print(f"  {i:2d}. {feat}")
        
        # Comparar con FeatureEngineer
        engineer = FeatureEngineer()
        generated_features = engineer.feature_names
        
        print(f"\n✓ Features generadas por FeatureEngineer: {len(generated_features)}")
        
        # Verificar coincidencia
        if expected_features == generated_features:
            print("\n✅ MATCH PERFECTO: Las features coinciden exactamente")
        else:
            print("\n⚠ DIFERENCIAS ENCONTRADAS:")
            
            missing = set(expected_features) - set(generated_features)
            extra = set(generated_features) - set(expected_features)
            
            if missing:
                print(f"\n❌ Features faltantes en FeatureEngineer:")
                for feat in missing:
                    print(f"   - {feat}")
            
            if extra:
                print(f"\n❌ Features extra en FeatureEngineer:")
                for feat in extra:
                    print(f"   - {feat}")
            
            # Verificar orden
            if set(expected_features) == set(generated_features):
                print(f"\n⚠ Las features son las mismas pero en diferente orden")
                print(f"   Esto podría causar problemas. Verificar el orden.")
        
    except FileNotFoundError:
        print(f"❌ Error: Archivo no encontrado en {features_pkl_path}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    # Cambiar estas rutas según tu configuración
    NOTEBOOK_PATH = "../PipelineEnergy.ipynb"
    FEATURES_PKL_PATH = "../models/features.pkl"
    
    print("""
    ╔════════════════════════════════════════════════════════════════════╗
    ║  SCRIPT DE ANÁLISIS DE FEATURE ENGINEERING                         ║
    ║  Sistema de Pronóstico de Demanda Energética                       ║
    ╚════════════════════════════════════════════════════════════════════╝
    """)
    
    # 1. Test del módulo de feature engineering
    print("\n[1/3] EJECUTANDO TEST DE FEATURE ENGINEERING...")
    features_df = test_feature_engineering()
    
    # 2. Analizar notebook (opcional)
    print("\n[2/3] ANALIZANDO NOTEBOOK...")
    if os.path.exists(NOTEBOOK_PATH):
        analyze_notebook_features(NOTEBOOK_PATH)
    else:
        print(f"⚠ Notebook no encontrado en {NOTEBOOK_PATH}")
        print("  Puedes saltar este paso si no tienes el notebook disponible")
    
    # 3. Comparar con features del modelo
    print("\n[3/3] COMPARANDO CON FEATURES DEL MODELO...")
    if os.path.exists(FEATURES_PKL_PATH):
        compare_with_model_features(FEATURES_PKL_PATH)
    else:
        print(f"⚠ Archivo features.pkl no encontrado en {FEATURES_PKL_PATH}")
        print("  Coloca el archivo features.pkl en la carpeta models/ para ejecutar esta validación")
    
    print("\n" + "="*70)
    print("ANÁLISIS COMPLETADO")
    print("="*70)
    print("\nPróximos pasos:")
    print("1. Revisa los resultados anteriores")
    print("2. Si hay diferencias, ajusta feature_engineering.py")
    print("3. Coloca los archivos .pkl del modelo en models/")
    print("4. Ejecuta docker-compose up para deployar el sistema")
