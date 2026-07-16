import os
import json
import requests
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN DE PARÁMETROS ---
# Reemplaza esto con el ID exacto de tu Google Sheet (lo encuentras en la URL de tu planilla)
SPREADSHEET_ID = "1xSGxvtVRHfuNygH6lt7BPq0v1TLIzt2dDYfybKmMprg" 

# Credenciales de la API de ZENTRA (se obtendrán de forma segura desde GitHub Secrets)
API_TOKEN = os.environ.get("ZENTRA_TOKEN")
DEVICE_SN = os.environ.get("DEVICE_SN")

# Credenciales de Google (se obtendrán de forma segura desde GitHub Secrets)
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDS")

def fetch_ultimas_24h(token, sn):
    """Consulta los datos de las últimas 24 horas a ZENTRA."""
    headers = {"Authorization": f"Token {token}"}
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=1) # Consultamos solo el último día para evitar colapsar la API
    
    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S").replace(" ", "%20")
    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S").replace(" ", "%20")
    
    url = (
        f"https://zentracloud.com/api/v4/get_readings/?"
        f"device_sn={sn}&"
        f"start_date={start_str}&"
        f"end_date={end_str}&"
        f"per_page=1000&"
        f"page_num=1"
    )
    
    response = requests.get(url, headers=headers, timeout=20)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error de API ZENTRA: {response.status_code} - {response.text}")
        return None

def main():
    if not API_TOKEN or not DEVICE_SN or not GOOGLE_CREDS_JSON:
        print("Faltan variables de entorno obligatorias en GitHub Secrets.")
        return

    # --- 2. CONECTARSE A GOOGLE SHEETS ---
    print("Conectando con Google Sheets...")
    creds_dict = json.loads(GOOGLE_CREDS_JSON)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1

    # --- 3. LEER DATOS EXISTENTES PARA EVITAR DUPLICADOS ---
    print("Leyendo registros existentes...")
    existing_records = sheet.get_all_records()
    
    # Creamos un conjunto (set) de tuplas (Fecha, Puerto, Variable) existentes para una búsqueda ultrarrápida
    existing_keys = set()
    for row in existing_records:
        # Guardamos la fecha como texto tal cual está en la hoja para poder comparar
        existing_keys.add((str(row.get("Fecha_Local")), str(row.get("Puerto")), str(row.get("Variable"))))

    # --- 4. CONSULTAR NUEVOS DATOS A ZENTRA ---
    print("Consultando datos de las últimas 24 horas a ZENTRA...")
    data_json = fetch_ultimas_24h(API_TOKEN, DEVICE_SN)
    
    if not data_json or 'data' not in data_json:
        print("No se recibieron datos nuevos o la respuesta de ZENTRA fue inválida.")
        return
        
    readings_dict = data_json['data']
    nuevas_filas = []
    
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
                    
                # Convertimos y limpiamos zona horaria
                timestamp = pd.to_datetime(raw_dt)
                if timestamp.tzinfo is not None:
                    timestamp = timestamp.tz_localize(None)
                
                fecha_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                val_raw = r.get("value")
                
                if val_raw is not None:
                    try:
                        val_float = float(val_raw)
                        if abs(val_float) < 9999:
                            # Asignamos la ubicación física igual que en la visualización
                            ubicacion = f"Puerto {port}"
                            if sensor_model == "CTD-10":
                                if port == "1":
                                    ubicacion = "Estero"
                                elif port == "2":
                                        ubicacion = "Pozo"
                            elif sensor_model in ["5TE", "5TM"]:
                                ubicacion = f"Puerto {port}"
                            
                            # Filtro estricto: solo agregamos si no existe previamente esta combinación exacta
                            key_check = (fecha_str, f"Puerto {port}", variable_name)
                            if key_check not in existing_keys:
                                nuevas_filas.append([
                                    fecha_str,
                                    f"Puerto {port}",
                                    sensor_model,
                                    ubicacion,
                                    variable_name,
                                    val_float,
                                    unit
                                ])
                    except (ValueError, TypeError):
                        pass

    # --- 5. ESCRIBIR EN GOOGLE SHEETS ---
    if nuevas_filas:
        # Ordenamos las filas por fecha de forma ascendente
        nuevas_filas.sort(key=lambda x: x[0])
        print(f"Se encontraron {len(nuevas_filas)} registros nuevos. Escribiendo en la planilla...")
        
        # Insertamos en lote (batch) al final del archivo para máxima eficiencia
        sheet.append_rows(nuevas_filas, value_input_option="USER_ENTERED")
        print("¡Datos históricos sincronizados exitosamente!")
    else:
        print("No hay registros nuevos para agregar. La planilla está al día.")

if __name__ == "__main__":
    main()