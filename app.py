import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta

# Configuración del panel web
st.set_page_config(page_title="Monitor Meteorológico UdeC", layout="wide")
st.title("🌊 Panel de Monitoreo Ambiental - Universidad de Concepción")
st.markdown("Visualización en tiempo real de sensores Hydros 21 y 5TE (Últimas 2 Semanas).")

# --- PARÁMETROS DESDE SECRETS ---
api_token = st.secrets.get("ZENTRA_TOKEN", "")
device_sn = st.secrets.get("DEVICE_SN", "")

# --- CONSULTA A LA API v4 (ÚLTIMAS 2 SEMANAS) ---
@st.cache_data(ttl=900)  # Guarda en caché por 15 minutos para optimizar
def fetch_hydros_data_v4(token, sn):
    headers = {
        "Authorization": f"Token {token}"
    }
    
    # Calcular rango de tiempo para las últimas 2 semanas (14 días)
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=14)
    
    # Formatear fechas con codificación de espacios para URL (%20)
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S").replace(" ", "%20")
    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S").replace(" ", "%20")
    
    url = (
        f"https://zentracloud.com/api/v4/get_readings/?"
        f"device_sn={sn}&"
        f"start_date={start_str}&"
        f"end_date={end_str}"
    )
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Error de API ZENTRA ({response.status_code}): {response.text}")
        return None

