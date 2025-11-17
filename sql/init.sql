-- ============================================================================
-- Script de Inicialización de Base de Datos
-- Sistema Inteligente de Pronóstico de Demanda Energética
-- Datos históricos: 2016-2020
-- ============================================================================

-- ============================================================================
-- CREAR BASES DE DATOS
-- ============================================================================

-- Base de datos para Airflow (metadatos)
CREATE DATABASE airflow_db;

-- ============================================================================
-- TABLA 1: historical_energy
-- Almacena datos históricos de consumo energético con sus 17 features
-- Rango: 2016-01-01 a 2020-12-31 (datos horarios)
-- ============================================================================

CREATE TABLE IF NOT EXISTS historical_energy (
    id SERIAL,
    
    -- Timestamp del registro (columna DATE del CSV original)
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- Variable objetivo (Y) - Lo que queremos predecir
    ENERGY NUMERIC(7, 2),
    
    -- Features climáticas (4)
    PRECTOT NUMERIC(7, 4),              -- Precipitación total (mm)
    RH2M NUMERIC(5, 2),                 -- Humedad relativa al 2m (%)
    T2M NUMERIC(5, 2),                  -- Temperatura al 2m (°C)
    ALLSKY NUMERIC(7, 2),               -- Radiación solar (W/m²)
    
    -- Features calendáricas (2)
    HOLIDAY INTEGER,                     -- Día festivo (0 o 1)
    IsWeekend INTEGER,                   -- Fin de semana (0 o 1)
    
    -- Features cíclicas temporales (6)
    Hour_sin NUMERIC(10, 6),            -- Hora del día (componente seno)
    Hour_cos NUMERIC(10, 6),            -- Hora del día (componente coseno)
    Month_sin NUMERIC(10, 6),           -- Mes del año (componente seno)
    Month_cos NUMERIC(10, 6),           -- Mes del año (componente coseno)
    DayOfWeek_sin NUMERIC(10, 6),      -- Día de la semana (componente seno)
    DayOfWeek_cos NUMERIC(10, 6),      -- Día de la semana (componente coseno)
    
    -- Features derivadas (1)
    Temp_Range NUMERIC(5, 2),           -- Rango de temperatura diario
    
    -- Features de lag/ventana temporal (4)
    ENERGY_lag1 NUMERIC(7, 2),          -- Energía del período anterior (1h)
    ENERGY_lag24 NUMERIC(7, 2),         -- Energía de hace 24h
    ENERGY_rolling_mean_24 NUMERIC(7, 2),   -- Media móvil 24h
    ENERGY_rolling_std_24 NUMERIC(7, 2),    -- Desviación estándar móvil 24h
    
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Índice para búsquedas temporales rápidas
CREATE INDEX idx_historical_energy_timestamp ON historical_energy(timestamp DESC);

-- Comentarios descriptivos
COMMENT ON TABLE historical_energy IS 'Datos históricos de consumo energético (2016-2020) con 17 features procesadas';
COMMENT ON COLUMN historical_energy.timestamp IS 'Fecha y hora del registro (proveniente de columna DATE del CSV)';
COMMENT ON COLUMN historical_energy.ENERGY IS 'Consumo energético en MW (variable objetivo Y)';


-- ============================================================================
-- TABLA 2: energy_forecasts
-- Almacena pronósticos generados por el agente
-- ============================================================================

CREATE TABLE IF NOT EXISTS energy_forecasts (
    id SERIAL PRIMARY KEY,
    forecast_timestamp TIMESTAMPTZ NOT NULL,
    predicted_energy_mw NUMERIC(7, 2) NOT NULL,
    model_version VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    dag_run_id VARCHAR(250),
    
    CONSTRAINT unique_forecast_timestamp UNIQUE (forecast_timestamp)
);

CREATE INDEX idx_forecast_timestamp ON energy_forecasts(forecast_timestamp DESC);
CREATE INDEX idx_forecast_created_at ON energy_forecasts(created_at DESC);
CREATE INDEX idx_forecast_model_version ON energy_forecasts(model_version);

COMMENT ON TABLE energy_forecasts IS 'Pronósticos de demanda energética generados por el agente';
COMMENT ON COLUMN energy_forecasts.forecast_timestamp IS 'Fecha/hora futura para la cual se hizo el pronóstico';
COMMENT ON COLUMN energy_forecasts.predicted_energy_mw IS 'Demanda energética pronosticada en MW';


-- ============================================================================
-- TABLA 3: model_performance
-- Almacena métricas de rendimiento del modelo
-- ============================================================================

CREATE TABLE IF NOT EXISTS model_performance (
    id SERIAL PRIMARY KEY,
    evaluation_date TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    model_version VARCHAR(50),
    metric_name VARCHAR(50) NOT NULL,
    metric_value NUMERIC(10, 4) NOT NULL,
    evaluation_period_start TIMESTAMPTZ,
    evaluation_period_end TIMESTAMPTZ,
    notes TEXT
);

CREATE INDEX idx_performance_date ON model_performance(evaluation_date DESC);
CREATE INDEX idx_performance_version ON model_performance(model_version);
CREATE INDEX idx_performance_metric ON model_performance(metric_name);

COMMENT ON TABLE model_performance IS 'Métricas de rendimiento del modelo (RMSE, MAE, MAPE, etc.)';


-- ============================================================================
-- TABLA 4: agent_logs
-- Logs de ejecución del agente
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_logs (
    id SERIAL PRIMARY KEY,
    log_timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    agent_phase VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    message TEXT,
    execution_time_seconds NUMERIC(10, 2),
    records_processed INTEGER,
    error_details TEXT
);

CREATE INDEX idx_logs_timestamp ON agent_logs(log_timestamp DESC);
CREATE INDEX idx_logs_phase ON agent_logs(agent_phase);
CREATE INDEX idx_logs_status ON agent_logs(status);

COMMENT ON TABLE agent_logs IS 'Logs de ejecución del ciclo Percepción-Acción del agente';

-- ============================================================================
-- Total de registros insertados: 43848
-- Para evitar duplicados al re-ejecutar, añade al final:
-- ON CONFLICT (timestamp) DO NOTHING;
-- ============================================================================

-- ============================================================================
-- Vista para Monitoreo de Performance del Modelo
-- Compara predicciones vs valores reales de energía
-- ============================================================================

CREATE OR REPLACE VIEW forecast_performance AS
SELECT 
    ef.id,
    ef.forecast_timestamp,
    ef.predicted_energy_mw,
    he.energy AS actual_energy_mw,
    ef.model_version,
    ef.created_at,
    ef.dag_run_id,
    
    -- Calcular error absoluto
    ABS(ef.predicted_energy_mw - he.energy) AS absolute_error,
    
    -- Calcular error porcentual
    CASE 
        WHEN he.energy > 0 THEN 
            ABS((ef.predicted_energy_mw - he.energy) / he.energy * 100)
        ELSE NULL 
    END AS percentage_error,
    
    -- Clasificar calidad de la predicción
    CASE 
        WHEN ABS((ef.predicted_energy_mw - he.energy) / he.energy * 100) <= 5 THEN 'Excelente'
        WHEN ABS((ef.predicted_energy_mw - he.energy) / he.energy * 100) <= 10 THEN 'Buena'
        WHEN ABS((ef.predicted_energy_mw - he.energy) / he.energy * 100) <= 20 THEN 'Aceptable'
        ELSE 'Necesita Mejora'
    END AS prediction_quality,
    
    -- Extraer información temporal para análisis
    EXTRACT(HOUR FROM ef.forecast_timestamp) AS hour_of_day,
    EXTRACT(DOW FROM ef.forecast_timestamp) AS day_of_week,
    EXTRACT(MONTH FROM ef.forecast_timestamp) AS month,
    
    -- Calcular tiempo transcurrido entre predicción y realidad
    he.created_at - ef.created_at AS time_to_validate

FROM energy_forecasts ef
LEFT JOIN historical_energy he 
    ON DATE_TRUNC('hour', ef.forecast_timestamp) = DATE_TRUNC('hour', he.timestamp)
WHERE he.energy IS NOT NULL  -- Solo donde tenemos valores reales
ORDER BY ef.forecast_timestamp DESC;

-- Crear índices para mejorar performance
CREATE INDEX IF NOT EXISTS idx_forecast_timestamp ON energy_forecasts(forecast_timestamp);
CREATE INDEX IF NOT EXISTS idx_historical_timestamp ON historical_energy(timestamp);

-- ============================================================================
-- Vista Agregada: Métricas por Día
-- ============================================================================

CREATE OR REPLACE VIEW daily_forecast_metrics AS
SELECT 
    DATE(forecast_timestamp) AS forecast_date,
    model_version,
    COUNT(*) AS n_predictions,
    COUNT(actual_energy_mw) AS n_validated,
    
    -- Métricas de error
    AVG(absolute_error) AS mae,  -- Mean Absolute Error
    SQRT(AVG(POWER(absolute_error, 2))) AS rmse,  -- Root Mean Squared Error
    AVG(percentage_error) AS mape,  -- Mean Absolute Percentage Error
    
    -- Distribución de calidad
    COUNT(CASE WHEN prediction_quality = 'Excelente' THEN 1 END) AS excellent_count,
    COUNT(CASE WHEN prediction_quality = 'Buena' THEN 1 END) AS good_count,
    COUNT(CASE WHEN prediction_quality = 'Aceptable' THEN 1 END) AS acceptable_count,
    COUNT(CASE WHEN prediction_quality = 'Necesita Mejora' THEN 1 END) AS needs_improvement_count,
    
    -- Valores promedio
    AVG(predicted_energy_mw) AS avg_predicted,
    AVG(actual_energy_mw) AS avg_actual,
    
    -- Rango de error
    MIN(absolute_error) AS min_error,
    MAX(absolute_error) AS max_error

FROM forecast_performance
GROUP BY DATE(forecast_timestamp), model_version
ORDER BY forecast_date DESC;

-- ============================================================================
-- Vista: Peores Predicciones (para análisis de errores)
-- ============================================================================

CREATE OR REPLACE VIEW worst_predictions AS
SELECT *
FROM forecast_performance
WHERE actual_energy_mw IS NOT NULL
  AND percentage_error > 20  -- Errores mayores al 20%
ORDER BY percentage_error DESC
LIMIT 100;

COMMENT ON VIEW forecast_performance IS 'Comparación detallada entre predicciones y valores reales';
COMMENT ON VIEW daily_forecast_metrics IS 'Métricas agregadas diarias de performance del modelo';
COMMENT ON VIEW worst_predictions IS 'Top 100 predicciones con mayor error para análisis';


-- ============================================================================
-- PERMISOS DE ACCESO
-- ============================================================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO energy_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO energy_user;

-- ============================================================================
-- MENSAJE DE CONFIRMACIÓN
-- ============================================================================

DO $$
DECLARE
    hist_count INTEGER;
    fore_count INTEGER;
    perf_count INTEGER;
    logs_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO hist_count FROM historical_energy;
    SELECT COUNT(*) INTO fore_count FROM energy_forecasts;
    SELECT COUNT(*) INTO perf_count FROM model_performance;
    SELECT COUNT(*) INTO logs_count FROM agent_logs;
    
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Base de datos inicializada correctamente';
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Tablas creadas:';
    RAISE NOTICE '   - historical_energy: % registros', hist_count;
    RAISE NOTICE '   - energy_forecasts: % registros', fore_count;
    RAISE NOTICE '   - model_performance: % registros', perf_count;
    RAISE NOTICE '   - agent_logs: % registros', logs_count;
    RAISE NOTICE '============================================================';
END $$;

-- ============================================================================
-- GRANTS (Permisos)
-- ============================================================================

-- Otorgar permisos al usuario de Airflow
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO energy_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO energy_user;


-- ============================================================================
-- INFORMACIÓN FINAL
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Base de datos inicializada correctamente';
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'Tablas creadas:';
    RAISE NOTICE '  - historical_energy: % registros', (SELECT COUNT(*) FROM historical_energy);
    RAISE NOTICE '  - energy_forecasts: % registros', (SELECT COUNT(*) FROM energy_forecasts);
    RAISE NOTICE '  - model_performance: % registros', (SELECT COUNT(*) FROM model_performance);
    RAISE NOTICE '  - agent_logs: % registros', (SELECT COUNT(*) FROM agent_logs);
    RAISE NOTICE '============================================================';
END $$;
