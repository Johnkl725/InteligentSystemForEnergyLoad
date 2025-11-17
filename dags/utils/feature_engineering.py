"""
Feature Engineering Module - Lógica de Transformación de Features

Este módulo contiene la lógica CRÍTICA para transformar datos crudos en las 17 features
que el modelo XGBRegressor espera.

Basado en el análisis del PipelineEnergy.ipynb, este módulo implementa:
1. Features Climáticas (PRECTOT, RH2M, T2M, ALLSKY)
2. Features Calendáricas (HOLIDAY, IsWeekend)
3. Features Cíclicas (Hour_sin, Hour_cos, Month_sin, Month_cos, DayOfWeek_sin, DayOfWeek_cos)
4. Features Derivadas (Temp_Range)
5. Features de Lag y Ventana (ENERGY_lag1, ENERGY_lag24, ENERGY_rolling_mean_24, ENERGY_rolling_std_24)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging

logger = logging.getLogger(__name__)


class FeatureEngineer:
    """
    Clase que encapsula toda la lógica de ingeniería de features.
    """
    
    # Definir días festivos de Perú (esto debe ser configurado según el país)
    HOLIDAYS = [
        # Formato: 'MM-DD'
        '01-01',  # Año Nuevo
        '04-14',  # Jueves Santo (variable)
        '04-15',  # Viernes Santo (variable)
        '05-01',  # Día del Trabajo
        '06-29',  # San Pedro y San Pablo
        '07-28',  # Fiestas Patrias
        '07-29',  # Fiestas Patrias
        '08-30',  # Santa Rosa de Lima
        '10-08',  # Combate de Angamos
        '11-01',  # Todos los Santos
        '12-08',  # Inmaculada Concepción
        '12-25',  # Navidad
    ]
    
    def __init__(self):
        """
        Inicializar el Feature Engineer.
        """
        self.feature_names = [
            'PRECTOT', 'RH2M', 'T2M', 'ALLSKY',
            'HOLIDAY', 'IsWeekend',
            'Hour_sin', 'Hour_cos', 'Month_sin', 'Month_cos',
            'DayOfWeek_sin', 'DayOfWeek_cos',
            'Temp_Range',
            'ENERGY_lag1', 'ENERGY_lag24',
            'ENERGY_rolling_mean_24', 'ENERGY_rolling_std_24'
        ]
    
    def create_cyclical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        f"""
        Crear features cíclicas usando codificación sin/cos.
        
        Esto transforma variables temporales lineales (hora, mes, día) en
        representaciones cíclicas que el modelo puede interpretar correctamente.
        
        Por ejemplo, la hora 23 está cerca de la hora 0, lo cual un modelo
        no entendería con representación lineal, pero sí con sin/cos.
        """
        df = df.copy()
        
        # Hour (0-23)
        df['Hour_sin'] = np.sin(2 * np.pi * df.index.hour / 24)
        df['Hour_cos'] = np.cos(2 * np.pi * df.index.hour / 24)
        
        # Month (1-12)
        df['Month_sin'] = np.sin(2 * np.pi * df.index.month / 12)
        df['Month_cos'] = np.cos(2 * np.pi * df.index.month / 12)
        
        # DayOfWeek (0-6, donde 0 es lunes)
        df['DayOfWeek_sin'] = np.sin(2 * np.pi * df.index.dayofweek / 7)
        df['DayOfWeek_cos'] = np.cos(2 * np.pi * df.index.dayofweek / 7)
        
        logger.info("✓ Features cíclicas creadas (Hour, Month, DayOfWeek)")
        
        return df
    
    def create_calendar_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Crear features basadas en calendario (días festivos, fin de semana).
        """
        df = df.copy()
        
        # IsWeekend: 1 si es sábado (5) o domingo (6), 0 en caso contrario
        df['IsWeekend'] = df.index.dayofweek.isin([5, 6]).astype(int)
        
        # HOLIDAY: 1 si la fecha está en la lista de festivos
        df['HOLIDAY'] = df.index.strftime('%m-%d').isin(self.HOLIDAYS).astype(int)
        
        logger.info(f"✓ Features calendáricas creadas")
        logger.info(f"  - Días de fin de semana: {df['IsWeekend'].sum()}")
        logger.info(f"  - Días festivos: {df['HOLIDAY'].sum()}")
        
        return df
    
    def create_weather_derived_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Crear features derivadas del clima.
        
        Temp_Range: Rango de temperatura (T2M_max - T2M_min) del día.
        Para pronóstico futuro, podemos usar una aproximación o valores históricos.
        """
        df = df.copy()
        
        # Para cada día, calcular el rango de temperatura
        # En pronóstico futuro, usaremos el rango esperado del pronóstico climático
        if 'T2M_max' in df.columns and 'T2M_min' in df.columns:
            df['Temp_Range'] = df['T2M_max'] - df['T2M_min']
        else:
            # Si no tenemos min/max, usar una aproximación basada en la hora
            # Asumimos que el rango diario promedio es ~10-15°C
            # Esta es una aproximación; idealmente el pronóstico debe incluir min/max
            df['Temp_Range'] = 10.0  # Valor por defecto
            logger.warning("⚠ Temp_Range usando valor por defecto (no hay T2M_max/T2M_min)")
        
        logger.info("✓ Features derivadas del clima creadas (Temp_Range)")
        
        return df
    
    def create_lag_features(
        self, 
        df: pd.DataFrame, 
        historical_energy: pd.Series
    ) -> pd.DataFrame:
        """
        Crear features de lag y ventana móvil.
        
        Esta es la parte MÁS CRÍTICA del feature engineering para series temporales.
        
        Args:
            df: DataFrame con índice temporal para el cual queremos crear features
            historical_energy: Serie con datos históricos de ENERGY (debe incluir
                              al menos las últimas 48 horas antes del primer timestamp en df)
        
        Returns:
            DataFrame con las features de lag añadidas
        """
        df = df.copy()
        
        # Combinar los datos históricos con el DataFrame de pronóstico
        # para poder calcular lags correctamente
        combined_energy = pd.concat([historical_energy, pd.Series(index=df.index, dtype=float)])
        combined_energy = combined_energy[~combined_energy.index.duplicated(keep='first')]
        combined_energy = combined_energy.sort_index()
        
        logger.info(f"Serie combinada: {len(combined_energy)} puntos temporales")
        logger.info(f"Rango: {combined_energy.index.min()} a {combined_energy.index.max()}")
        
        # ENERGY_lag1: Valor de energía del período anterior (1 hora atrás)
        df['ENERGY_lag1'] = combined_energy.shift(1).reindex(df.index)
        
        # ENERGY_lag24: Valor de energía de hace 24 horas (mismo hora del día anterior)
        df['ENERGY_lag24'] = combined_energy.shift(24).reindex(df.index)
        
        # ENERGY_rolling_mean_24: Media móvil de las últimas 24 horas
        df['ENERGY_rolling_mean_24'] = combined_energy.rolling(
            window=24, 
            min_periods=24
        ).mean().reindex(df.index)
        
        # ENERGY_rolling_std_24: Desviación estándar móvil de las últimas 24 horas
        df['ENERGY_rolling_std_24'] = combined_energy.rolling(
            window=24,
            min_periods=24
        ).std().reindex(df.index)
        
        # Verificar valores nulos (crítico)
        null_counts = df[['ENERGY_lag1', 'ENERGY_lag24', 
                          'ENERGY_rolling_mean_24', 'ENERGY_rolling_std_24']].isnull().sum()
        
        if null_counts.any():
            logger.warning(f"⚠ Valores nulos detectados en features de lag:")
            logger.warning(f"{null_counts[null_counts > 0]}")
            
            # ESTRATEGIA DE IMPUTACIÓN MEJORADA
            logger.warning("  Aplicando estrategia de imputación...")
            
            # Para lag1 y lag24: usar forward fill (propagar último valor conocido)
            if df['ENERGY_lag1'].isnull().any():
                df['ENERGY_lag1'].fillna(method='ffill', inplace=True)
                logger.info("    • ENERGY_lag1: forward fill aplicado")
            
            if df['ENERGY_lag24'].isnull().any():
                df['ENERGY_lag24'].fillna(method='ffill', inplace=True)
                logger.info("    • ENERGY_lag24: forward fill aplicado")
            
            # Para rolling mean/std: usar la media/std de los datos históricos disponibles
            if df['ENERGY_rolling_mean_24'].isnull().any():
                # Usar la media de los últimos valores conocidos de energía
                fallback_mean = historical_energy.tail(24).mean()
                df['ENERGY_rolling_mean_24'].fillna(fallback_mean, inplace=True)
                logger.info(f"    • ENERGY_rolling_mean_24: imputado con {fallback_mean:.2f}")
            
            if df['ENERGY_rolling_std_24'].isnull().any():
                # Usar la desviación estándar de los últimos valores conocidos
                fallback_std = historical_energy.tail(24).std()
                df['ENERGY_rolling_std_24'].fillna(fallback_std, inplace=True)
                logger.info(f"    • ENERGY_rolling_std_24: imputado con {fallback_std:.2f}")
        
        logger.info("✓ Features de lag/ventana creadas")
        logger.info(f"  - ENERGY_lag1: [{df['ENERGY_lag1'].min():.2f}, {df['ENERGY_lag1'].max():.2f}]")
        logger.info(f"  - ENERGY_lag24: [{df['ENERGY_lag24'].min():.2f}, {df['ENERGY_lag24'].max():.2f}]")
        logger.info(f"  - ENERGY_rolling_mean_24: [{df['ENERGY_rolling_mean_24'].min():.2f}, {df['ENERGY_rolling_mean_24'].max():.2f}]")
        logger.info(f"  - ENERGY_rolling_std_24: [{df['ENERGY_rolling_std_24'].min():.2f}, {df['ENERGY_rolling_std_24'].max():.2f}]")
        
        return df
    
    def process_features(
        self,
        future_timestamps: pd.DatetimeIndex,
        weather_forecast: pd.DataFrame,
        historical_energy: pd.Series
    ) -> pd.DataFrame:
        """
        Función principal que orquesta toda la creación de features.
        
        Args:
            future_timestamps: Índice de tiempo para las próximas 24 horas
            weather_forecast: DataFrame con pronóstico del clima
                             Debe contener: PRECTOT, RH2M, T2M, ALLSKY_SFC_SW_DWN
                             (ALLSKY_SFC_SW_DWN se mapeará automáticamente a ALLSKY)
            historical_energy: Serie con datos históricos de energía
                              Debe contener al menos las últimas 48 horas
        
        Returns:
            DataFrame con las 17 features procesadas, listo para ser enviado a la API
        """
        logger.info("="*60)
        logger.info("INICIANDO FEATURE ENGINEERING")
        logger.info("="*60)
        
        # 1. Crear DataFrame base con el índice temporal
        df = pd.DataFrame(index=future_timestamps)
        logger.info(f"1. DataFrame base creado: {len(df)} timestamps")
        logger.info(f"   Rango: {df.index.min()} a {df.index.max()}")
        
        # 2. Añadir features climáticas del pronóstico
        # Mapear ALLSKY_SFC_SW_DWN (del pronóstico) a ALLSKY (nombre usado en el modelo)
        weather_features_map = {
            'PRECTOT': 'PRECTOT',
            'RH2M': 'RH2M',
            'T2M': 'T2M',
            'ALLSKY_SFC_SW_DWN': 'ALLSKY'  # Mapeo importante!
        }
        
        for source_col, target_col in weather_features_map.items():
            if source_col in weather_forecast.columns:
                df[target_col] = weather_forecast[source_col].reindex(df.index)
            else:
                logger.error(f"❌ Feature climática faltante: {source_col}")
                raise ValueError(f"Weather forecast debe contener la columna '{source_col}'")
        
        logger.info(f"2. Features climáticas añadidas: {list(weather_features_map.values())}")
        
        # 3. Crear features cíclicas
        df = self.create_cyclical_features(df)
        logger.info("3. Features cíclicas creadas")
        
        # 4. Crear features calendáricas
        df = self.create_calendar_features(df)
        logger.info("4. Features calendáricas creadas")
        
        # 5. Crear features derivadas del clima
        df = self.create_weather_derived_features(df)
        logger.info("5. Features derivadas del clima creadas")
        
        # 6. Crear features de lag/ventana (LA PARTE MÁS CRÍTICA)
        df = self.create_lag_features(df, historical_energy)
        logger.info("6. Features de lag/ventana creadas")
        
        # 7. Validar que todas las features esperadas estén presentes
        missing_features = set(self.feature_names) - set(df.columns)
        if missing_features:
            logger.error(f"❌ Features faltantes: {missing_features}")
            raise ValueError(f"Faltan features: {missing_features}")
        
        # 8. Reordenar columnas según el orden esperado
        df = df[self.feature_names]
        
        # 9. Validación final con tratamiento de nulos residuales
        null_count = df.isnull().sum().sum()
        if null_count > 0:
            logger.warning(f"⚠️ Se encontraron {null_count} valores nulos residuales")
            logger.warning(df.isnull().sum()[df.isnull().sum() > 0])
            
            # Última estrategia: imputar con mediana de la columna
            logger.warning("  Aplicando imputación final con mediana...")
            for col in df.columns:
                if df[col].isnull().any():
                    median_val = df[col].median()
                    if pd.isna(median_val):
                        # Si la mediana es NaN, usar 0 como fallback
                        df[col].fillna(0, inplace=True)
                        logger.warning(f"    • {col}: imputado con 0 (fallback)")
                    else:
                        df[col].fillna(median_val, inplace=True)
                        logger.warning(f"    • {col}: imputado con mediana {median_val:.2f}")
            
            # Verificar nuevamente
            final_null_count = df.isnull().sum().sum()
            if final_null_count > 0:
                logger.error(f"❌ Aún quedan {final_null_count} valores nulos después de imputación")
                logger.error(df.isnull().sum()[df.isnull().sum() > 0])
                raise ValueError("No se pudieron eliminar todos los valores nulos")
            
            logger.info("✓ Todos los nulos fueron imputados exitosamente")
        
        logger.info("="*60)
        logger.info("✓ FEATURE ENGINEERING COMPLETADO")
        logger.info(f"  - Shape: {df.shape}")
        logger.info(f"  - Features: {len(df.columns)}")
        logger.info(f"  - Registros: {len(df)}")
        logger.info("="*60)
        
        return df


def create_future_timestamps(start_time: datetime, hours: int = 24) -> pd.DatetimeIndex:
    """
    Crear un índice de tiempo para las próximas N horas.
    
    Args:
        start_time: Tiempo de inicio (usualmente datetime.now() + 1 hora)
        hours: Número de horas a pronosticar (por defecto 24)
    
    Returns:
        DatetimeIndex con timestamps horarios
    """
    timestamps = pd.date_range(
        start=start_time,
        periods=hours,
        freq='H'
    )
    logger.info(f"Timestamps futuros creados: {len(timestamps)} horas")
    logger.info(f"  Desde: {timestamps[0]}")
    logger.info(f"  Hasta: {timestamps[-1]}")
    
    return timestamps


def validate_historical_energy(
    historical_energy: pd.Series,
    required_lookback: int = 48
) -> bool:
    """
    Validar que los datos históricos de energía sean suficientes.
    
    Args:
        historical_energy: Serie con datos históricos
        required_lookback: Horas de lookback requeridas (por defecto 48)
    
    Returns:
        True si los datos son válidos, False en caso contrario
    """
    if len(historical_energy) < required_lookback:
        logger.error(f"❌ Datos históricos insuficientes: {len(historical_energy)} < {required_lookback}")
        return False
    
    # Verificar que no haya gaps en los datos
    if not isinstance(historical_energy.index, pd.DatetimeIndex):
        logger.error("❌ El índice de historical_energy debe ser DatetimeIndex")
        return False
    
    # Verificar frecuencia horaria
    inferred_freq = pd.infer_freq(historical_energy.index)
    if inferred_freq != 'H':
        logger.warning(f"⚠ Frecuencia inferida: {inferred_freq} (esperado: 'H')")
    
    # Verificar valores nulos
    null_count = historical_energy.isnull().sum()
    if null_count > 0:
        logger.warning(f"⚠ Datos históricos contienen {null_count} valores nulos")
    
    logger.info(f"✓ Validación de datos históricos exitosa: {len(historical_energy)} puntos")
    
    return True


# Ejemplo de uso
if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(level=logging.INFO)
    
    # Crear instancia del Feature Engineer
    engineer = FeatureEngineer()
    
    # Simular datos de entrada
    future_timestamps = create_future_timestamps(
        start_time=datetime.now() + timedelta(hours=1),
        hours=24
    )
    
    # Simular pronóstico climático
    weather_forecast = pd.DataFrame({
        'PRECTOT': np.random.uniform(0, 5, 24),
        'RH2M': np.random.uniform(40, 80, 24),
        'T2M': np.random.uniform(15, 30, 24),
        'ALLSKY_SFC_SW_DWN': np.random.uniform(200, 600, 24)
    }, index=future_timestamps)
    
    # Simular datos históricos de energía
    historical_timestamps = pd.date_range(
        end=datetime.now(),
        periods=48,
        freq='H'
    )
    historical_energy = pd.Series(
        np.random.uniform(4000, 7000, 48),
        index=historical_timestamps
    )
    
    # Validar datos históricos
    if validate_historical_energy(historical_energy):
        # Procesar features
        features_df = engineer.process_features(
            future_timestamps=future_timestamps,
            weather_forecast=weather_forecast,
            historical_energy=historical_energy
        )
        
        print("\n" + "="*60)
        print("FEATURES GENERADAS")
        print("="*60)
        print(features_df.head())
        print(f"\nShape: {features_df.shape}")
        print(f"Columnas: {features_df.columns.tolist()}")