# --- PROCESAMIENTO Y VISUALIZACIÓN ---
if api_token and device_sn:
    data_json = fetch_hydros_data_v4(api_token, device_sn)
    
    if data_json and 'data' in data_json:
        readings_dict = data_json['data']
        records = []
        
        # Procesar la estructura real devuelta por la API v4 de ZENTRA
        for variable_name, items in readings_dict.items():
            for item in items:
                metadata = item.get("metadata", {})
                port = metadata.get("port_number", "S/P")
                sensor_model = metadata.get("sensor_name", "Desconocido")
                unit = metadata.get("units", "").strip()
                
                # Extraer las lecturas de esta serie temporal
                readings = item.get("readings", [])
                for r in readings:
                    if r.get("error_flag") is True:
                        continue # Descartar mediciones con bandera de error
                        
                    timestamp = pd.to_datetime(r.get("datetime"))
                    val_raw = r.get("value")
                    
                    if val_raw is not None:
                        try:
                            val_float = float(val_raw)
                            # Filtrar valores de error fuera de escala (-9999 o superiores)
                            if abs(val_float) < 9999:
                                records.append({
                                    "Fecha_Local": timestamp,
                                    "Puerto": f"Puerto {port}",
                                    "Sensor": sensor_model,
                                    "Variable": variable_name,
                                    "Valor": val_float,
                                    "Unidad": unit
                                })
                        except (ValueError, TypeError):
                            continue
                            
        df = pd.DataFrame(records)
        
        if not df.empty:
            # --- SEPARACIÓN DE VARIABLES ---
            # 1. Hydros 21 / CTD-10 (Puerto 1)
            hydros_df = df[df['Sensor'].str.contains('CTD|Hydros', case=False, na=False)]
            
            # 2. Humedad de suelo 5TE (Puerto 3)
            soil_df = df[df['Sensor'].str.contains('5TE', case=False, na=False)]
            
            # 3. Datos del Sistema (Batería y Presión de referencia / Logger)
            system_df = df[df['Sensor'].str.contains('Battery|Barometer', case=False, na=False)]
            
            # --- CREACIÓN DE PESTAÑAS ---
            tab1, tab2, tab3, tab4 = st.tabs([
                "💧 Sensor Hydros 21 (Agua)", 
                "🌱 Sensor 5TE (Suelo)", 
                "🔋 Estado del Sistema", 
                "📋 Tabla General"
            ])
            
            # PESTAÑA 1: HYDROS 21
            with tab1:
                st.subheader("Monitoreo de la Columna de Agua")
                if not hydros_df.empty:
                    col1, col2, col3 = st.columns(3)
                    
                    # Gráfico de Profundidad
                    with col1:
                        sub_depth = hydros_df[hydros_df['Variable'] == 'Water Level']
                        if not sub_depth.empty:
                            unit = sub_depth['Unidad'].iloc[0]
                            fig = px.line(sub_depth, x='Fecha_Local', y='Valor', 
                                          title=f"Nivel de Agua ({unit})", labels={'Valor': unit, 'Fecha_Local': 'Tiempo'})
                            fig.update_traces(line_color='#0284c7')
                            st.plotly_chart(fig, use_container_width=True)
                    
                    # Gráfico de Temperatura de Agua
                    with col2:
                        sub_temp = hydros_df[hydros_df['Variable'] == 'Water Temperature']
                        if not sub_temp.empty:
                            unit = sub_temp['Unidad'].iloc[0]
                            fig = px.line(sub_temp, x='Fecha_Local', y='Valor', 
                                          title=f"Temperatura del Agua ({unit})", labels={'Valor': unit, 'Fecha_Local': 'Tiempo'})
                            fig.update_traces(line_color='#f97316')
                            st.plotly_chart(fig, use_container_width=True)
                            
                    # Gráfico de Conductividad
                    with col3:
                        sub_ec = hydros_df[hydros_df['Variable'] == 'EC']
                        if not sub_ec.empty:
                            unit = sub_ec['Unidad'].iloc[0]
                            fig = px.line(sub_ec, x='Fecha_Local', y='Valor', 
                                          title=f"Conductividad Eléctrica ({unit})", labels={'Valor': unit, 'Fecha_Local': 'Tiempo'})
                            fig.update_traces(line_color='#10b981')
                            st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No se encontraron datos del sensor Hydros 21.")

            # PESTAÑA 2: SENSOR 5TE
            with tab2:
                st.subheader("Parámetros de Humedad y Temperatura de Suelo")
                if not soil_df.empty:
                    col1, col2, col3 = st.columns(3)
                    
                    # Contenido de Agua
                    with col1:
                        sub_wc = soil_df[soil_df['Variable'] == 'Water Content']
                        if not sub_wc.empty:
                            unit = sub_wc['Unidad'].iloc[0]
                            fig = px.line(sub_wc, x='Fecha_Local', y='Valor', 
                                          title=f"Contenido Volumétrico de Agua ({unit})", labels={'Valor': unit, 'Fecha_Local': 'Tiempo'})
                            fig.update_traces(line_color='#1d4ed8')
                            st.plotly_chart(fig, use_container_width=True)
                    
                    # Temperatura de Suelo
                    with col2:
                        sub_st = soil_df[soil_df['Variable'] == 'Soil Temperature']
                        if not sub_st.empty:
                            unit = sub_st['Unidad'].iloc[0]
                            fig = px.line(sub_st, x='Fecha_Local', y='Valor', 
                                          title=f"Temperatura de Suelo ({unit})", labels={'Valor': unit, 'Fecha_Local': 'Tiempo'})
                            fig.update_traces(line_color='#ea580c')
                            st.plotly_chart(fig, use_container_width=True)
                            
                    # Saturation Extract EC
                    with col3:
                        sub_sec = soil_df[soil_df['Variable'] == 'Saturation Extract EC']
                        if not sub_sec.empty:
                            unit = sub_sec['Unidad'].iloc[0]
                            fig = px.line(sub_sec, x='Fecha_Local', y='Valor', 
                                          title=f"EC del Extracto de Saturación ({unit})", labels={'Valor': unit, 'Fecha_Local': 'Tiempo'})
                            fig.update_traces(line_color='#059669')
                            st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No se encontraron datos del sensor de suelo 5TE.")

            # PESTAÑA 3: ESTADO DEL SISTEMA (Datalogger)
            with tab3:
                st.subheader("Parámetros de Diagnóstico y Presión de Referencia")
                if not system_df.empty:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        sub_bat = system_df[system_df['Variable'] == 'Battery Percent']
                        if not sub_bat.empty:
                            fig = px.line(sub_bat, x='Fecha_Local', y='Valor', 
                                          title="Porcentaje de Batería (%)", labels={'Valor': '%', 'Fecha_Local': 'Tiempo'})
                            fig.update_traces(line_color='#e11d48')
                            st.plotly_chart(fig, use_container_width=True)
                            
                    with col2:
                        sub_pres = system_df[system_df['Variable'] == 'Reference Pressure']
                        if not sub_pres.empty:
                            unit = sub_pres['Unidad'].iloc[0]
                            fig = px.line(sub_pres, x='Fecha_Local', y='Valor', 
                                          title=f"Presión Atmosférica de Referencia ({unit})", labels={'Valor': unit, 'Fecha_Local': 'Tiempo'})
                            fig.update_traces(line_color='#475569')
                            st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No se encontraron datos de diagnóstico del sistema.")

            # PESTAÑA 4: TABLA DE DATOS CONSOLIDADOS
            with tab4:
                st.subheader("Visualización de Datos Consolidados")
                df_sorted = df[['Fecha_Local', 'Puerto', 'Sensor', 'Variable', 'Valor', 'Unidad']].sort_values(by='Fecha_Local', ascending=False)
                st.dataframe(df_sorted, use_container_width=True)
                
        else:
            st.warning("No se encontraron registros numéricos válidos en la respuesta de ZENTRA.")
    else:
        st.error("No se pudo analizar el JSON de respuesta. Asegúrate de que las credenciales en Secrets correspondan a tu logger activo.")
else:
    st.info("Configura las credenciales `ZENTRA_TOKEN` y `DEVICE_SN` en la pestaña de Secrets de Streamlit.")