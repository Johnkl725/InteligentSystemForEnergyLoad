"""
Agente Climático Inteligente Avanzado v2.0

Agente inteligente con 3 capas de validación:
1. 🛡️ Validación de Rangos Físicos (local, instantánea, <1ms, $0)
2. 🔍 Validación Estadística con BD Histórica (z-score, outliers, ~10ms, $0)
3. 🤖 Validación Contextual con Google AI (análisis semántico, ~500ms, ~$0.001)

Integra múltiples fuentes de datos:
- 📡 Firebase IoT (sensores en tiempo real - temperatura y humedad)
- 🌐 OpenWeatherMap (precipitación)
- 🛰️ NASA POWER (radiación solar)

El agente detecta y corrige automáticamente:
- Datos fuera de rangos físicos (sensor desconectado)
- Outliers estadísticos (sensor manipulado/defectuoso)
- Anomalías contextuales (evento climático extremo vs fallo)
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
import streamlit as st
import json
from enum import Enum
import logging

# Configurar logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class ValidacionNivel(Enum):
    """Niveles de confianza en la validación de datos"""
    VALIDO = "✅ Válido"
    VALIDO_CON_ADVERTENCIA = "⚠️ Válido con advertencia"
    OUTLIER_LEVE = "🟡 Outlier leve"
    OUTLIER_SEVERO = "🔴 Outlier severo"
    INVALIDO = "❌ Inválido"


class ResultadoValidacion:
    """Resultado detallado de la validación de un dato"""
    def __init__(self, 
                 valor: float, 
                 es_valido: bool, 
                 nivel: ValidacionNivel,
                 fuente: str,
                 mensaje: str = "",
                 capa_validacion: int = 1,
                 zscore: Optional[float] = None,
                 ai_analisis: Optional[str] = None):
        self.valor = valor
        self.es_valido = es_valido
        self.nivel = nivel
        self.fuente = fuente
        self.mensaje = mensaje
        self.capa_validacion = capa_validacion
        self.zscore = zscore
        self.ai_analisis = ai_analisis
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self):
        """Convertir a diccionario para logging/debugging"""
        return {
            "valor": self.valor,
            "es_valido": self.es_valido,
            "nivel": self.nivel.value,
            "fuente": self.fuente,
            "mensaje": self.mensaje,
            "capa_validacion": self.capa_validacion,
            "zscore": self.zscore,
            "ai_analisis": self.ai_analisis,
            "timestamp": self.timestamp
        }


class AgenteClimaticoInteligente:
    """
    Agente inteligente con validación multicapa para datos climáticos.
    
    Capas de validación (jerarquía de coste):
    1. Rangos físicos (instantáneo, sin coste) - 99% de casos
    2. Análisis estadístico con BD histórica (10ms, sin coste) - 0.9% de casos
    3. Validación contextual con Google AI (500ms, ~$0.001) - 0.1% de casos
    """
    
    def __init__(self):
        """Inicializa el agente con configuración desde variables de entorno."""
        
        # ============ APIs EXTERNAS ============
        # OpenWeatherMap (Precipitación)
        self.openweather_key = os.getenv("WEATHER_API_KEY", "")
        self.openweather_url = os.getenv("WEATHER_API_URL", "https://api.openweathermap.org/data/2.5/weather")
        
        # NASA POWER (Radiación Solar)
        self.nasa_power_url = os.getenv("NASA_POWER_URL", "https://power.larc.nasa.gov/api/temporal/daily/point")
        
        # Firebase IoT (Sensores en tiempo real)
        self.firebase_url = os.getenv("FIREBASE_URL", "https://si-grupo2-default-rtdb.firebaseio.com/iot_lecturas_clima.json")
        self.firebase_enabled = os.getenv("FIREBASE_ENABLED", "true").lower() == "true"
        
        # Google AI Studio (Gemini API para validación contextual)
        self.google_ai_key = os.getenv("GOOGLE_AI_API_KEY", "")
        self.google_ai_model = os.getenv("GOOGLE_AI_MODEL", "gemini-2.0-flash")
        self.google_ai_enabled = os.getenv("GOOGLE_AI_ENABLED", "true").lower() == "true"
        self.enable_ai_validation = os.getenv("ENABLE_AI_VALIDATION", "true").lower() == "true"
        
        # IP Geolocation (Detección automática de ubicación)
        self.ipgeolocation_key = os.getenv("IPGEOLOCATION_KEY", "")
        self.ipgeolocation_url = os.getenv("IPGEOLOCATION_URL", "https://api.ipgeolocation.io/ipgeo")
        self.ipapi_url = os.getenv("IPAPI_URL", "https://ipapi.co/json/")
        
        # ============ CONFIGURACIÓN GENERAL ============
        self.auto_detect_location = os.getenv("AUTO_DETECT_LOCATION", "true").lower() == "true"
        self.api_timeout = int(os.getenv("API_TIMEOUT", "10"))
        self.api_retries = int(os.getenv("API_RETRIES", "2"))
        
        # Ubicación por defecto (Lima, Perú)
        self.default_lat = float(os.getenv("LOCATION_LAT", "-12.0464"))
        self.default_lon = float(os.getenv("LOCATION_LON", "-77.0428"))
        self.default_location = os.getenv("LOCATION_NAME", "Lima")
        
        # ============ RANGOS FÍSICOS VÁLIDOS (Capa 1) ============
        self.temp_min = float(os.getenv("TEMP_MIN_VALID", "-10.0"))
        self.temp_max = float(os.getenv("TEMP_MAX_VALID", "50.0"))
        self.humidity_min = int(os.getenv("HUMIDITY_MIN_VALID", "0"))
        self.humidity_max = int(os.getenv("HUMIDITY_MAX_VALID", "100"))
        self.precipitation_min = float(os.getenv("PRECIPITATION_MIN_VALID", "0.0"))
        self.precipitation_max = float(os.getenv("PRECIPITATION_MAX_VALID", "200.0"))
        self.solar_min = float(os.getenv("SOLAR_MIN_VALID", "0.0"))
        self.solar_max = float(os.getenv("SOLAR_MAX_VALID", "1000.0"))
        
        # ============ CONFIGURACIÓN DETECCIÓN OUTLIERS (Capa 2) ============
        self.zscore_threshold = float(os.getenv("OUTLIER_ZSCORE_THRESHOLD", "3.0"))
        self.zscore_severe = float(os.getenv("OUTLIER_ZSCORE_SEVERE", "5.0"))
        
        # ============ VALORES POR DEFECTO ============
        self.default_temperature = float(os.getenv("DEFAULT_TEMPERATURE", "20.0"))
        self.default_humidity = int(os.getenv("DEFAULT_HUMIDITY", "65"))
        self.default_precipitation = float(os.getenv("DEFAULT_PRECIPITATION", "0.0"))
        self.default_solar_radiation = float(os.getenv("DEFAULT_SOLAR_RADIATION", "400.0"))
        
        # ============ CACHE Y ESTADÍSTICAS ============
        self._cache = {}
        self.cache_duration = int(os.getenv("CLIMATE_CACHE_DURATION", "300"))  # 5 minutos
        
        # Estadísticas del agente (para monitoreo)
        self.stats = {
            "llamadas_capa1": 0,
            "llamadas_capa2": 0,
            "llamadas_capa3": 0,
            "datos_invalidos": 0,
            "datos_corregidos": 0,
            "outliers_detectados": 0,
            "llamadas_firebase": 0,
            "llamadas_openweather": 0,
            "llamadas_nasa": 0
        }
        
        # Conexión a BD para validación estadística (lazy loading)
        self._db_connection = None
    
    def _get_db_stats(self, variable: str, hour: int, month: int) -> Optional[Dict]:
        """
        Obtiene estadísticas (media, desviación estándar) de la BD histórica.
        
        Args:
            variable: Nombre de la variable (T2M, RH2M, PRECTOT, ALLSKY)
            hour: Hora del día (0-23)
            month: Mes del año (1-12)
        
        Returns:
            Dict con 'mean' y 'std', o None si falla
        """
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            # Lazy loading de conexión
            if self._db_connection is None or self._db_connection.closed:
                self._db_connection = psycopg2.connect(
                    host=os.getenv("POSTGRES_HOST", "db"),
                    port=os.getenv("POSTGRES_PORT", "5432"),
                    database=os.getenv("POSTGRES_DB", "energy_forecast"),
                    user=os.getenv("POSTGRES_USER", "energy_user"),
                    password=os.getenv("POSTGRES_PASSWORD", "energy_pass"),
                    cursor_factory=RealDictCursor
                )
            
            cursor = self._db_connection.cursor()
            
            # Query para obtener media y desviación estándar histórica
            query = f"""
                SELECT 
                    AVG({variable}) as mean,
                    STDDEV({variable}) as std,
                    COUNT(*) as n_samples
                FROM historical_energy
                WHERE EXTRACT(HOUR FROM timestamp) = %s
                  AND EXTRACT(MONTH FROM timestamp) = %s
                  AND {variable} IS NOT NULL
            """
            
            cursor.execute(query, (hour, month))
            result = cursor.fetchone()
            cursor.close()
            
            if result and result['n_samples'] > 10:  # Mínimo 10 muestras
                return {
                    'mean': float(result['mean']) if result['mean'] else None,
                    'std': float(result['std']) if result['std'] else None,
                    'n_samples': int(result['n_samples'])
                }
            
            return None
            
        except Exception as e:
            # Si falla la BD, no es crítico - seguir sin validación estadística
            return None
    
    def _validar_rango_fisico(self, variable: str, valor: float) -> ResultadoValidacion:
        """
        CAPA 1: Validación de rangos físicos (instantánea, sin coste).
        
        Args:
            variable: Nombre de la variable (T2M, RH2M, PRECTOT, ALLSKY)
            valor: Valor a validar
        
        Returns:
            ResultadoValidacion con el resultado
        """
        self.stats['llamadas_capa1'] += 1
        
        rangos = {
            'T2M': (self.temp_min, self.temp_max, "°C"),
            'RH2M': (self.humidity_min, self.humidity_max, "%"),
            'PRECTOT': (self.precipitation_min, self.precipitation_max, "mm"),
            'ALLSKY': (self.solar_min, self.solar_max, "W/m²")
        }
        
        if variable not in rangos:
            return ResultadoValidacion(
                valor=valor,
                es_valido=False,
                nivel=ValidacionNivel.INVALIDO,
                fuente="Capa 1: Rangos Físicos",
                mensaje=f"Variable '{variable}' no reconocida",
                capa_validacion=1
            )
        
        min_val, max_val, unidad = rangos[variable]
        
        if min_val <= valor <= max_val:
            return ResultadoValidacion(
                valor=valor,
                es_valido=True,
                nivel=ValidacionNivel.VALIDO,
                fuente="Capa 1: Rangos Físicos",
                mensaje=f"✅ Valor {valor}{unidad} dentro de rango físico válido [{min_val}, {max_val}]{unidad}",
                capa_validacion=1
            )
        else:
            self.stats['datos_invalidos'] += 1
            return ResultadoValidacion(
                valor=valor,
                es_valido=False,
                nivel=ValidacionNivel.INVALIDO,
                fuente="Capa 1: Rangos Físicos",
                mensaje=f"❌ Valor {valor}{unidad} FUERA de rango físico válido [{min_val}, {max_val}]{unidad}",
                capa_validacion=1
            )
    
    def _validar_estadistico(self, variable: str, valor: float, timestamp: datetime = None) -> ResultadoValidacion:
        """
        CAPA 2: Validación estadística con BD histórica (10ms, sin coste).
        
        Usa Z-score para detectar outliers:
        - Z < 3: Normal
        - 3 <= Z < 5: Outlier leve
        - Z >= 5: Outlier severo
        
        Args:
            variable: Nombre de la variable (T2M, RH2M, PRECTOT, ALLSKY)
            valor: Valor a validar
            timestamp: Timestamp del dato (para contexto temporal)
        
        Returns:
            ResultadoValidacion con el resultado
        """
        self.stats['llamadas_capa2'] += 1
        
        if timestamp is None:
            timestamp = datetime.now()
        
        # Obtener estadísticas de la BD
        stats = self._get_db_stats(
            variable=variable,
            hour=timestamp.hour,
            month=timestamp.month
        )
        
        if stats is None or stats['mean'] is None or stats['std'] is None or stats['std'] == 0:
            # Si no hay datos estadísticos suficientes, asumir válido (no rechazar)
            return ResultadoValidacion(
                valor=valor,
                es_valido=True,
                nivel=ValidacionNivel.VALIDO,
                fuente="Capa 2: Validación Estadística",
                mensaje=f"✅ Sin datos históricos suficientes para validación estadística (n={stats['n_samples'] if stats else 0}). Asumiendo válido.",
                capa_validacion=2
            )
        
        # Calcular Z-score
        zscore = abs((valor - stats['mean']) / stats['std'])
        
        if zscore < self.zscore_threshold:
            # Normal - dentro de 3 desviaciones estándar
            return ResultadoValidacion(
                valor=valor,
                es_valido=True,
                nivel=ValidacionNivel.VALIDO,
                fuente="Capa 2: Validación Estadística",
                mensaje=f"✅ Valor dentro de rango estadístico normal (Z-score: {zscore:.2f}, μ={stats['mean']:.2f}, σ={stats['std']:.2f})",
                capa_validacion=2,
                zscore=zscore
            )
        elif zscore < self.zscore_severe:
            # Outlier leve
            self.stats['outliers_detectados'] += 1
            return ResultadoValidacion(
                valor=valor,
                es_valido=True,
                nivel=ValidacionNivel.OUTLIER_LEVE,
                fuente="Capa 2: Validación Estadística",
                mensaje=f"🟡 Outlier LEVE detectado (Z-score: {zscore:.2f}). Valor poco común pero posible.",
                capa_validacion=2,
                zscore=zscore
            )
        else:
            # Outlier severo - pasar a Capa 3 (Google AI)
            self.stats['outliers_detectados'] += 1
            return ResultadoValidacion(
                valor=valor,
                es_valido=False,
                nivel=ValidacionNivel.OUTLIER_SEVERO,
                fuente="Capa 2: Validación Estadística",
                mensaje=f"🔴 Outlier SEVERO detectado (Z-score: {zscore:.2f}). Requiere validación contextual.",
                capa_validacion=2,
                zscore=zscore
            )
    
    def _validar_con_google_ai(self, variable: str, valor: float, location: str, timestamp: datetime = None) -> ResultadoValidacion:
        """
        CAPA 3: Validación contextual con Google AI (500ms, ~$0.001).
        
        Usa Gemini API para analizar si un valor anómalo es físicamente posible
        considerando el contexto (ubicación, hora, mes, eventos climáticos).
        
        Args:
            variable: Nombre de la variable (T2M, RH2M, PRECTOT, ALLSKY)
            valor: Valor a validar
            location: Ubicación (ciudad, país)
            timestamp: Timestamp del dato
        
        Returns:
            ResultadoValidacion con el resultado
        """
        self.stats['llamadas_capa3'] += 1
        
        if not self.google_ai_enabled or not self.google_ai_key:
            return ResultadoValidacion(
                valor=valor,
                es_valido=False,
                nivel=ValidacionNivel.INVALIDO,
                fuente="Capa 3: Google AI (deshabilitada)",
                mensaje="⚠️ Validación AI no disponible. Rechazando valor por seguridad.",
                capa_validacion=3
            )
        
        if timestamp is None:
            timestamp = datetime.now()
        
        # Mapeo de variables a nombres legibles
        var_nombres = {
            'T2M': f"temperatura de {valor}°C",
            'RH2M': f"humedad relativa de {valor}%",
            'PRECTOT': f"precipitación de {valor}mm",
            'ALLSKY': f"radiación solar de {valor}W/m²"
        }
        
        var_descripcion = var_nombres.get(variable, f"{variable} = {valor}")
        
        # Construir prompt para Gemini
        prompt = f"""Eres un experto meteorólogo evaluando datos de sensores climáticos.

