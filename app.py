import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Valle Hermoso - Monitoreo UdeC", layout="wide")

# --- TÍTULO Y DESCRIPCIÓN DEL SITIO ---
st.title("🏔️ Estación de Monitoreo en Valle Hermoso")
st.markdown("### **Grupo de Hidrología de Montaña UdeC**")

# Bloque de metadatos del sitio (Actualizado a 5 días)
col_meta1, col_meta2 = st.columns(2)
with col_meta1:
    st.markdown("""
    * **Elevación:** 1576 msnm
    * **Financiamiento:** Fondecyt Regular 1261545
    * **Investigador Principal (IP):** Sebastian Krogh
    """)
with col_meta2:
    st.markdown("""
    * **Sensores en Terreno:** Hydros 21 (CTD-10) en Estero/Pozo y Sensores de Suelo (5TE/5TM)
    * **Frecuencia de Actualización:** Tiempo real (API ZENTRA Cloud v4)
    * **Rango Visualizado:** Últimos 5 días de registro (Límite de API estándar)
    """)

st.markdown("---")

# --- PARÁMETROS DESDE SECRETS ---
api_token = st.secrets.get("ZENTRA_TOKEN", "")
device_sn = st.secrets.get("DEVICE_SN", "")

# --- CONSULTA A LA API v4 (UNA SOLA SOLICITUD ESTÁNDAR) ---
@st.cache_data(ttl=900)
def fetch_hydros_data_v4(token, sn):
    headers = {"Authorization": f"Token {token}"}
    end_time = datetime.utcnow()
    # Solicitamos los últimos 5 días para coincidir exactamente con el volumen estándar de la API
    start_time = end_time - timedelta(days=5)
    
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S").replace(" ", "%20")
    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S").replace(" ", "%20")
    
    try:
        # Solicitud simple y limpia de una sola página con el límite estándar de 500 registros
        url = (
            f"https://zentracloud.com/api/v4/get_readings/?"
            f"device_sn={sn}&"
            f"start_date={start_str}&"
            f"end_date={end_str}&"
            f"page_num=1"
        )
        
        response = requests.get(url, headers=headers, timeout=20)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error devuelto por la API ZENTRA ({response.status_code}): {response.text}")
            return None
            
    except Exception as e:
        st.error(f"Error de conexión con el servidor: {e}")
        return None

# --- FUNCIÓN PARA GRÁFICOS MULTI-LÍNEA ESTILIZADOS ---
def crear_grafico_estilizado(df_var, titulo, y_label, color_map=None):
    fig = px.line(
        df_var, 
        x='Fecha_Local', 
        y='Valor', 
        color='Ubicación',
        color_discrete_map=color_map,
        labels={'Fecha_Local': 'Fecha y Hora', 'Valor': y_label, 'Ubicación': 'Ubicación / Estación'},
        template="plotly_white"
    )
    
    fig.update_traces(line_width=2.5)
    
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=15, family="Arial", color="#1e293b"), x=0.0),
        hovermode="x unified",
        margin=dict(l=40, r=20, t=50, b=40),
        height=400,
        xaxis=dict(showgrid=True, gridcolor='#f1f5f9', tickformat="%d %b\n%H:%M", linecolor='#cbd5e1'),
        yaxis=dict(showgrid=True, gridcolor='#f1f5f9', linecolor='#cbd5e1', zeroline=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=dict(text=""))
    )
    return fig

