import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import json
import base64
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Valle Hermoso - Monitoreo Histórico", layout="wide")

# --- TÍTULO Y DESCRIPCIÓN DEL SITIO ---
st.title("🏔️ Estación de Monitoreo en Valle Hermoso")
st.markdown("### **Grupo de Hidrología de Montaña UdeC**")

# Bloque de metadatos del sitio
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
    * **Base de Datos:** Histórica almacenada en Google Sheets
    * **Actualización:** Automática (Cosechador GitHub Actions todos los días a las 00:00)
    """)

st.markdown("---")

# --- CONEXIÓN DE SEGURIDAD A GOOGLE SHEETS (MÉTODO BASE64) ---
@st.cache_data(ttl=600)  # Almacena en caché los datos por 10 minutos
def cargar_datos_historicos():
    try:
        # Recuperamos la cápsula Base64 y el ID de la hoja desde los Secrets
        b64_creds = st.secrets.get("B64_CREDS")
        sheet_id = st.secrets.get("HISTORICO_SHEETS_ID")
        
        if not b64_creds or not sheet_id:
            st.error("Faltan configurar las variables 'B64_CREDS' o 'HISTORICO_SHEETS_ID' en los Secrets de Streamlit.")
            return pd.DataFrame()
            
        # 1. Decodificamos la cápsula binaria de vuelta a texto plano JSON
        creds_json_str = base64.b64decode(b64_creds).decode('utf-8')
        
        # 2. Convertimos el texto JSON en un diccionario nativo de Python
        creds_dict = json.loads(creds_json_str)
        
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # 3. Autenticación directa a la API de Google sin problemas de formato PEM
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        
        # Conectar a la hoja y descargar todas las filas
        sheet = client.open_by_key(sheet_id).sheet1
        records = sheet.get_all_records()
        
        if not records:
            return pd.DataFrame()
            
        df_raw = pd.DataFrame(records)
        
        # Procesar formatos
        df_raw['Fecha_Local'] = pd.to_datetime(df_raw['Fecha_Local'])
        df_raw['Valor'] = pd.to_numeric(df_raw['Valor'], errors='coerce')
        return df_raw.dropna(subset=['Fecha_Local', 'Valor'])
        
    except Exception as e:
        st.error(f"Error al conectar con la base de datos de Google Sheets: {e}")
        return pd.DataFrame()

# --- CARGAR BASE DE DATOS ---
with st.spinner("Conectando con el histórico en Google Sheets..."):
    df = cargar_datos_historicos()

# --- FUNCIÓN PARA GRÁFICOS MULTI-LÍNEA ESTILIZADOS ---
def crear_grafico_estilizado(df_var, titulo, y_label, color_map=None):
    fig = px.line(
        df_var, 
        x='Fecha_Local', 
        y='Valor', 
        color='Ubicación',
        color_discrete_map=color_map,
        labels={'Valor': y_label, 'Ubicación': 'Ubicación / Estación'},
        template="plotly_white"
    )
    
    fig.update_traces(line_width=2.5)
    
    fig.update_layout(
        title=dict(
            text=titulo, 
            font=dict(size=14, family="Arial", color="#1e293b"), 
            x=0.0,
            y=0.95
        ),
        hovermode="x unified",
        margin=dict(l=40, r=20, t=75, b=80),  # Margen inferior amplio para la leyenda externa
        height=400,
        xaxis=dict(
            title=None,  # Eliminamos el rótulo redundante de Fecha_Local
            showgrid=True, 
            gridcolor='#f1f5f9', 
            tickformat="%d %b\n%H:%M", 
            linecolor='#cbd5e1'
        ),
        yaxis=dict(
            title=dict(text=y_label, font=dict(size=12)),
            showgrid=True, 
            gridcolor='#f1f5f9', 
            linecolor='#cbd5e1', 
            zeroline=False
        ),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.22,  # Ubica la leyenda perfectamente centrada debajo de las etiquetas del eje X
            xanchor="center",
            x=0.5,
            title=dict(text="")
        )
    )
        
    return fig

# --- PROCESAMIENTO Y FILTROS EN PÁGINA ---
if not df.empty:
    # --- BARRA LATERAL: SELECTOR TEMPORAL ---
    st.sidebar.header("🗓️ Rango Temporal")
    
    # Determinar rango máximo de fechas en la base de datos de forma robusta
    max_fecha = df['Fecha_Local'].max()
    min_fecha = df['Fecha_Local'].min()
    dias_totales = (max_fecha - min_fecha).days + 1
    
    # Calcular el valor máximo permitido para el slider (mínimo de seguridad de 5 días)
    max_slider = max(5, dias_totales)
    
    # Selector deslizante (slider) interactivo de días
    dias_seleccionados = st.sidebar.slider(
        "Días a visualizar en los gráficos",
        min_value=1,
        max_value=max_slider,
        value=min(5, dias_totales),
        help="Elige cuántos días del histórico hacia atrás deseas graficar en pantalla."
    )
    
    # Filtrar el dataframe según el rango seleccionado
    limite_tiempo = max_fecha - pd.Timedelta(days=dias_seleccionados)
    df_filtrado = df[df['Fecha_Local'] >= limite_tiempo]

    # Separar dataframes por tipo de sensor
    hydros_df = df_filtrado[df_filtrado['Sensor'].str.contains('CTD|Hydros', case=False, na=False)]
    soil_df = df_filtrado[df_filtrado['Sensor'].str.contains('5TE|5TM', case=False, na=False)]
    system_df = df_filtrado[df_filtrado['Sensor'].str.contains('Battery|Barometer|Logger', case=False, na=False)]
    
    # Buscamos la temperatura del datalogger para el contexto histórico
    logger_temp_df = df_filtrado[df_filtrado['Variable'].str.contains('Logger Temperature', case=False, na=False)]
    
    if not logger_temp_df.empty:
        logger_temp_df = logger_temp_df.copy()
        logger_temp_df['Ubicación'] = "Temperatura del aire (datalogger)"
    
    # Malla de seguridad para los colores (cubre nombres formateados y crudos de la base de datos)
    colors_hydros = {
        "Estero": "#0284c7", "Puerto 1": "#0284c7",
        "Pozo": "#f97316", "Puerto 2": "#f97316",
        "Temperatura del aire (datalogger)": "#64748b"
    }
    colors_soil = {
        "Puerto 3": "#10b981", 
        "Puerto 4": "#eab308", 
        "Puerto 5": "#a855f7",
        "Temperatura del aire (datalogger)": "#64748b"
    }
    
    # Pestañas para las gráficas
    tab1, tab2, tab3 = st.tabs([
        "💧 Sensor Hydros 21 (Agua)", 
        "🌱 Sensor 5TE / 5TM (Suelo)", 
        "🔋 Estado del Sistema"
    ])
    
    # PESTAÑA 1: HYDROS 21 (AGUA)
    with tab1:
        st.subheader(f"Monitoreo de la Columna de Agua - Últimos {dias_seleccionados} días")
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
                    if not logger_temp_df.empty:
                        sub_temp = pd.concat([sub_temp, logger_temp_df], ignore_index=True)
                    
                    unit_str = sub_temp['Unidad'].iloc[0]
                    fig = crear_grafico_estilizado(sub_temp, "Temperatura del Agua vs Aire", f"Temperatura ({unit_str})", colors_hydros)
                    st.plotly_chart(fig, use_container_width=True)
                    
            with col3:
                sub_ec = hydros_df[hydros_df['Variable'] == 'EC']
                if not sub_ec.empty:
                    unit_str = sub_ec['Unidad'].iloc[0]
                    fig = crear_grafico_estilizado(sub_ec, "Conductividad Eléctrica", f"Conductividad ({unit_str})", colors_hydros)
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No se encontraron datos del sensor Hydros 21 en este periodo.")

    # PESTAÑA 2: SENSORES DE SUELO
    with tab2:
        st.subheader(f"Humedad y Temperatura de Suelo - Últimos {dias_seleccionados} días")
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
                    if not logger_temp_df.empty:
                        sub_st = pd.concat([sub_st, logger_temp_df], ignore_index=True)
                        
                    unit_str = sub_st['Unidad'].iloc[0]
                    fig = crear_grafico_estilizado(sub_st, "Temperatura de Suelo vs Aire", f"Temperatura ({unit_str})", colors_soil)
                    st.plotly_chart(fig, use_container_width=True)
                    
            with col3:
                sub_sec = soil_df[soil_df['Variable'] == 'Saturation Extract EC']
                if not sub_sec.empty:
                    unit_str = sub_sec['Unidad'].iloc[0]
                    fig = crear_grafico_estilizado(sub_sec, "EC Extracto Saturación", f"Salinidad ({unit_str})", colors_soil)
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No se encontraron datos de los sensores de suelo en este periodo.")

    # PESTAÑA 3: DIAGNÓSTICO DEL SISTEMA
    with tab3:
        st.subheader(f"Parámetros de Diagnóstico y Referencia - Últimos {dias_seleccionados} días")
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
    st.warning("La base de datos histórica en Google Sheets está vacía o no se ha podido leer correctamente.")

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