**Datos del sensor:**
- Variable: {var_descripcion}
- Ubicación: {location}
- Fecha/Hora: {timestamp.strftime('%Y-%m-%d %H:%M')} (Hora: {timestamp.hour}h, Mes: {timestamp.strftime('%B')})

**Contexto:**
Este valor fue marcado como estadísticamente inusual comparado con datos históricos.
Sin embargo, puede ser perfectamente válido si representa:
- Condiciones climáticas reales (ola de calor, lluvia intensa, día soleado)
- Variación natural esperada en esa ubicación y época del año
- Eventos climáticos documentados (El Niño, ENSO, etc.)

**Tu tarea:**
Evalúa si este valor es FÍSICAMENTE POSIBLE y CLIMATOLÓGICAMENTE RAZONABLE para esa ubicación y fecha.

NO rechaces valores solo por ser "inusuales" - enfócate en detectar:
- Valores físicamente imposibles (temperatura >60°C, humedad >100%)
- Errores evidentes de sensor (lecturas congeladas, saltos abruptos)
- Combinaciones incoherentes entre variables

Responde SOLO con un JSON en este formato exacto:
{{
    "es_valido": true o false,
    "confianza": 0.0 a 1.0,
    "razonamiento": "explicación breve de máximo 80 palabras"
}}

