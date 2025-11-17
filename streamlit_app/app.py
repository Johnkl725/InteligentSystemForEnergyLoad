"""
Energy Forecast Agent - Aplicación Web Principal

Dashboard inteligente para:
1. Visualizar predicciones de demanda energética
2. Ingresar nuevos datos históricos
3. Monitorear performance del modelo
4. Ver recomendaciones del agente
"""

import streamlit as st
import requests
from datetime import datetime
import os

# Configuración de la página
st.set_page_config(
    page_title="Energy Forecast Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos personalizados
st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown('<h1 class="main-header">⚡ Energy Forecast Agent</h1>', unsafe_allow_html=True)
st.markdown("### 🤖 Sistema Inteligente de Predicción de Demanda Energética")

# Sidebar - Información del sistema
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/artificial-intelligence.png", width=80)
    st.title("🔧 Panel de Control")
    
    # Estado del sistema
    st.subheader("Estado del Sistema")
    
    # Obtener API URL desde variable de entorno (cambiado de st.secrets)
    api_url = os.getenv("API_URL", "http://localhost:8000")
    
    try:
        response = requests.get(f"{api_url}/health", timeout=2)
        if response.status_code == 200:
            st.success("✅ API Conectada")
        else:
            st.error("❌ API No Responde")
    except:
        st.error("❌ API No Disponible")
        st.caption(f"URL: {api_url}")
    
    st.divider()
    
    # Información del modelo
    st.subheader("📊 Información del Modelo")
    try:
        response = requests.get(f"{api_url}/model/info", timeout=2)
        if response.status_code == 200:
            model_info = response.json()
            st.metric("Versión", model_info.get("model_version", "N/A"))
            st.metric("Features", len(model_info.get("features", [])))
    except:
        st.warning("No se pudo obtener info del modelo")
    
    st.divider()
    
    # Links rápidos
    st.subheader("🔗 Enlaces Rápidos")
    st.markdown("- [Airflow UI](http://localhost:8081)")
    st.markdown("- [API Docs](http://localhost:8000/docs)")
    st.markdown("- [Métricas](http://localhost:8000/dashboard/performance/summary)")

# Contenido principal
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric(
        label="📊 Dashboard",
        value="Ver Análisis",
        help="Visualiza predicciones vs realidad"
    )
    if st.button("Ir al Dashboard 📊", use_container_width=True):
        st.switch_page("pages/1_📊_Dashboard.py")
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric(
        label="📝 Ingresar Datos",
        value="Agregar Registro",
        help="Ingresa nuevos datos de energía"
    )
    if st.button("Ingresar Datos 📝", use_container_width=True):
        st.switch_page("pages/2_📝_Ingresar_Datos.py")
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric(
        label="📈 Análisis",
        value="Ver Insights",
        help="Análisis avanzado de performance"
    )
    if st.button("Ver Análisis 📈", use_container_width=True):
        st.switch_page("pages/3_📈_Análisis.py")
    st.markdown('</div>', unsafe_allow_html=True)

with col4:
    st.markdown('<div class="metric-card">', unsafe_allow_html=True)
    st.metric(
        label="🔮 Predecir Demanda",
        value="Usar Modelo",
        help="Ingresa datos para predecir demanda energética"
    )
    if st.button("Predecir Demanda 🔮", use_container_width=True):
        st.switch_page("pages/3_🔮_Predecir_Demanda.py")
    st.markdown('</div>', unsafe_allow_html=True)

st.divider()

# Últimas predicciones
st.subheader("🔮 Últimas Predicciones")

try:
    response = requests.get(f"{api_url}/dashboard/performance/comparison?hours=24")
    if response.status_code == 200:
        data = response.json()
        
        import pandas as pd
        import plotly.graph_objects as go
        
        df = pd.DataFrame({
            'Timestamp': data['timestamps'],
            'Predicción': data['predicted'],
            'Real': data['actual'],
            'Error': data['errors']
        })
        
        # Gráfico de líneas
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['Timestamp'],
            y=df['Predicción'],
            mode='lines+markers',
            name='Predicción',
            line=dict(color='#1f77b4', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=df['Timestamp'],
            y=df['Real'],
            mode='lines+markers',
            name='Real',
            line=dict(color='#2ca02c', width=2)
        ))
        
        fig.update_layout(
            title="Predicción vs Realidad (Últimas 24 horas)",
            xaxis_title="Timestamp",
            yaxis_title="Energía (MW)",
            hovermode='x unified',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Métricas de error
        col1, col2, col3, col4 = st.columns(4)
        stats = data['statistics']
        
        with col1:
            st.metric("Error Promedio", f"{stats['mean_error']:.2f} MW")
        with col2:
            st.metric("Error Máximo", f"{stats['max_error']:.2f} MW")
        with col3:
            st.metric("Error Mínimo", f"{stats['min_error']:.2f} MW")
        with col4:
            st.metric("Desv. Estándar", f"{stats['std_error']:.2f} MW")
        
    else:
        st.info("No hay datos de predicción disponibles")
        
except Exception as e:
    st.error(f"Error al cargar predicciones: {e}")

# Footer
st.divider()
st.markdown("""
    <div style='text-align: center; color: gray;'>
        <p>🤖 Energy Forecast Agent | Powered by XGBoost + Airflow + FastAPI</p>
        <p>© 2025 - Sistema de Predicción Inteligente</p>
    </div>
""", unsafe_allow_html=True)