# --- PROCESAMIENTO Y VISUALIZACIÓN ---
if api_token and device_sn:
    data_json = fetch_hydros_data_v4(api_token, device_sn)
    
    if data_json and 'data' in data_json:
        readings_dict = data_json['data']
        records = []
        
        for variable_name, items in readings_dict.items():
            for item in items:
                metadata = item.get("metadata", {})
                
                port_raw = metadata.get("port_number")
                port = str(port_raw) if port_raw is not None else "S/P"
                
                sensor_raw = metadata.get("sensor_name")
                sensor_model = str(sensor_raw) if sensor_raw else "Desconocido"
                
                unit_raw = metadata.get("units")
                unit = str(unit_raw).strip() if unit_raw else ""
                
                readings = item.get("readings", [])
                for r in readings:
                    if r.get("error_flag") is True:
                        continue
                        
                    raw_dt = r.get("datetime")
                    if not raw_dt:
                        continue
                        
                    timestamp = pd.to_datetime(raw_dt)
                    if timestamp.tzinfo is not None:
                        timestamp = timestamp.tz_localize(None)
                        
                    val_raw = r.get("value")
                    if val_raw is not None:
                        try:
                            val_float = float(val_raw)
                            if abs(val_float) < 9999:
                                ubicacion = f"Puerto {port}"
                                if sensor_model == "CTD-10":
                                    if port == "1":
                                        ubicacion = "Estero"
                                    elif port == "2":
                                        ubicacion = "Pozo"
                                elif sensor_model in ["5TE", "5TM"]:
                                    ubicacion = f"Puerto {port}"
                                
                                records.append({
                                    "Fecha_Local": timestamp,
                                    "Puerto": f"Puerto {port}",
                                    "Sensor": sensor_model,
                                    "Ubicación": ubicacion,
                                    "Variable": variable_name,
                                    "Valor": val_float,
                                    "Unidad": unit
                                })
                        except (ValueError, TypeError):
                            pass 
                            
        df = pd.DataFrame(records)
        
        if not df.empty:
            hydros_df = df[df['Sensor'].str.contains('CTD|Hydros', case=False, na=False)]
            soil_df = df[df['Sensor'].str.contains('5TE|5TM', case=False, na=False)]
            system_df = df[df['Sensor'].str.contains('Battery|Barometer', case=False, na=False)]
            
            colors_hydros = {"Estero": "#0284c7", "Pozo": "#f97316"}
            colors_soil = {"Puerto 3": "#10b981", "Puerto 4": "#eab308", "Puerto 5": "#a855f7"}
            
            # Pestañas para las gráficas
            tab1, tab2, tab3 = st.tabs([
                "💧 Sensor Hydros 21 (Agua)", 
                "🌱 Sensor 5TE / 5TM (Suelo)", 
                "🔋 Estado del Sistema"
            ])
            
            # PESTAÑA 1: HYDROS 21
            with tab1:
                st.subheader("Monitoreo de la Columna de Agua - Últimos 5 Días")
                if not hydros_df.empty:
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        sub_depth = hydros_df[hydros_df['Variable'] == 'Water Level']
                        if not sub_depth.empty:
                            unit_str = sub_depth['Unidad'].iloc[0]
                            fig = crear_grafico_estilizado(sub_depth, "Nivel de Agua", f"Profundidad ({unit_str})", colors_hydros)
                            st.plotly_chart(fig, use_container_width=True)
                            
                    with col2:
                        sub_temp = hydros_df[hydros_df['Variable'] == 'Water Temperature']
                        if not sub_temp.empty:
                            unit_str = sub_temp['Unidad'].iloc[0]
                            fig = crear_grafico_estilizado(sub_temp, "Temperatura del Agua", f"Temperatura ({unit_str})", colors_hydros)
                            st.plotly_chart(fig, use_container_width=True)
                            
                    with col3:
                        sub_ec = hydros_df[hydros_df['Variable'] == 'EC']
                        if not sub_ec.empty:
                            unit_str = sub_ec['Unidad'].iloc[0]
                            fig = crear_grafico_estilizado(sub_ec, "Conductividad Eléctrica", f"Conductividad ({unit_str})", colors_hydros)
                            st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No se encontraron datos del sensor Hydros 21.")

            # PESTAÑA 2: SENSORES DE SUELO
            with tab2:
                st.subheader("Parámetros de Humedad y Temperatura de Suelo - Últimos 5 Días")
                if not soil_df.empty:
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        sub_wc = soil_df[soil_df['Variable'] == 'Water Content']
                        if not sub_wc.empty:
                            unit_str = sub_wc['Unidad'].iloc[0]
                            fig = crear_grafico_estilizado(sub_wc, "Contenido Volumétrico de Agua", f"Humedad ({unit_str})", colors_soil)
                            st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        sub_st = soil_df[soil_df['Variable'] == 'Soil Temperature']
                        if not sub_st.empty:
                            unit_str = sub_st['Unidad'].iloc[0]
                            fig = crear_grafico_estilizado(sub_st, "Temperatura de Suelo", f"Temperatura ({unit_str})", colors_soil)
                            st.plotly_chart(fig, use_container_width=True)
                            
                    with col3:
                        sub_sec = soil_df[soil_df['Variable'] == 'Saturation Extract EC']
                        if not sub_sec.empty:
                            unit_str = sub_sec['Unidad'].iloc[0]
                            fig = crear_grafico_estilizado(sub_sec, "EC Extracto Saturación", f"Salinidad ({unit_str})", colors_soil)
                            st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No se encontraron datos de los sensores de suelo (Puertos 3, 4 o 5).")

            # PESTAÑA 3: DIAGNÓSTICO
            with tab3:
                st.subheader("Parámetros de Diagnóstico y Presión de Referencia")
                if not system_df.empty:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        sub_bat = system_df[system_df['Variable'] == 'Battery Percent']
                        if not sub_bat.empty:
                            fig = crear_grafico_estilizado(sub_bat, "Nivel de Batería", "Porcentaje (%)", {"Puerto 7": "#e11d48"})
                            st.plotly_chart(fig, use_container_width=True)
                            
                    with col2:
                        sub_pres = system_df[system_df['Variable'] == 'Reference Pressure']
                        if not sub_pres.empty:
                            unit_str = sub_pres['Unidad'].iloc[0]
                            fig = crear_grafico_estilizado(sub_pres, "Presión Atmosférica de Referencia", f"Presión ({unit_str})", {"Puerto 8": "#475569"})
                            st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No se encontraron datos de diagnóstico del sistema.")
                
        else:
            st.warning("No se encontraron registros numéricos válidos en la respuesta de ZENTRA.")
    else:
        st.error("No se pudo analizar el JSON de respuesta de ZENTRA. Asegúrate de que las credenciales son correctas.")
else:
    st.info("Configura las credenciales `ZENTRA_TOKEN` y `DEVICE_SN` en los Secrets de Streamlit.")


# --- SECCIÓN FIJA DE FOTOGRAFÍA AL FINAL DE LA PÁGINA ---
st.markdown("---")
st.subheader("📸 Registro Fotográfico del Sitio de Monitoreo")

imagen_encontrada = False
for ext in ["jpg", "jpeg", "png", "JPG", "PNG"]:
    path_imagen = f"estacion.{ext}"
    if os.path.exists(path_imagen):
        col_img1, col_img2, col_img3 = st.columns([1, 2, 1])
        with col_img2:
            st.image(path_imagen, caption="Estación Fluviométrica en Valle Hermoso (1576 msnm)", use_container_width=True)
        imagen_encontrada = True
        break

if not imagen_encontrada:
    st.info("💡 Para mostrar una fotografía fija aquí, sube un archivo de imagen llamado **'estacion.jpg'** o **'estacion.png'** directamente a la carpeta raíz de tu repositorio en GitHub.")