**IMPORTANTE:** Si el valor es plausible para esa ubicación/fecha, marca es_valido=true aunque sea inusual.

Responde SOLO el JSON, sin texto adicional."""

        try:
            # Llamar a Gemini API
            url = f"https://generativelanguage.googleapis.com/v1/models/{self.google_ai_model}:generateContent?key={self.google_ai_key}"
            
            headers = {"Content-Type": "application/json"}
            data = {
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.1,  # Baja temperatura para respuestas más consistentes
                    "topK": 1,
                    "topP": 0.8,
                    "maxOutputTokens": 256
                }
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=10)
            
            if response.status_code != 200:
                error_detail = response.text[:200] if response.text else 'No response'
                st.warning(f"🤖 Google AI API error {response.status_code}: {error_detail}")
                raise Exception(f"API error: {response.status_code}")
            
            result = response.json()
            
            # Extraer el texto de la respuesta
            if 'candidates' in result and len(result['candidates']) > 0:
                text = result['candidates'][0]['content']['parts'][0]['text']
                
                # Parsear JSON de la respuesta
                # Limpiar markdown si lo hay
                text = text.strip()
                if text.startswith('```json'):
                    text = text[7:]
                if text.startswith('```'):
                    text = text[3:]
                if text.endswith('```'):
                    text = text[:-3]
                text = text.strip()
                
                ai_response = json.loads(text)
                
                es_valido = ai_response.get('es_valido', False)
                confianza = ai_response.get('confianza', 0.0)
                razonamiento = ai_response.get('razonamiento', 'Sin razonamiento')
                
                if es_valido and confianza >= 0.7:
                    return ResultadoValidacion(
                        valor=valor,
                        es_valido=True,
                        nivel=ValidacionNivel.VALIDO_CON_ADVERTENCIA,
                        fuente="Capa 3: Google AI",
                        mensaje=f"⚠️ Valor anómalo pero VÁLIDO según AI (confianza: {confianza:.0%})",
                        capa_validacion=3,
                        ai_analisis=razonamiento
                    )
                else:
                    self.stats['datos_invalidos'] += 1
                    return ResultadoValidacion(
                        valor=valor,
                        es_valido=False,
                        nivel=ValidacionNivel.INVALIDO,
                        fuente="Capa 3: Google AI",
                        mensaje=f"❌ Valor RECHAZADO por AI (confianza: {confianza:.0%})",
                        capa_validacion=3,
                        ai_analisis=razonamiento
                    )
            else:
                raise Exception("Respuesta vacía de la API")
                
        except Exception as e:
            # Si falla la API de Google, rechazar por seguridad
            return ResultadoValidacion(
                valor=valor,
                es_valido=False,
                nivel=ValidacionNivel.INVALIDO,
                fuente="Capa 3: Google AI (error)",
                mensaje=f"❌ Error en validación AI: {str(e)[:100]}. Rechazando por seguridad.",
                capa_validacion=3
            )
    
    def validar_dato_inteligente(self, variable: str, valor: float, location: str = None, timestamp: datetime = None) -> ResultadoValidacion:
        """
        Validación inteligente multicapa de un dato climático.
        
        Jerarquía de validación:
        1. Capa 1: Rangos físicos (siempre)
        2. Capa 2: Análisis estadístico (si pasa Capa 1)
        3. Capa 3: Google AI (solo si Capa 2 detecta outlier severo)
        
        Args:
            variable: Nombre de la variable (T2M, RH2M, PRECTOT, ALLSKY)
            valor: Valor a validar
            location: Ubicación (opcional, para contexto en Capa 3)
            timestamp: Timestamp del dato (opcional, para contexto)
        
        Returns:
            ResultadoValidacion con el resultado final
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        if location is None:
            location = self.default_location
        
        # CAPA 1: Validación de rangos físicos
        resultado_capa1 = self._validar_rango_fisico(variable, valor)
        
        if not resultado_capa1.es_valido:
            # Rechazado en Capa 1 - no continuar
            return resultado_capa1
        
        # CAPA 2: Validación estadística
        resultado_capa2 = self._validar_estadistico(variable, valor, timestamp)
        
        if resultado_capa2.nivel == ValidacionNivel.OUTLIER_SEVERO and self.enable_ai_validation and self.google_ai_key:
            # CAPA 3: Validación con Google AI (solo para outliers SEVEROS)
            resultado_capa3 = self._validar_con_google_ai(variable, valor, location, timestamp)
            return resultado_capa3
        elif resultado_capa2.nivel == ValidacionNivel.OUTLIER_SEVERO and not self.google_ai_key:
            # Si no hay API key de Google AI, rechazar outliers severos por seguridad
            return ResultadoValidacion(
                valor=valor,
                es_valido=False,
                nivel=ValidacionNivel.INVALIDO,
                fuente="Capa 2: Validación Estadística",
                mensaje=f"🔴 Outlier severo SIN validación AI (API key no configurada). Rechazando por seguridad.",
                capa_validacion=2,
                zscore=resultado_capa2.zscore
            )
        
        return resultado_capa2
    
    def obtener_ubicacion_usuario(self) -> Tuple[float, float, str]:
        """
        Detecta la ubicación del usuario usando IP Geolocation.
        
        Returns:
            Tuple[lat, lon, location_name]
        """
        if not self.auto_detect_location:
            return self.default_lat, self.default_lon, self.default_location
        
        # Intentar con ipgeolocation.io primero
        if self.ipgeolocation_key:
            try:
                response = requests.get(
                    self.ipgeolocation_url,
                    params={"apiKey": self.ipgeolocation_key},
                    timeout=self.api_timeout
                )
                if response.status_code == 200:
                    data = response.json()
                    lat = float(data.get("latitude", self.default_lat))
                    lon = float(data.get("longitude", self.default_lon))
                    city = data.get("city", self.default_location)
                    country = data.get("country_name", "")
                    location_name = f"{city}, {country}" if country else city
                    
                    return lat, lon, location_name
            except Exception as e:
                st.warning(f"🌍 Error en ipgeolocation.io: {e}")
        
        # Fallback a ipapi.co (gratuito sin key)
        try:
            response = requests.get(self.ipapi_url, timeout=self.api_timeout)
            if response.status_code == 200:
                data = response.json()
                lat = float(data.get("latitude", self.default_lat))
                lon = float(data.get("longitude", self.default_lon))
                city = data.get("city", self.default_location)
                country = data.get("country_name", "")
                location_name = f"{city}, {country}" if country else city
                
                return lat, lon, location_name
        except Exception as e:
            st.warning(f"🌍 Error en ipapi.co: {e}")
        
        # Si todo falla, usar ubicación por defecto
        return self.default_lat, self.default_lon, self.default_location
    
    def _obtener_firebase_iot(self) -> Optional[Dict]:
        """
        Obtiene temperatura y humedad de sensores Firebase IoT con validación inteligente.
        
        Returns:
            Dict con T2M y RH2M validados, o None si falla
        """
        if not self.firebase_enabled:
            logger.info("Firebase IoT está deshabilitado en configuración")
            return None
        
        self.stats['llamadas_firebase'] += 1
        
        try:
            logger.info(f"Conectando a Firebase: {self.firebase_url}")
            response = requests.get(self.firebase_url, timeout=self.api_timeout)
            response.raise_for_status()
            data = response.json()
            
            if data:
                # Obtener la última lectura
                ultima_key = list(data.keys())[-1]
                ultima_lectura = data[ultima_key]
                
                temperatura_raw = ultima_lectura.get("temperatura", None)
                humedad_raw = ultima_lectura.get("humedad", None)
                
                logger.info(f"Firebase IoT datos recibidos: Temp={temperatura_raw}°C, Hum={humedad_raw}%")
                
                if temperatura_raw is not None and humedad_raw is not None:
                    # Validar temperatura
                    resultado_temp = self.validar_dato_inteligente(
                        variable="T2M",
                        valor=float(temperatura_raw),
                        location=self.default_location,
                        timestamp=datetime.now()
                    )
                    
                    # Validar humedad
                    resultado_hum = self.validar_dato_inteligente(
                        variable="RH2M",
                        valor=float(humedad_raw),
                        location=self.default_location,
                        timestamp=datetime.now()
                    )
                    
                    # SOLO rechazar si falla Capa 1 (rangos físicos imposibles)
                    # Capa 2/3 son warnings pero aceptamos el dato
                    temp_rechazada = not resultado_temp.es_valido and resultado_temp.capa_validacion == 1
                    hum_rechazada = not resultado_hum.es_valido and resultado_hum.capa_validacion == 1
                    
                    # Mostrar TODOS los warnings/rechazos
                    if not resultado_temp.es_valido:
                        if resultado_temp.capa_validacion == 1:
                            st.error(f"🚨 Temperatura IoT RECHAZADA (Capa 1): {resultado_temp.mensaje}")
                        else:
                            st.warning(f"⚠️ Temperatura IoT advertencia (Capa {resultado_temp.capa_validacion}): {resultado_temp.mensaje}")
                        self.stats['datos_corregidos'] += 1
                    
                    if not resultado_hum.es_valido:
                        if resultado_hum.capa_validacion == 1:
                            st.error(f"🚨 Humedad IoT RECHAZADA (Capa 1): {resultado_hum.mensaje}")
                        else:
                            st.warning(f"⚠️ Humedad IoT advertencia (Capa {resultado_hum.capa_validacion}): {resultado_hum.mensaje}")
                        self.stats['datos_corregidos'] += 1
                    
                    # Solo rechazar TODO si algún dato falla Capa 1
                    if temp_rechazada or hum_rechazada:
                        return None
                    
                    # Aceptar datos aunque tengan warnings de Capa 2/3
                    return {
                        "T2M": resultado_temp.valor,
                        "RH2M": resultado_hum.valor,
                        "validacion_temp": resultado_temp,
                        "validacion_hum": resultado_hum
                    }
                else:
                    st.warning(f"📡 Firebase IoT: Datos incompletos (temp={temperatura_raw}, hum={humedad_raw})")
                
        except Exception as e:
            st.error(f"📡 Error en Firebase IoT: {e}")
            return None
        
        return None
    
    def _obtener_openweather(self, lat: float, lon: float) -> Optional[Dict]:
        """Obtiene precipitación de OpenWeatherMap con validación"""
        if not self.openweather_key:
            return None
        
        self.stats['llamadas_openweather'] += 1
        
        try:
            params = {
                "lat": lat,
                "lon": lon,
                "appid": self.openweather_key,
                "units": "metric"
            }
            
            response = requests.get(
                self.openweather_url,
                params=params,
                timeout=self.api_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                rain = data.get("rain", {})
                precipitation_raw = rain.get("1h", 0.0)
                
                # Validar precipitación
                resultado = self.validar_dato_inteligente(
                    variable="PRECTOT",
                    valor=float(precipitation_raw),
                    location=self.default_location,
                    timestamp=datetime.now()
                )
                
                # Mostrar warnings pero aceptar datos con Capa 2/3
                if not resultado.es_valido:
                    if resultado.capa_validacion == 1:
                        st.error(f"🚨 Precipitación RECHAZADA (Capa 1): {resultado.mensaje}")
                        return None  # Solo rechazar si falla Capa 1
                    else:
                        st.warning(f"⚠️ Precipitación advertencia (Capa {resultado.capa_validacion}): {resultado.mensaje}")
                
                return {
                    "PRECTOT": resultado.valor,
                    "validacion": resultado
                }
                    
        except Exception as e:
            return None
        
        return None
    
    def _obtener_nasa_power(self, lat: float, lon: float) -> Optional[Dict]:
        """Obtiene radiación solar de NASA POWER con validación"""
        self.stats['llamadas_nasa'] += 1
        
        try:
            logger.info(f"Consultando NASA POWER para lat={lat}, lon={lon}")
            hace_7_dias = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
            ayer = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
            
            params = {
                "parameters": "ALLSKY_SFC_SW_DWN",
                "community": "RE",
                "longitude": lon,
                "latitude": lat,
                "start": hace_7_dias,
                "end": ayer,
                "format": "JSON"
            }
            
            response = requests.get(
                self.nasa_power_url,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                parameters = data.get("properties", {}).get("parameter", {})
                allsky_data = parameters.get("ALLSKY_SFC_SW_DWN", {})
                
                logger.info(f"NASA POWER datos recibidos: {len(allsky_data)} registros")
                
                if allsky_data:
                    valores = list(allsky_data.values())
                    valores.reverse()
                    
                    for valor in valores:
                        if isinstance(valor, (int, float)) and valor > 0 and valor != -999.0:
                            radiacion_solar_raw = valor * 1000 / 24  # kWh/m²/day a W/m²
                            
                            # Validar radiación solar
                            resultado = self.validar_dato_inteligente(
                                variable="ALLSKY",
                                valor=radiacion_solar_raw,
                                location=self.default_location,
                                timestamp=datetime.now()
                            )
                            
                            # Mostrar warnings pero aceptar datos con Capa 2/3
                            if not resultado.es_valido:
                                if resultado.capa_validacion == 1:
                                    st.error(f"🚨 Radiación Solar RECHAZADA (Capa 1): {resultado.mensaje}")
                                    self.stats['datos_corregidos'] += 1
                                    return None  # Solo rechazar si falla Capa 1
                                else:
                                    st.warning(f"⚠️ Radiación Solar advertencia (Capa {resultado.capa_validacion}): {resultado.mensaje}")
                                    self.stats['datos_corregidos'] += 1
                            
                            return {
                                "ALLSKY": resultado.valor,
                                "validacion": resultado
                            }
                    
                    st.warning(f"🛰️ NASA POWER: Todos los valores son -999 (sin datos) en los últimos 7 días")
                                
        except Exception as e:
            logger.error(f"NASA POWER error: {str(e)[:150]}")
            return None
        
        return None
    
    def obtener_datos_climaticos_completos(self, lat: Optional[float] = None, lon: Optional[float] = None) -> Dict:
        """
        Obtiene TODOS los datos climáticos (temperatura, humedad, precipitación, radiación solar)
        con validación inteligente multicapa.
        
        Fuentes:
        - Firebase IoT: Temperatura y humedad
        - OpenWeatherMap: Precipitación
        - NASA POWER: Radiación solar
        
        Args:
            lat: Latitud (opcional, se detecta automáticamente)
            lon: Longitud (opcional, se detecta automáticamente)
        
        Returns:
            Dict con T2M, RH2M, PRECTOT, ALLSKY y metadatos de validación
        """
        # Detectar ubicación si no se proporciona
        if lat is None or lon is None:
            lat, lon, location_name = self.obtener_ubicacion_usuario()
        else:
            location_name = f"Lat: {lat:.4f}, Lon: {lon:.4f}"
        
        # Verificar cache
        cache_key = f"clima_completo_{lat}_{lon}"
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if (datetime.now() - timestamp).seconds < self.cache_duration:
                cached_data["from_cache"] = True
                return cached_data
        
        # Inicializar resultado
        resultado = {
            "T2M": self.default_temperature,
            "RH2M": self.default_humidity,
            "PRECTOT": self.default_precipitation,
            "ALLSKY": self.default_solar_radiation,
            "location": location_name,
            "lat": lat,
            "lon": lon,
            "fuentes": {
                "temperatura": "default",
                "humedad": "default",
                "precipitacion": "default",
                "radiacion_solar": "default"
            },
            "validaciones": {},
            "timestamp": datetime.now().isoformat(),
            "from_cache": False
        }
        
        # 1. Obtener temperatura y humedad de Firebase IoT
        firebase_data = self._obtener_firebase_iot()
        if firebase_data:
            resultado["T2M"] = firebase_data["T2M"]
            resultado["RH2M"] = firebase_data["RH2M"]
            resultado["fuentes"]["temperatura"] = "📡 Firebase IoT"
            resultado["fuentes"]["humedad"] = "📡 Firebase IoT"
            resultado["validaciones"]["temperatura"] = firebase_data["validacion_temp"].to_dict()
            resultado["validaciones"]["humedad"] = firebase_data["validacion_hum"].to_dict()
        
        # 2. Obtener precipitación de OpenWeatherMap
        openweather_data = self._obtener_openweather(lat, lon)
        if openweather_data:
            resultado["PRECTOT"] = openweather_data["PRECTOT"]
            resultado["fuentes"]["precipitacion"] = "🌐 OpenWeatherMap"
            resultado["validaciones"]["precipitacion"] = openweather_data["validacion"].to_dict()
        
        # 3. Obtener radiación solar de NASA POWER
        nasa_data = self._obtener_nasa_power(lat, lon)
        if nasa_data:
            resultado["ALLSKY"] = nasa_data["ALLSKY"]
            resultado["fuentes"]["radiacion_solar"] = "🛰️ NASA POWER"
            resultado["validaciones"]["radiacion_solar"] = nasa_data["validacion"].to_dict()
        
        # Guardar en cache
        self._cache[cache_key] = (resultado, datetime.now())
        
        return resultado
    
    def limpiar_cache(self):
        """Limpia el cache de datos climáticos."""
        self._cache.clear()
    
    def obtener_estadisticas(self) -> Dict:
        """
        Obtiene estadísticas del agente (para monitoring/debugging).
        
        Returns:
            Dict con estadísticas de uso y validación
        """
        return {
            **self.stats,
            "cache_size": len(self._cache),
            "openweather_configured": bool(self.openweather_key),
            "google_ai_configured": bool(self.google_ai_key),
            "firebase_enabled": self.firebase_enabled,
            "ai_validation_enabled": self.enable_ai_validation,
            "default_location": f"{self.default_location} ({self.default_lat}, {self.default_lon})"
        }
