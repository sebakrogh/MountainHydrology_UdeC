import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta

# Configuración del panel web
st.set_page_config(page_title="Monitor Hydros 21", layout="wide")
st.title("🌊 Monitoreo de Sensor Hydros 21 - Últimas 2 Semanas (API v4)")
st.markdown("Datos consultados en tiempo real desde la API de ZENTRA Cloud.")

# --- PARÁMETROS DESDE SECRETS ---
api_token = st.secrets.get("ZENTRA_TOKEN", "")
device_sn = st.secrets.get("DEVICE_SN", "")

# --- CONSULTA A LA API v4 (ÚLTIMAS 2 SEMANAS) ---
@st.cache_data(ttl=900)  # Guarda en caché por 15 minutos para optimizar
def fetch_hydros_data_v4(token, sn):
    # Cabecera de autenticación idéntica a tu curl exitoso
    headers = {
        "Authorization": f"Token {token}"
    }
    
    # Calcular rango de tiempo para las últimas 2 semanas (14 días)
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=14)
    
    # Formatear fechas con codificación de espacios para URL (%20 en lugar de espacio plano)
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S").replace(" ", "%20")
    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S").replace(" ", "%20")
    
    # Construimos la URL completa con los parámetros incrustados directamente (Query Parameters)
    url = (
        f"https://zentracloud.com/api/v4/get_readings/?"
        f"device_sn={sn}&"
        f"start_date={start_str}&"
        f"end_date={end_str}"
    )
    
    # Hacemos la petición directa con la URL parametrizada
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Error de API ZENTRA ({response.status_code}): {response.text}")
        return None

# --- PROCESAMIENTO Y VISUALIZACIÓN ---
if api_token and device_sn:
    data_json = fetch_hydros_data_v4(api_token, device_sn)
    
    # La API v4 devuelve un formato estructurado como un diccionario de datos
    if data_json and 'data' in data_json:
        readings = data_json['data']
        records = []
        
        # Procesar la respuesta JSON de ZENTRA v4
        for sensor_port, measurements in readings.items():
            for measurement in measurements:
                # Extraer variables si contiene lecturas válidas
                timestamp = pd.to_datetime(measurement.get('datetime'))
                for key, value in measurement.items():
                    # Ignorar metadatos comunes para quedarnos solo con las variables físicas
                    if key not in ['datetime', 'error', 'metadata']:
                        records.append({
                            "Fecha_UTC": timestamp,
                            "Sensor": sensor_port,
                            "Variable": key,
                            "Valor": value
                        })
        
        df = pd.DataFrame(records)
        
        if not df.empty:
            # Normalizar nombres de variables para buscar el Hydros 21
            df['Variable_Normalizada'] = df['Variable'].str.lower()
            
            # Filtros para las variables clave del Hydros 21 (profundidad, temperatura y conductividad)
            depth_df = df[df['Variable_Normalizada'].str.contains('depth|water level|nivel|profundidad')]
            temp_df = df[df['Variable_Normalizada'].str.contains('temp|temperature|temperatura')]
            ec_df = df[df['Variable_Normalizada'].str.contains('ec|conductivity|conductividad|bulk ec')]
            
            # Crear pestañas para organizar cada gráfico de forma limpia
            tab1, tab2, tab3, tab4 = st.tabs([
                "💧 Profundidad de Agua", 
                "🌡️ Temperatura del Agua", 
                "⚡ Conductividad Eléctrica", 
                "📋 Tabla de Datos"
            ])
            
            with tab1:
                if not depth_df.empty:
                    fig_depth = px.line(depth_df, x='Fecha_UTC', y='Valor', color='Sensor',
                                        title="Nivel / Profundidad del Agua",
                                        labels={'Fecha_UTC': 'Fecha (UTC)', 'Valor': 'Profundidad'})
                    fig_depth.update_traces(line_color='#0284c7')
                    st.plotly_chart(fig_depth, use_container_width=True)
                else:
                    st.info("No se encontraron datos de profundidad en el rango seleccionado.")
                    
            with tab2:
                if not temp_df.empty:
                    fig_temp = px.line(temp_df, x='Fecha_UTC', y='Valor', color='Sensor',
                                       title="Temperatura del Agua",
                                       labels={'Fecha_UTC': 'Fecha (UTC)', 'Valor': 'Temperatura (°C)'})
                    fig_temp.update_traces(line_color='#f97316')
                    st.plotly_chart(fig_temp, use_container_width=True)
                else:
                    st.info("No se encontraron datos de temperatura en el rango seleccionado.")
                    
            with tab3:
                if not ec_df.empty