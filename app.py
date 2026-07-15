import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta

# Configuración del panel web
st.set_page_config(page_title="Monitor Hydros 21", layout="wide")
st.title("🌊 Monitoreo de Sensor Hydros 21 - Últimas 2 Semanas")
st.markdown("Datos consultados en tiempo real desde la API de ZENTRA Cloud.")

# --- PARÁMETROS EN BARRA LATERAL ---
st.sidebar.header("Configuración de Conexión")

# Uso de Secrets de Streamlit para no exponer credenciales
api_token = st.secrets.get("ZENTRA_TOKEN", "")
device_sn = st.secrets.get("DEVICE_SN", "")

# Si no están configurados en Secrets, permite ingresarlos manualmente
if not api_token or not device_sn:
    st.sidebar.warning("⚠️ Configura las credenciales en Streamlit Secrets para producción.")
    api_token = st.sidebar.text_input("ZENTRA Token", type="password", value=api_token)
    device_sn = st.sidebar.text_input("Número de Serie del Registrador", value=device_sn)

# --- CONSULTA A LA API (ÚLTIMAS 2 SEMANAS) ---
@st.cache_data(ttl=900)  # Almacena en caché por 15 minutos para optimizar llamadas API
def fetch_hydros_data(token, sn):
    headers = {"Authorization": f"Token {token}"}
    
    # Calcular rango de tiempo para las últimas 2 semanas (14 días)
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=14)
    
    params = {
        "start_date": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "end_date": end_time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    url = f"https://api.zentracloud.com/v5/devices/{sn}/readings/"
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Error de API ZENTRA ({response.status_code}): {response.text}")
        return None

# --- PROCESAMIENTO Y VISUALIZACIÓN ---
if api_token and device_sn:
    data_json = fetch_hydros_data(api_token, device_sn)
    
    if data_json and 'data' in data_json:
        readings = data_json['data']
        records = []
        
        # Recorrer puertos y sensores para extraer las métricas del Hydros 21
        for port, sensors in readings.items():
            for sensor_name, measurements in sensors.items():
                for m in measurements:
                    records.append({
                        "Fecha_UTC": pd.to_datetime(m['datetime']),
                        "Sensor": f"Puerto {port} - {sensor_name}",
                        "Variable": m.get('description', sensor_name),
                        "Valor": m['value'],
                        "Unidad": m.get('unit', '')
                    })
        
        df = pd.DataFrame(records)
        
        if not df.empty:
            # Filtrar las 3 variables clave del Hydros 21 utilizando búsquedas parciales inteligentes
            df['Variable_Normalizada'] = df['Variable'].str.lower()
            
            # Filtros por palabras clave (en inglés y español según la configuración del sensor)
            depth_df = df[df['Variable_Normalizada'].str.contains('depth|profundidad|water level|nivel')]
            temp_df = df[df['Variable_Normalizada'].str.contains('temp|temperature|temperatura')]
            ec_df = df[df['Variable_Normalizada'].str.contains('ec|conductivity|conductividad|bulk ec')]
            
            # Crear pestañas para organizar de forma limpia cada gráfico
            tab1, tab2, tab3, tab4 = st.tabs([
                "💧 Profundidad de Agua", 
                "🌡️ Temperatura del Agua", 
                "⚡ Conductividad Eléctrica", 
                "📋 Tabla de Datos"
            ])
            
            with tab1:
                if not depth_df.empty:
                    fig_depth = px.line(depth_df, x='Fecha_UTC', y='Valor', 
                                        title="Nivel / Profundidad del Agua (Últimas 2 Semanas)",
                                        labels={'Fecha_UTC': 'Fecha (UTC)', 'Valor': f"Profundidad ({depth_df['Unidad'].iloc[0]})"})
                    fig_depth.update_traces(line_color='#0284c7')
                    st.plotly_chart(fig_depth, use_container_width=True)
                else:
                    st.info("No se encontraron datos de profundidad en el rango seleccionado.")
                    
            with tab2:
                if not temp_df.empty:
                    fig_temp = px.line(temp_df, x='Fecha_UTC', y='Valor', 
                                       title="Temperatura del Agua (Últimas 2 Semanas)",
                                       labels={'Fecha_UTC': 'Fecha (UTC)', 'Valor': f"Temperatura ({temp_df['Unidad'].iloc[0]})"})
                    fig_temp.update_traces(line_color='#f97316')
                    st.plotly_chart(fig_temp, use_container_width=True)
                else:
                    st.info("No se encontraron datos de temperatura en el rango seleccionado.")
                    
            with tab3:
                if not ec_df.empty:
                    fig_ec = px.line(ec_df, x='Fecha_UTC', y='Valor', 
                                     title="Conductividad Eléctrica (Últimas 2 Semanas)",
                                     labels={'Fecha_UTC': 'Fecha (UTC)', 'Valor': f"EC ({ec_df['Unidad'].iloc[0]})"})
                    fig_ec.update_traces(line_color='#10b981')
                    st.plotly_chart(fig_ec, use_container_width=True)
                else:
                    st.info("No se encontraron datos de conductividad eléctrica en el rango seleccionado.")
                    
            with tab4:
                st.subheader("Datos Consolidados del Sensor")
                # Mostrar tabla con opción de descarga incorporada por Streamlit
                df_mostrar = df[['Fecha_UTC', 'Sensor', 'Variable', 'Valor', 'Unidad']].sort_values(by='Fecha_UTC', ascending=False)
                st.dataframe(df_mostrar, use_container_width=True)
        else:
            st.warning("No se encontraron mediciones ni datos estructurados para este número de serie en las últimas 2 semanas.")
    else:
        st.error("No se pudo obtener la estructura de datos del dispositivo. Verifica que el número de serie sea correcto.")
else:
    st.info("Por favor, introduce tu Token de ZENTRA y el SN del logger en la barra lateral o configúralos en Streamlit Secrets.")