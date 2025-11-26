"""
Página de Predicción de Demanda Energética

Formulario para predecir la demanda energética usando el modelo entrenado.
El usuario solo ingresa las variables de entrada (sin el target ENERGY).
"""

import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os
import sys
import pytz

# Agregar el directorio padre al path para importar agente_climatico
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agente_climatico_v2 import AgenteClimaticoInteligente

st.set_page_config(page_title="Predecir Demanda", page_icon="🔮", layout="wide")

# API URL
api_url = os.getenv("API_URL", "http://localhost:8000")

# Zona horaria de Lima, Perú
LIMA_TZ = pytz.timezone('America/Lima')

# Inicializar Agente Climático Inteligente v2.0
agente_clima = AgenteClimaticoInteligente()

# Obtener TODOS los datos climáticos con validación inteligente
clima_data = agente_clima.obtener_datos_climaticos_completos()

# Extraer valores con validación
default_t2m = clima_data.get("T2M", 20.0)
default_rh2m = clima_data.get("RH2M", 65)
default_prectot = clima_data.get("PRECTOT", 0.0)
default_allsky = clima_data.get("ALLSKY", 400.0)

st.title("🔮 Predicción de Demanda Energética")
st.markdown("### Ingresa los datos meteorológicos y temporales para predecir la demanda")

# Banner de estado del agente inteligente (más compacto)
st.success("""
**🤖 Agente Climático Inteligente v2.0 ACTIVO** • Validación multicapa: Rangos físicos ✅ | Análisis estadístico 🔍 | Google AI 🤖
""")

# Ubicación y botón de refresh en una sola línea
col_loc, col_refresh = st.columns([5, 1])
with col_loc:
    st.caption(f"🌍 **{clima_data['location']}** | 📡 Firebase IoT | 🌐 OpenWeatherMap | 🛰️ NASA POWER")
with col_refresh:
    if st.button("🔄", help="Refrescar datos climáticos"):
        agente_clima.limpiar_cache()
        st.rerun()

# Mostrar SOLO advertencias importantes (outliers severos o rechazos)
if 'validaciones' in clima_data and clima_data['validaciones']:
    for var_name, validacion in clima_data['validaciones'].items():
        nivel = validacion.get('nivel', '')
        # Solo mostrar si es outlier leve o advertencia válida
        if '⚠️' in nivel or '🟡' in nivel:
            with st.expander(f"⚠️ {var_name.upper()}: {nivel}"):
                st.caption(validacion['mensaje'])
                if validacion.get('ai_analisis'):
                    st.info(f"🤖 Análisis AI: {validacion['ai_analisis']}")

# Información sobre el modelo (más compacto)
with st.expander("ℹ️ ¿Cómo funciona?"):
    st.markdown("""
    **Agente Climático Inteligente** con validación multicapa:
    - 📡 **Firebase IoT**: Sensores temperatura/humedad en tiempo real
    - 🌐 **OpenWeatherMap**: Precipitación actual
    - 🛰️ **NASA POWER**: Radiación solar histórica
    
    **Predicción con Machine Learning (XGBoost)** basada en:
    - 🌡️ Variables meteorológicas (temperatura, humedad, precipitación, radiación)
    - 📅 Variables temporales (hora, día, mes, fines de semana, festivos)
    
    *El agente obtiene automáticamente los datos más recientes* - ¡tú solo ajusta si es necesario!
    """)

st.divider()

# ==================== FORMULARIO DE PREDICCIÓN ====================
st.markdown("### 📊 Configuración de Predicción")

