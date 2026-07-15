{\rtf1\ansi\ansicpg1252\cocoartf2870
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\margl1440\margr1440\vieww19460\viewh14740\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import streamlit as st\
import pandas as pd\
import requests\
import plotly.express as px\
from datetime import datetime, timedelta\
\
# Configuraci\'f3n del panel web\
st.set_page_config(page_title="Monitor Hydros 21", layout="wide")\
st.title("\uc0\u55356 \u57098  Monitoreo de Sensor Hydros 21 - \'daltimas 2 Semanas")\
st.markdown("Datos consultados en tiempo real desde la API de ZENTRA Cloud.")\
\
# --- PAR\'c1METROS EN BARRA LATERAL ---\
st.sidebar.header("Configuraci\'f3n de Conexi\'f3n")\
\
# Uso de Secrets de Streamlit para no exponer credenciales\
api_token = st.secrets.get("ZENTRA_TOKEN", "")\
device_sn = st.secrets.get("DEVICE_SN", "")\
\
# Si no est\'e1n configurados en Secrets, permite ingresarlos manualmente\
if not api_token or not device_sn:\
    st.sidebar.warning("\uc0\u9888 \u65039  Configura las credenciales en Streamlit Secrets para producci\'f3n.")\
    api_token = st.sidebar.text_input("ZENTRA Token", type="password", value=api_token)\
    device_sn = st.sidebar.text_input("N\'famero de Serie del Registrador", value=device_sn)\
\
# --- CONSULTA A LA API (\'daLTIMAS 2 SEMANAS) ---\
@st.cache_data(ttl=900)  # Almacena en cach\'e9 por 15 minutos para optimizar llamadas API\
def fetch_hydros_data(token, sn):\
    headers = \{"Authorization": f"Token \{token\}"\}\
    \
    # Calcular rango de tiempo para las \'faltimas 2 semanas (14 d\'edas)\
    end_time = datetime.utcnow()\
    start_time = end_time - timedelta(days=14)\
    \
    params = \{\
        "start_date": start_time.strftime("%Y-%m-%d %H:%M:%S"),\
        "end_date": end_time.strftime("%Y-%m-%d %H:%M:%S")\
    \}\
    \
    url = f"https://api.zentracloud.com/v5/devices/\{sn\}/readings/"\
    response = requests.get(url, headers=headers, params=params)\
    \
    if response.status_code == 200:\
        return response.json()\
    else:\
        st.error(f"Error de API ZENTRA (\{response.status_code\}): \{response.text\}")\
        return None\
\
# --- PROCESAMIENTO Y VISUALIZACI\'d3N ---\
if api_token and device_sn:\
    data_json = fetch_hydros_data(api_token, device_sn)\
    \
    if data_json and 'data' in data_json:\
        readings = data_json['data']\
        records = []\
        \
        # Recorrer puertos y sensores para extraer las m\'e9tricas del Hydros 21\
        for port, sensors in readings.items():\
            for sensor_name, measurements in sensors.items():\
                for m in measurements:\
                    records.append(\{\
                        "Fecha_UTC": pd.to_datetime(m['datetime']),\
                        "Sensor": f"Puerto \{port\} - \{sensor_name\}",\
                        "Variable": m.get('description', sensor_name),\
                        "Valor": m['value'],\
                        "Unidad": m.get('unit', '')\
                    \})\
        \
        df = pd.DataFrame(records)\
        \
        if not df.empty:\
            # Filtrar las 3 variables clave del Hydros 21 utilizando b\'fasquedas parciales inteligentes\
            df['Variable_Normalizada'] = df['Variable'].str.lower()\
            \
            # Filtros por palabras clave (en ingl\'e9s y espa\'f1ol seg\'fan la configuraci\'f3n del sensor)\
            depth_df = df[df['Variable_Normalizada'].str.contains('depth|profundidad|water level|nivel')]\
            temp_df = df[df['Variable_Normalizada'].str.contains('temp|temperature|temperatura')]\
            ec_df = df[df['Variable_Normalizada'].str.contains('ec|conductivity|conductividad|bulk ec')]\
            \
            # Crear pesta\'f1as para organizar de forma limpia cada gr\'e1fico\
            tab1, tab2, tab3, tab4 = st.tabs([\
                "\uc0\u55357 \u56487  Profundidad de Agua", \
                "\uc0\u55356 \u57121 \u65039  Temperatura del Agua", \
                "\uc0\u9889  Conductividad El\'e9ctrica", \
                "\uc0\u55357 \u56523  Tabla de Datos"\
            ])\
            \
            with tab1:\
                if not depth_df.empty:\
                    fig_depth = px.line(depth_df, x='Fecha_UTC', y='Valor', \
                                        title="Nivel / Profundidad del Agua (\'daltimas 2 Semanas)",\
                                        labels=\{'Fecha_UTC': 'Fecha (UTC)', 'Valor': f"Profundidad (\{depth_df['Unidad'].iloc[0]\})"\})\
                    fig_depth.update_traces(line_color='#0284c7')\
                    st.plotly_chart(fig_depth, use_container_width=True)\
                else:\
                    st.info("No se encontraron datos de profundidad en el rango seleccionado.")\
                    \
            with tab2:\
                if not temp_df.empty:\
                    fig_temp = px.line(temp_df, x='Fecha_UTC', y='Valor', \
                                       title="Temperatura del Agua (\'daltimas 2 Semanas)",\
                                       labels=\{'Fecha_UTC': 'Fecha (UTC)', 'Valor': f"Temperatura (\{temp_df['Unidad'].iloc[0]\})"\})\
                    fig_temp.update_traces(line_color='#f97316')\
                    st.plotly_chart(fig_temp, use_container_width=True)\
                else:\
                    st.info("No se encontraron datos de temperatura en el rango seleccionado.")\
                    \
            with tab3:\
                if not ec_df.empty:\
                    fig_ec = px.line(ec_df, x='Fecha_UTC', y='Valor', \
                                     title="Conductividad El\'e9ctrica (\'daltimas 2 Semanas)",\
                                     labels=\{'Fecha_UTC': 'Fecha (UTC)', 'Valor': f"EC (\{ec_df['Unidad'].iloc[0]\})"\})\
                    fig_ec.update_traces(line_color='#10b981')\
                    st.plotly_chart(fig_ec, use_container_width=True)\
                else:\
                    st.info("No se encontraron datos de conductividad el\'e9ctrica en el rango seleccionado.")\
                    \
            with tab4:\
                st.subheader("Datos Consolidados del Sensor")\
                # Mostrar tabla con opci\'f3n de descarga incorporada por Streamlit\
                df_mostrar = df[['Fecha_UTC', 'Sensor', 'Variable', 'Valor', 'Unidad']].sort_values(by='Fecha_UTC', ascending=False)\
                st.dataframe(df_mostrar, use_container_width=True)\
        else:\
            st.warning("No se encontraron mediciones ni datos estructurados para este n\'famero de serie en las \'faltimas 2 semanas.")\
    else:\
        st.error("No se pudo obtener la estructura de datos del dispositivo. Verifica que el n\'famero de serie sea correcto.")\
else:\
    st.info("Por favor, introduce tu Token de ZENTRA y el SN del logger en la barra lateral o config\'faralos en Streamlit Secrets.")}