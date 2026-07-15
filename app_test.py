import streamlit as st
import requests

st.title("Diagnóstico de Conexión ZENTRA Cloud")

# Recuperar credenciales de los Secrets
api_token = st.secrets.get("ZENTRA_TOKEN", "")
device_sn = st.secrets.get("DEVICE_SN", "")

st.write(f"**Dispositivo configurado:** {device_sn}")
st.write(f"**Token configurado (primeros 5 caracteres):** {api_token[:5]}...")

if st.button("Probar Conexión con ZENTRA"):
    headers = {
        "Authorization": f"Token {api_token}"
    }
    url = f"https://api.zentracloud.com/v5/devices/{device_sn}/readings/"
    
    with st.spinner("Consultando API..."):
        try:
            response = requests.get(url, headers=headers)
            
            st.write(f"**Código de estado HTTP:** {response.status_code}")
            
            # Si el tipo de contenido no es JSON, imprimimos el error de redirección
            if "application/json" not in response.headers.get("Content-Type", ""):
                st.error("❌ El servidor de ZENTRA no devolvió datos. Devolvió una página web de login/redirección.")
                st.warning("Esto confirma que el Token de la API no es válido o no tiene permisos para este número de serie.")
                with st.expander("Ver respuesta HTML del servidor"):
                    st.code(response.text[:1000], language="html")
            else:
                st.success("✅ ¡Conexión exitosa! El servidor devolvió datos en formato JSON correcto.")
                st.json(response.json())
                
        except Exception as e:
            st.error(f"Error de red: {e}")