# Crear formulario
with st.form("prediction_form", clear_on_submit=False):
    
    # Sección temporal
    st.markdown("#### 📅 Información Temporal")
    col_fecha, col_hora = st.columns(2)
    
    with col_fecha:
        fecha = st.date_input(
            "Fecha de Predicción",
            value=datetime.now(LIMA_TZ).date(),
            help="Fecha para la cual deseas predecir la demanda"
        )
    
    with col_hora:
        hora = st.time_input(
            "Hora de Predicción",
            value=datetime.now(LIMA_TZ).time(),
            help="Hora para la predicción (formato 24h)"
        )
    
    # Combinar fecha y hora y calcular variables derivadas
    timestamp = datetime.combine(fecha, hora)
    is_weekend = timestamp.weekday() >= 5
    holidays = ["01-01", "04-14", "04-15", "05-01", "06-29", "07-28", "07-29", 
                "08-30", "10-08", "11-01", "12-08", "12-25"]
    is_holiday = timestamp.strftime("%m-%d") in holidays
    
    st.divider()
    
    # Sección meteorológica
    st.markdown("#### 🌦️ Variables Meteorológicas")
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Temperatura**")
        t2m = st.number_input(
            "Promedio (°C)",
            min_value=-20.0,
            max_value=50.0,
            value=float(default_t2m),
            step=0.5,
            key="t2m_input"
        )
        
        col_min, col_max = st.columns(2)
        with col_min:
            t2m_min = st.number_input(
                "Mínima (°C)",
                min_value=-30.0,
                max_value=50.0,
                value=float(t2m - 5),
                step=0.5,
                key="t2m_min_input"
            )
        with col_max:
            t2m_max = st.number_input(
                "Máxima (°C)",
                min_value=-20.0,
                max_value=60.0,
                value=float(t2m + 5),
                step=0.5,
                key="t2m_max_input"
            )
        
        st.markdown("**Humedad**")
        rh2m = st.slider(
            "Humedad Relativa (%)",
            min_value=0.0,
            max_value=100.0,
            value=float(default_rh2m),
            step=1.0
        )
    
    with col2:
        st.markdown("**Precipitación**")
        prectot = st.number_input(
            "Precipitación Total (mm)",
            min_value=0.0,
            max_value=200.0,
            value=float(default_prectot),
            step=0.1
        )
        
        st.markdown("**Radiación Solar**")
        allsky = st.number_input(
            "Radiación Solar (W/m²)",
            min_value=0.0,
            max_value=1000.0,
            value=float(default_allsky),
            step=10.0
        )
        
        # Variables derivadas (compactas)
        st.caption("📊 Variables calculadas automáticamente:")
        hdd = max(0.0, 18.3 - t2m)
        cdd0 = max(0.0, t2m - 0)
        cdd10 = max(0.0, t2m - 10)
        
        col_hdd, col_cdd = st.columns(2)
        with col_hdd:
            st.metric("HDD18.3", f"{hdd:.1f}")
        with col_cdd:
            st.metric("CDD0/CDD10", f"{cdd0:.1f} / {cdd10:.1f}")
    
    st.divider()
    
    # Botón de predicción centrado
    col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 2])
    with col_btn2:
        predict_button = st.form_submit_button(
            "🔮 Predecir Demanda",
            use_container_width=True,
            type="primary"
        )

