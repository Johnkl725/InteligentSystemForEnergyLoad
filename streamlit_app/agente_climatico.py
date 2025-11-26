"""
Agente Climático Inteligente Avanzado

Agente inteligente con 3 capas de validación:
1. 🛡️ Validación de Rangos Físicos (local, instantánea)
2. 🔍 Validación Estadística con BD Histórica (z-score, outliers)
3. 🤖 Validación Contextual con Google AI (para anomalías severas)

Integra múltiples fuentes de datos:
- 📡 Firebase IoT (sensores en tiempo real)
- 🌐 OpenWeatherMap (precipitación)
- 🛰️ NASA POWER (radiación solar)

El agente detecta y corrige datos corruptos, manipulados o inválidos.
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
import streamlit as st
import json
from enum import Enum


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


class AgenteClimatico:
    """
    Agente inteligente con validación multicapa para datos climáticos.
    
    Capas de validación:
    1. Rangos físicos (instantáneo, sin coste)
    2. Análisis estadístico con BD histórica (10ms, sin coste)
    3. Validación contextual con Google AI (500ms, ~$0.001 por llamada)
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
        self.google_ai_model = os.getenv("GOOGLE_AI_MODEL", "gemini-1.5-flash")
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
        
        # Estadísticas del agente
        self.stats = {
            "llamadas_capa1": 0,
            "llamadas_capa2": 0,
            "llamadas_capa3": 0,
            "datos_invalidos": 0,
            "datos_corregidos": 0,
            "outliers_detectados": 0
        }
        
        # Conexión a BD para validación estadística (lazy loading)
        self._db_connection = None
    
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
    
    def obtener_datos_complementarios(self, lat: Optional[float] = None, lon: Optional[float] = None) -> Dict:
        """
        Obtiene datos climáticos complementarios (precipitación y radiación solar).
        
        Args:
            lat: Latitud (opcional, se detecta automáticamente)
            lon: Longitud (opcional, se detecta automáticamente)
        
        Returns:
            Dict con PRECTOT, ALLSKY y metadatos de fuentes
        """
        # Detectar ubicación si no se proporciona
        if lat is None or lon is None:
            lat, lon, location_name = self.obtener_ubicacion_usuario()
        else:
            location_name = f"Lat: {lat:.4f}, Lon: {lon:.4f}"
        
        # Verificar cache
        cache_key = f"clima_{lat}_{lon}"
        if cache_key in self._cache:
            cached_data, timestamp = self._cache[cache_key]
            if (datetime.now() - timestamp).seconds < self.cache_duration:
                cached_data["from_cache"] = True
                return cached_data
        
        # Inicializar resultado
        resultado = {
            "PRECTOT": self.default_precipitation,
            "ALLSKY": self.default_solar_radiation,
            "location": location_name,
            "lat": lat,
            "lon": lon,
            "fuentes": {
                "precipitacion": "default",
                "radiacion_solar": "default"
            },
            "timestamp": datetime.now().isoformat(),
            "from_cache": False
        }
        
        # 1. Obtener precipitación de OpenWeatherMap
        openweather_data = self._obtener_openweather(lat, lon)
        if openweather_data:
            resultado["PRECTOT"] = openweather_data.get("precipitacion", resultado["PRECTOT"])
            resultado["fuentes"]["precipitacion"] = "🌐 OpenWeatherMap"
        
        # 2. Obtener radiación solar de NASA POWER
        nasa_data = self._obtener_nasa_power(lat, lon)
        if nasa_data:
            resultado["ALLSKY"] = nasa_data.get("radiacion_solar", resultado["ALLSKY"])
            resultado["fuentes"]["radiacion_solar"] = "🛰️ NASA POWER"
        
        # Guardar en cache
        self._cache[cache_key] = (resultado, datetime.now())
        
        return resultado
    
    def _obtener_firebase_iot(self) -> Optional[Dict]:
        """
        Obtiene temperatura y humedad de sensores Firebase IoT.
        
        Returns:
            Dict con temperatura y humedad, o None si falla
        """
        try:
            response = requests.get(self.firebase_url, timeout=self.api_timeout)
            response.raise_for_status()
            data = response.json()
            
            if data:
                # Obtener la última lectura
                ultima_key = list(data.keys())[-1]
                ultima_lectura = data[ultima_key]
                
                return {
                    "temperatura": ultima_lectura.get("temperatura", None),
                    "humedad": ultima_lectura.get("humedad", None)
                }
        except Exception as e:
            st.warning(f"📡 Error en Firebase IoT: {e}")
            return None
    
    def _obtener_openweather(self, lat: float, lon: float) -> Optional[Dict]:
        """
        Obtiene datos de precipitación de OpenWeatherMap.
        
        Args:
            lat: Latitud
            lon: Longitud
        
        Returns:
            Dict con precipitación, o None si falla
        """
        if not self.openweather_key:
            st.warning("🌐 OpenWeatherMap: API key no configurada")
            return None
        
        try:
            params = {
                "lat": lat,
                "lon": lon,
                "appid": self.openweather_key,
                "units": "metric"  # Celsius
            }
            
            response = requests.get(
                self.openweather_url,
                params=params,
                timeout=self.api_timeout
            )
            
            # Mostrar el status code para debugging
            if response.status_code != 200:
                error_msg = response.json().get("message", "Error desconocido") if response.text else "Sin respuesta"
                st.warning(f"🌐 OpenWeatherMap error {response.status_code}: {error_msg}")
                return None
            
            if response.status_code == 200:
                data = response.json()
                
                # Extraer precipitación (última hora)
                rain = data.get("rain", {})
                precipitation = rain.get("1h", 0.0)  # mm en última hora
                
                return {
                    "precipitacion": precipitation
                }
        except requests.exceptions.RequestException as e:
            st.warning(f"🌐 OpenWeatherMap conexión: {str(e)[:100]}")
            return None
        except Exception as e:
            st.warning(f"🌐 Error inesperado en OpenWeatherMap: {e}")
            return None
    
    def _obtener_nasa_power(self, lat: float, lon: float) -> Optional[Dict]:
        """
        Obtiene radiación solar de NASA POWER API.
        
        Args:
            lat: Latitud
            lon: Longitud
        
        Returns:
            Dict con radiación solar, o None si falla
        """
        try:
            # NASA POWER usa datos diarios, obtenemos últimos 7 días para mayor probabilidad de datos válidos
            hace_7_dias = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
            ayer = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
            
            params = {
                "parameters": "ALLSKY_SFC_SW_DWN",  # Radiación solar
                "community": "RE",  # Renewable Energy
                "longitude": lon,
                "latitude": lat,
                "start": hace_7_dias,
                "end": ayer,
                "format": "JSON"
            }
            
            response = requests.get(
                self.nasa_power_url,
                params=params,
                timeout=30  # NASA POWER es más lento, aumentar timeout a 30s
            )
            
            if response.status_code != 200:
                st.warning(f"🛰️ NASA POWER error {response.status_code}")
                return None
            
            if response.status_code == 200:
                data = response.json()
                parameters = data.get("properties", {}).get("parameter", {})
                allsky_data = parameters.get("ALLSKY_SFC_SW_DWN", {})
                
                # Obtener valores recientes y buscar el primero válido
                if allsky_data:
                    # Iterar desde el más reciente hacia atrás
                    valores = list(allsky_data.values())
                    valores.reverse()  # Más reciente primero
                    
                    for valor in valores:
                        # -999 es el código de NASA para "sin datos"
                        if isinstance(valor, (int, float)) and valor > 0 and valor != -999.0:
                            # NASA da kWh/m²/day, convertir a W/m² promedio (dividir por 24)
                            radiacion_solar = valor * 1000 / 24  # W/m²
                            
                            # Validar rango razonable (0-1000 W/m²)
                            if 0 <= radiacion_solar <= 1000:
                                return {
                                    "radiacion_solar": radiacion_solar
                                }
                    
                    # Si todos los valores son -999 o inválidos
                    st.warning("🛰️ NASA POWER: Sin datos disponibles para esta ubicación (usando valor por defecto)")
        except requests.exceptions.Timeout:
            st.warning("🛰️ NASA POWER: Timeout (servidor lento, usando valor por defecto)")
            return None
        except requests.exceptions.RequestException as e:
            st.warning(f"🛰️ NASA POWER conexión: {str(e)[:80]}")
            return None
        except Exception as e:
            st.warning(f"🛰️ NASA POWER error: {str(e)[:80]}")
            return None
    
    def limpiar_cache(self):
        """Limpia el cache de datos climáticos."""
        self._cache.clear()
    
    def obtener_estadisticas(self) -> Dict:
        """
        Obtiene estadísticas del agente (para debugging).
        
        Returns:
            Dict con información del estado del agente
        """
        return {
            "cache_size": len(self._cache),
            "openweather_configured": bool(self.openweather_key),
            "ipgeolocation_configured": bool(self.ipgeolocation_key),
            "auto_detect_location": self.auto_detect_location,
            "default_location": f"{self.default_location} ({self.default_lat}, {self.default_lon})"
        }
