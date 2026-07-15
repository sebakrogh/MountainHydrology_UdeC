import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import datetime, timedelta

# Configuración del panel web
st.set_page_config(page_title="Monitor Meteorológico UdeC", layout="wide")
st.title("🌊 Panel de Monitoreo Ambiental - Universidad de Concepción")
st.markdown("Visualización en tiempo real de sensores Hydros 21 (CTD-10) y Sensores de Suelo (5TE/5TM).")

# --- PARÁMETROS DESDE SECRETS ---
api_token = st.secrets.get("ZENTRA_TOKEN", "")
device_sn = st.secrets.get("DEVICE_SN", "")

# --- CONSULTA A LA API v4 (ÚLTIMAS 2 SEMANAS) ---
@st.cache_data(ttl=900)  # Guarda en caché por 15 minutos para optimizar
def fetch_hydros_data_v4(token, sn):
    headers = {
        "Authorization": f"Token {token}"
    }
    
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=14)
    
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

# --- FUNCIÓN PARA GRÁFICOS MULTI-LÍNEA ESTILIZADOS ---
def crear_grafico_estilizado(df_var, titulo, y_label, color_map=None):
    """
    Genera un gráfico de línea altamente optimizado, limpio y que soporta múltiples
    series de datos usando una columna de agrupación ('Ubicación').
    """
    fig = px.line(
        df_var, 
        x='Fecha_Local', 
        y='Valor', 
        color='Ubicación',
        color_discrete_map=color_map,
        labels={'Fecha_Local': 'Fecha y Hora', 'Valor': y_label, 'Ubicación': 'Ubicación / Estación'},
        template="plotly_white"
    )
    
    # Suavizado de curva y diseño de línea
    fig.update_traces(
        line=dict(width=2.5, shape='spline'),
        mode='lines'
    )
    
    # Optimización de diseño de la plantilla
    fig.update_layout(
        title=dict(
            text=titulo,
            font=dict(size=15, family="Arial", color="#1e293b"),
            x=0.0,
        ),
        hovermode="x unified",
        margin=dict(l=40, r=20, t=50, b=40),
        height=400,
        xaxis=dict(
            showgrid=True,
            gridcolor='#f1f5f9',
            tickformat="%d %b\n%H:%M",
            linecolor='#cbd5e1'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='#f1f5f9',
            linecolor='#cbd5e1',
            zeroline=False
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            title=dict(text="")
        )
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
                port = metadata.get("port_number", "S/P")
                sensor_model = metadata.get("sensor_name", "Desconocido")
                unit = metadata.get("units", "").strip()
                
                readings = item.get("readings", [])
                for r in readings:
                    if r.get("error_flag") is True:
                        continue
                        
                    timestamp = pd.to_datetime(r.get("datetime"))
                    val_raw = r.get("value")
                    
                    if val_raw is not None:
                        try:
                            val_float = float(val_raw)
                            if abs(val_float) < 9999:
                                # --- ASOCIACIÓN DE UBICACIONES Y LEYENDAS ---
                                ubicacion = f"Puerto {port}"
                                if sensor_model == "CTD-10":
                                    if str(port) == "1":
                                        ubicacion = "Estero"
                                    elif str(port) == "2":
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
                            continue
                            
        df = pd.DataFrame(records)
        
        if not df.empty:
            # --- SEPARACIÓN DE VARIABLES SEGÚN SENSOR ---
            hydros_df = df[df['Sensor'].str.contains('CTD|Hydros', case=False, na=False)]
            soil_df = df[df['Sensor'].str.contains('5TE|5TM', case=False, na=False