# Procesar la predicción
if predict_button:
    with st.spinner("🤖 El modelo está calculando la predicción..."):
        try:
            # Construir las 17 features necesarias
            import numpy as np
            
            # Features cíclicas
            hour_sin = np.sin(2 * np.pi * timestamp.hour / 24)
            hour_cos = np.cos(2 * np.pi * timestamp.hour / 24)
            month_sin = np.sin(2 * np.pi * timestamp.month / 12)
            month_cos = np.cos(2 * np.pi * timestamp.month / 12)
            day_sin = np.sin(2 * np.pi * timestamp.weekday() / 7)
            day_cos = np.cos(2 * np.pi * timestamp.weekday() / 7)
            
            # Temp_Range
            temp_range = t2m_max - t2m_min
            
            # Features de lag (usar valores por defecto basados en promedios históricos)
            # En producción, estos vendrían de la BD
            energy_lag1 = 110.0  # Valor promedio histórico
            energy_lag24 = 110.0
            energy_rolling_mean_24 = 110.0
            energy_rolling_std_24 = 5.0
            
            # Construir payload con las 17 features
            payload = {
                "features": [{
                    "PRECTOT": prectot,
                    "RH2M": rh2m,
                    "T2M": t2m,
                    "ALLSKY": allsky,
                    "HOLIDAY": 1 if is_holiday else 0,
                    "IsWeekend": 1 if is_weekend else 0,
                    "Hour_sin": hour_sin,
                    "Hour_cos": hour_cos,
                    "Month_sin": month_sin,
                    "Month_cos": month_cos,
                    "DayOfWeek_sin": day_sin,
                    "DayOfWeek_cos": day_cos,
                    "Temp_Range": temp_range,
                    "ENERGY_lag1": energy_lag1,
                    "ENERGY_lag24": energy_lag24,
                    "ENERGY_rolling_mean_24": energy_rolling_mean_24,
                    "ENERGY_rolling_std_24": energy_rolling_std_24
                }]
            }
            
            # Llamar a la API de predicción
            response = requests.post(
                f"{api_url}/predict",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                predicted_energy = result['predictions'][0]
                
                # Mostrar resultado
                st.success("✅ Predicción realizada exitosamente")
                
                st.divider()
                
                # Métricas principales
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "🔮 Demanda Predicha",
                        f"{predicted_energy:.2f} MW",
                        help="Demanda energética predicha por el modelo"
                    )
                
                with col2:
                    # Clasificar el nivel de demanda
                    if predicted_energy < 100:
                        nivel = "Baja"
                        color = "🟢"
                    elif predicted_energy < 120:
                        nivel = "Media"
                        color = "🟡"
                    else:
                        nivel = "Alta"
                        color = "🔴"
                    
                    st.metric(
                        "📊 Nivel de Demanda",
                        f"{color} {nivel}",
                        help="Clasificación basada en rangos históricos"
                    )
                
                with col3:
                    st.metric(
                        "🌡️ Temperatura",
                        f"{t2m:.1f}°C",
                        help="Temperatura ingresada"
                    )
                
                with col4:
                    st.metric(
                        "⏰ Hora",
                        timestamp.strftime('%H:%M'),
                        help="Hora de la predicción"
                    )
                
                st.divider()
                
                # Gráfico de gauge
                fig = go.Figure(go.Indicator(
                    mode="gauge+number+delta",
                    value=predicted_energy,
                    domain={'x': [0, 1], 'y': [0, 1]},
                    title={'text': "Demanda Energética Predicha (MW)"},
                    delta={'reference': 110, 'suffix': " MW"},
                    gauge={
                        'axis': {'range': [None, 150]},
                        'bar': {'color': "darkblue"},
                        'steps': [
                            {'range': [0, 100], 'color': "lightgreen"},
                            {'range': [100, 120], 'color': "yellow"},
                            {'range': [120, 150], 'color': "lightcoral"}
                        ],
                        'threshold': {
                            'line': {'color': "red", 'width': 4},
                            'thickness': 0.75,
                            'value': 140
                        }
                    }
                ))
                
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                # Interpretación
                st.markdown("### 💡 Interpretación y Recomendaciones")
                
                if predicted_energy > 130:
                    st.error("""
                    ⚠️ *Demanda Alta Detectada*
                    
                    - Activar protocolos de alta demanda
                    - Considerar fuentes de energía adicionales
                    - Alertar a los operadores del sistema
                    """)
                elif predicted_energy > 110:
                    st.warning("""
                    ⚡ *Demanda Normal-Alta*
                    
                    - Monitorear continuamente
                    - Preparar recursos de respaldo
                    - Mantener eficiencia operativa
                    """)
                else:
                    st.success("""
                    ✅ *Demanda Normal*
                    
                    - Operación estándar
                    - Continuar con monitoreo rutinario
                    - Oportunidad para mantenimiento planificado
                    """)
                
                # Mostrar detalles técnicos
                with st.expander("🔧 Detalles Técnicos de la Predicción"):
                    st.markdown("**Features Utilizadas:**")
                    
                    feature_df = pd.DataFrame([{
                        'Feature': k,
                        'Valor': f"{v:.4f}" if isinstance(v, (int, float)) else str(v)
                    } for k, v in payload['features'][0].items()])
                    
                    st.dataframe(feature_df, use_container_width=True, hide_index=True)
                    
                    st.markdown(f"""
                    **Información del Modelo:**
                    - Versión: {result.get('model_version', 'N/A')}
                    - Tipo: XGBRegressor
                    - Features: {result.get('n_predictions', 17)}
                    """)
                    
                    st.markdown("**Fuentes de Datos Climáticos:**")
                    st.json({
                        "ubicacion": clima_data['location'],
                        "coordenadas": f"({clima_data['lat']:.4f}, {clima_data['lon']:.4f})",
                        "fuentes": clima_data['fuentes'],
                        "timestamp": clima_data['timestamp'],
                        "desde_cache": clima_data.get('from_cache', False)
                    })
                    
                    if 'validaciones' in clima_data and clima_data['validaciones']:
                        st.markdown("**Detalles de Validación:**")
                        for var_name, val_info in clima_data['validaciones'].items():
                            with st.expander(f"{var_name.upper()} - {val_info['nivel']}"):
                                st.caption(val_info['mensaje'])
                                st.caption(f"Capa de validación: {val_info['capa_validacion']}")
                                if val_info.get('zscore'):
                                    st.caption(f"Z-score: {val_info['zscore']:.2f}")
                                if val_info.get('ai_analisis'):
                                    st.info(f"🤖 {val_info['ai_analisis']}")
                    
                    # Estadísticas del agente
                    stats = agente_clima.obtener_estadisticas()
                    st.markdown("**Estado del Agente Climático:**")
                    st.json(stats)
                
                # Opción para guardar la predicción
                st.divider()
                
                if st.button("💾 Guardar esta predicción en el histórico", use_container_width=True):
                    st.info("💡 Funcionalidad en desarrollo: guardar predicción en la base de datos")
            
            else:
                error_detail = response.json().get('detail', 'Error desconocido')
                st.error(f"❌ Error en la predicción: {error_detail}")
                
                with st.expander("Ver detalles del error"):
                    st.json(response.json())
        
        except requests.exceptions.Timeout:
            st.error("❌ Timeout: La API no respondió a tiempo. Verifica que el servicio esté activo.")
        
        except requests.exceptions.ConnectionError:
            st.error("❌ Error de conexión: No se pudo conectar con la API.")
            st.info(f"Verifica que la API esté corriendo en: {api_url}")
        
        except Exception as e:
            st.error(f"❌ Error inesperado: {e}")
            
            with st.expander("Ver detalles del error"):
                st.exception(e)

# Footer con información
st.divider()
st.markdown("""
    <div style='text-align: center; color: gray;'>
        <p>🔮 Predicción basada en modelo XGBoost entrenado con datos históricos 2016-2020</p>
        <p>⚠️ Las predicciones son estimaciones y deben ser validadas por expertos</p>
    </div>
""", unsafe_allow_html=True)