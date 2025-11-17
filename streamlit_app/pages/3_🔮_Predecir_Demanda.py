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

st.set_page_config(page_title="Predecir Demanda", page_icon="🔮", layout="wide")

# API URL
api_url = os.getenv("API_URL", "http://localhost:8000")

st.title("🔮 Predicción de Demanda Energética")
st.markdown("### Ingresa los datos meteorológicos y temporales para predecir la demanda")

# Información sobre el modelo
with st.expander("ℹ️ ¿Cómo funciona?"):
    st.markdown("""
    Este sistema utiliza un modelo de Machine Learning (XGBoost) entrenado con datos históricos 
    para predecir la demanda energética basándose en:
    
    - 🌡️ **Variables meteorológicas**: Temperatura, humedad, precipitación, radiación solar
    - 📅 **Variables temporales**: Hora del día, día de la semana, mes del año
    - 🎯 **Variables calendáricas**: Días festivos, fines de semana
    
    **No necesitas ingresar la demanda energética** - ¡el modelo la predecirá por ti!
    """)

st.divider()

# Crear formulario de predicción
with st.form("prediction_form", clear_on_submit=False):
    st.markdown("#### 📅 Información Temporal")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fecha = st.date_input(
            "Fecha de Predicción",
            value=datetime.now().date(),
            help="Fecha para la cual deseas predecir la demanda"
        )
    
    with col2:
        hora = st.time_input(
            "Hora de Predicción",
            value=datetime.now().time(),
            help="Hora para la predicción (formato 24h)"
        )
    
    # Combinar fecha y hora
    timestamp = datetime.combine(fecha, hora)
    
    # Detectar si es fin de semana
    is_weekend = timestamp.weekday() >= 5
    
    # Detectar si es festivo (puedes personalizar esta lista)
    holidays = [
        "01-01", "04-14", "04-15", "05-01", "06-29",
        "07-28", "07-29", "08-30", "10-08", "11-01",
        "12-08", "12-25"
    ]
    is_holiday = timestamp.strftime("%m-%d") in holidays
    
    st.divider()
    
    st.markdown("#### 🌦️ Variables Meteorológicas")
    st.caption("Ingresa las condiciones meteorológicas actuales o esperadas")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        t2m = st.number_input(
            "🌡️ Temperatura Promedio (°C)",
            min_value=-20.0,
            max_value=50.0,
            value=20.0,
            step=0.5,
            help="Temperatura promedio al nivel de 2 metros"
        )
        
        t2m_min = st.number_input(
            "❄️ Temperatura Mínima (°C)",
            min_value=-30.0,
            max_value=50.0,
            value=t2m - 5,
            step=0.5,
            help="Temperatura mínima esperada"
        )
        
        t2m_max = st.number_input(
            "🔥 Temperatura Máxima (°C)",
            min_value=-20.0,
            max_value=60.0,
            value=t2m + 5,
            step=0.5,
            help="Temperatura máxima esperada"
        )
    
    with col2:
        rh2m = st.slider(
            "💧 Humedad Relativa (%)",
            min_value=0,
            max_value=100,
            value=65,
            help="Humedad relativa al nivel de 2 metros"
        )
        
        prectot = st.number_input(
            "🌧️ Precipitación Total (mm)",
            min_value=0.0,
            max_value=200.0,
            value=0.0,
            step=0.1,
            help="Precipitación acumulada"
        )
        
        allsky = st.number_input(
            "☀️ Radiación Solar (W/m²)",
            min_value=0.0,
            max_value=1000.0,
            value=400.0,
            step=10.0,
            help="Radiación solar total (ALLSKY_SFC_SW_DWN)"
        )
    
    with col3:
        st.markdown("**Variables Calculadas Automáticamente**")
        
        # Mostrar variables que se calcularán
        st.info(f"📅 **Día:** {timestamp.strftime('%A, %d %B %Y')}")
        st.info(f"⏰ **Hora:** {timestamp.strftime('%H:%M')}")
        st.info(f"🗓️ **Fin de Semana:** {'Sí' if is_weekend else 'No'}")
        st.info(f"🎉 **Día Festivo:** {'Sí' if is_holiday else 'No'}")
        
        # Calcular HDD y CDD
        hdd = max(0.0, 18.3 - t2m)
        cdd0 = max(0.0, t2m - 0)
        cdd10 = max(0.0, t2m - 10)
        
        st.caption("Variables derivadas:")
        st.metric("HDD18.3", f"{hdd:.2f}")
        st.metric("CDD0", f"{cdd0:.2f}")
        st.metric("CDD10", f"{cdd10:.2f}")
    
    st.divider()
    
    # Botón de predicción
    col1, col2, col3 = st.columns([2, 1, 2])
    
    with col2:
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
                    ⚠️ **Demanda Alta Detectada**
                    
                    - Activar protocolos de alta demanda
                    - Considerar fuentes de energía adicionales
                    - Alertar a los operadores del sistema
                    """)
                elif predicted_energy > 110:
                    st.warning("""
                    ⚡ **Demanda Normal-Alta**
                    
                    - Monitorear continuamente
                    - Preparar recursos de respaldo
                    - Mantener eficiencia operativa
                    """)
                else:
                    st.success("""
                    ✅ **Demanda Normal**
                    
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
