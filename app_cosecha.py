# --- CONEXIÓN DE SEGURIDAD A GOOGLE SHEETS ---
@st.cache_data(ttl=600)  # Almacena en caché los datos por 10 minutos
def cargar_datos_historicos():
    try:
        # Recuperamos la línea plana de texto de los secrets
        google_creds_raw = st.secrets.get("GOOGLE_CREDS_RAW")
        sheet_id = st.secrets.get("HISTORICO_SHEETS_ID")
        
        if not google_creds_raw or not sheet_id:
            st.error("Faltan configurar las variables GOOGLE_CREDS_RAW o HISTORICO_SHEETS_ID en los Secrets.")
            return pd.DataFrame()
            
        # Transformamos el texto plano a un diccionario de Python
        creds_dict = json.loads(google_creds_raw)
        
        # Corregimos de forma interna los saltos de línea físicos de la clave PEM
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
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