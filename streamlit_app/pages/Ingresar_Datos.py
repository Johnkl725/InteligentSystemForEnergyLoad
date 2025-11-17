"""
Página de Ingesta de Datos

Formulario inteligente para ingresar nuevos datos de energía.
El agente valida y procesa automáticamente los datos.
"""

import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import os

st.set_page_config(page_title="Ingresar Datos", page_icon="📝", layout="wide")

# API URL
api_url = os.getenv("API_URL", "http://localhost:8000")

st.title("📝 Ingresar Nuevos Datos de Energía")
st.markdown("### El agente validará y procesará automáticamente tus datos")

# Tabs para diferentes modos de ingesta
tab1, tab2, tab3 = st.tabs(["📝 Registro Individual", "📊 Carga Masiva (CSV)", "📈 Ver Estadísticas"])

# ============================================================
# TAB 1: REGISTRO INDIVIDUAL
# ============================================================
with tab1:
    st.subheader("Ingreso de Registro Individual")
    
    with st.form("energy_data_form", clear_on_submit=True):
        st.markdown("#### 📅 Información Temporal")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fecha = st.date_input(
                "Fecha",
                value=datetime.now().date(),
                max_value=datetime.now().date(),
                help="Fecha del registro (no puede ser futura)"
            )
        
        with col2:
            hora = st.time_input(
                "Hora",
                value=datetime.now().time(),
                help="Hora del registro (formato 24h)"
            )
        
        # Combinar fecha y hora
        timestamp = datetime.combine(fecha, hora)
        
        st.divider()
        
        st.markdown("#### ⚡ Datos de Energía")
        
        energy = st.number_input(
            "Demanda Energética (MW)",
            min_value=0.0,
            value=100.0,
            step=0.1,
            help="Demanda de energía en Megawatts"
        )
        
        st.divider()
        
        st.markdown("#### 🌦️ Variables Meteorológicas")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            t2m = st.number_input(
                "Temperatura Promedio (°C)",
                value=20.0,
                step=0.1,
                help="Temperatura promedio al 2m"
            )
            
            t2m_min = st.number_input(
                "Temperatura Mínima (°C)",
                value=t2m - 5,
                step=0.1,
                help="Opcional: se calculará automáticamente si no se ingresa"
            )
            
            t2m_max = st.number_input(
                "Temperatura Máxima (°C)",
                value=t2m + 5,
                step=0.1,
                help="Opcional: se calculará automáticamente si no se ingresa"
            )
        
        with col2:
            rh2m = st.slider(
                "Humedad Relativa (%)",
                min_value=0,
                max_value=100,
                value=65,
                help="Humedad relativa al 2m"
            )
            
            prectot = st.number_input(
                "Precipitación Total (mm)",
                min_value=0.0,
                value=0.0,
                step=0.1,
                help="Precipitación acumulada"
            )
            
            allsky = st.number_input(
                "Radiación Solar (W/m²)",
                min_value=0.0,
                value=400.0,
                step=1.0,
                help="Radiación solar total"
            )
        
        with col3:
            st.markdown("**Variables Derivadas (Opcionales)**")
            st.caption("Se calcularán automáticamente si no se ingresan")
            
            hdd = st.number_input(
                "HDD18.3",
                value=max(0.0, 18.3 - t2m),
                step=0.1,
                help="Heating Degree Days"
            )
            
            cdd0 = st.number_input(
                "CDD0",
                value=max(0.0, t2m - 0),
                step=0.1,
                help="Cooling Degree Days (base 0)"
            )
            
            cdd10 = st.number_input(
                "CDD10",
                value=max(0.0, t2m - 10),
                step=0.1,
                help="Cooling Degree Days (base 10)"
            )
        
        st.divider()
        
        st.markdown("#### 📆 Variables Calendáricas")
        
        holiday = st.checkbox("Es día festivo", value=False)
        
        # Botón de envío
        col1, col2, col3 = st.columns([2, 1, 2])
        
        with col2:
            submit_button = st.form_submit_button(
                "✅ Enviar Datos",
                use_container_width=True,
                type="primary"
            )
    
    # Procesar el formulario
    if submit_button:
        with st.spinner("🤖 El agente está validando y procesando tus datos..."):
            try:
                # Preparar payload
                payload = {
                    "timestamp": timestamp.isoformat(),
                    "ENERGY": energy,
                    "PRECTOT": prectot,
                    "RH2M": rh2m,
                    "T2M": t2m,
                    "T2M_MIN": t2m_min,
                    "T2M_MAX": t2m_max,
                    "ALLSKY": allsky,
                    "HOLIDAY": 1 if holiday else 0,
                    "HDD18_3": hdd,
                    "CDD0": cdd0,
                    "CDD10": cdd10
                }
                
                # Enviar a la API
                response = requests.post(
                    f"{api_url}/ingestion/submit",
                    json=payload,
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    # Mostrar resultado exitoso
                    st.success(f"✅ {result['message']}")
                    
                    # Mostrar advertencias si las hay
                    if result['validation_warnings']:
                        with st.expander("⚠️ Advertencias de Validación"):
                            for warning in result['validation_warnings']:
                                st.warning(warning)
                    
                    # Mostrar si se triggeó reentrenamiento
                    if result['trigger_retraining']:
                        st.info("🔄 Se ha iniciado el reentrenamiento del modelo debido a la cantidad de datos nuevos")
                    
                    # Mostrar ID del registro
                    st.info(f"📋 ID del registro: {result['record_id']}")
                    
                    # Botón para ver el registro en la BD
                    st.balloons()
                    
                elif response.status_code == 409:
                    st.error("❌ Ya existe un registro para esta fecha y hora")
                
                else:
                    error_detail = response.json().get('detail', 'Error desconocido')
                    st.error(f"❌ Error: {error_detail}")
                    
            except requests.exceptions.Timeout:
                st.error("❌ Timeout: La API no respondió a tiempo")
            except requests.exceptions.ConnectionError:
                st.error("❌ Error de conexión: No se pudo conectar con la API")
            except Exception as e:
                st.error(f"❌ Error inesperado: {e}")

# ============================================================
# TAB 2: CARGA MASIVA
# ============================================================
with tab2:
    st.subheader("Carga Masiva de Datos (CSV)")
    
    st.markdown("""
    📊 **Formato del CSV esperado:**
    
    El archivo debe contener las siguientes columnas:
    - `DATE` (formato: YYYY-MM-DD HH:MM:SS)
    - `ENERGY` (float)
    - `PRECTOT` (float)
    - `RH2M` (float)
    - `T2M` (float)
    - `T2M_MIN` (float, opcional)
    - `T2M_MAX` (float, opcional)
    - `ALLSKY` (float)
    - `HOLIDAY` (0 o 1)
    - `HDD18_3` (float, opcional)
    - `CDD0` (float, opcional)
    - `CDD10` (float, opcional)
    """)
    
    # Descargador de plantilla
    col1, col2 = st.columns([1, 3])
    
    with col1:
        # Crear CSV de ejemplo
        sample_data = {
            'DATE': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            'ENERGY': [100.5],
            'PRECTOT': [0.0],
            'RH2M': [65.0],
            'T2M': [20.0],
            'T2M_MIN': [15.0],
            'T2M_MAX': [25.0],
            'ALLSKY': [400.0],
            'HOLIDAY': [0],
            'HDD18_3': [0.0],
            'CDD0': [20.0],
            'CDD10': [10.0]
        }
        
        sample_df = pd.DataFrame(sample_data)
        csv = sample_df.to_csv(index=False)
        
        st.download_button(
            label="📥 Descargar Plantilla CSV",
            data=csv,
            file_name="plantilla_energy.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    st.divider()
    
    # Upload del archivo
    uploaded_file = st.file_uploader(
        "Selecciona tu archivo CSV",
        type=['csv'],
        help="El archivo será validado antes de ser procesado"
    )
    
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            
            st.success(f"✅ Archivo cargado: {len(df)} registros detectados")
            
            # Previsualización
            with st.expander("👁️ Previsualizar datos"):
                st.dataframe(df.head(10), use_container_width=True)
            
            # Validación básica
            required_cols = ['DATE', 'ENERGY', 'PRECTOT', 'RH2M', 'T2M', 'ALLSKY', 'HOLIDAY']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                st.error(f"❌ Faltan columnas requeridas: {', '.join(missing_cols)}")
            else:
                # Botón para procesar el batch
                if st.button("🚀 Procesar Batch", type="primary", use_container_width=True):
                    with st.spinner(f"🤖 Procesando {len(df)} registros..."):
                        
                        # Convertir DataFrame a lista de dicts
                        records = []
                        for _, row in df.iterrows():
                            record = {
                                "timestamp": row['DATE'],
                                "ENERGY": float(row['ENERGY']),
                                "PRECTOT": float(row['PRECTOT']),
                                "RH2M": float(row['RH2M']),
                                "T2M": float(row['T2M']),
                                "T2M_MIN": float(row.get('T2M_MIN', row['T2M'] - 5)),
                                "T2M_MAX": float(row.get('T2M_MAX', row['T2M'] + 5)),
                                "ALLSKY": float(row['ALLSKY']),
                                "HOLIDAY": int(row['HOLIDAY']),
                                "HDD18_3": float(row.get('HDD18_3', max(0, 18.3 - row['T2M']))),
                                "CDD0": float(row.get('CDD0', max(0, row['T2M']))),
                                "CDD10": float(row.get('CDD10', max(0, row['T2M'] - 10)))
                            }
                            records.append(record)
                        
                        # Enviar batch a la API
                        response = requests.post(
                            f"{api_url}/ingestion/submit_batch",
                            json=records,
                            timeout=60
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric("Total", result['total'])
                            with col2:
                                st.metric("✅ Exitosos", result['success'])
                            with col3:
                                st.metric("❌ Fallidos", result['failed'])
                            
                            if result['failed'] > 0:
                                with st.expander("Ver Errores"):
                                    st.json(result['errors'])
                            
                            st.balloons()
                        else:
                            st.error(f"Error en el batch: {response.text}")
                            
        except Exception as e:
            st.error(f"❌ Error al procesar el archivo: {e}")

# ============================================================
# TAB 3: ESTADÍSTICAS
# ============================================================
with tab3:
    st.subheader("📈 Estadísticas de Datos Ingresados")
    
    try:
        response = requests.get(f"{api_url}/ingestion/stats")
        
        if response.status_code == 200:
            stats = response.json()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Total de Registros", f"{stats['total_records']:,}")
            
            with col2:
                st.metric("Registro Más Antiguo", stats['oldest_record'][:10])
            
            with col3:
                st.metric("Registro Más Reciente", stats['newest_record'][:10])
            
            st.divider()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Energía Promedio", f"{stats['avg_energy']:.2f} MW")
            
            with col2:
                st.metric("Energía Mínima", f"{stats['min_energy']:.2f} MW")
            
            with col3:
                st.metric("Energía Máxima", f"{stats['max_energy']:.2f} MW")
        
        else:
            st.info("No hay estadísticas disponibles")
            
    except Exception as e:
        st.error(f"Error al cargar estadísticas: {e}")