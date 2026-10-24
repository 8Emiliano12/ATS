import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import datetime

# --- CONFIGURACIÓN SEGURA ---
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
modelo_ia = genai.GenerativeModel('gemini-1.5-flash')

st.set_page_config(page_title="ATS Pumas CU", page_icon="🏈", layout="wide")

# --- DIAGNÓSTICO DE IA (EN BARRA LATERAL) ---
try:
    st.sidebar.warning("Modelos detectados por tu API Key:")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            st.sidebar.write(m.name)
except Exception as e:
    st.sidebar.error(f"Error al listar modelos: {e}")

# --- ESTADO DE SESIÓN ---
if "usuario" not in st.session_state:
    st.session_state.usuario = None

# --- FUNCIONES ---
def login(correo, password):
    res = supabase.table("usuarios").select("*").eq("correo", correo).eq("password", password).execute()
    if len(res.data) > 0:
        st.session_state.usuario = res.data[0]
        st.rerun()
    else:
        st.error("Credenciales incorrectas.")

def registrar(correo, password, nombre):
    try:
        nuevo = {"correo": correo, "password": password, "nombre": nombre, "rol": "jugador", "pruebas_desbloqueadas": "Ninguna"}
        supabase.table("usuarios").insert(nuevo).execute()
        st.success("Registro exitoso. Inicia sesión.")
    except Exception as e:
        st.error(f"El verdadero error de la base de datos es: {e}")

def generar_perfil_ia(nombre, poms, acsi):
    try:
        with open("manual.txt", "r", encoding="utf-8") as f:
            manual = f.read()
        prompt = f"Psicólogo de Pumas CU. Evalúa con ESTE manual:\n\n{manual}\n\nJUGADOR: {nombre}\nPOMS: {poms}\nACSI: {acsi}\n\nGenera perfil y 2 recomendaciones."
        respuesta = modelo_ia.generate_content(prompt)
        return respuesta.text
    except Exception as e:
        return f"Error real de Gemini: {e}"

# --- INTERFAZ PRINCIPAL ---
if st.session_state.usuario is None:
    st.title("ATS Pumas CU - Acceso")
    tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrarse"])
    
    with tab1:
        correo_login = st.text_input("Correo", key="login_correo")
        pass_login = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Entrar"):
            login(correo_login, pass_login)
            
    with tab2:
        nombre_reg = st.text_input("Nombre Completo")
        correo_reg = st.text_input("Correo", key="reg_correo")
        pass_reg = st.text_input("Contraseña", type="password", key="reg_pass")
        if st.button("Crear Cuenta"):
            registrar(correo_reg, pass_reg, nombre_reg)

else:
    usuario_actual = st.session_state.usuario
    st.sidebar.title(f"Bienvenido, {usuario_actual['nombre']}")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.usuario = None
        st.rerun()

    # --- VISTA STAFF (PSICÓLOGO) ---
    if usuario_actual["rol"] == "psicologo":
        st.title("Panel de Control - Staff Psicológico")
        tab_eval, tab_roster = st.tabs(["Evaluaciones", "Roster"])
        
        with tab_eval:
            st.subheader("Resultados y Perfiles IA")
            evaluaciones = supabase.table("evaluaciones").select("*, usuarios(nombre)").execute()
            
            for ev in evaluaciones.data:
                nombre_jugador = ev['usuarios']['nombre'] if ev['usuarios'] else "Desconocido"
                with st.expander(f"{nombre_jugador} - POMS: {ev['poms_total']} | ACSI: {ev['acsi_total']}"):
                    st.write("**Perfil IA Generado:**")
                    st.write(ev.get("perfil_ia", "No generado"))
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🔄 Regenerar Perfil IA", key=f"regen_{ev['id']}"):
                            with st.spinner("Conectando con Gemini..."):
                                nuevo_perfil = generar_perfil_ia(nombre_jugador, ev['poms_total'], ev['acsi_total'])
                                supabase.table("evaluaciones").update({"perfil_ia": nuevo_perfil}).eq("id", ev["id"]).execute()
                            st.success("Perfil actualizado exitosamente.")
                            st.rerun()
                    with col2:
                        if st.button("🗑️ Borrar Prueba", key=f"del_{ev['id']}"):
                            supabase.table("evaluaciones").delete().eq("id", ev["id"]).execute()
                            st.warning("Prueba eliminada de la base de datos.")
                            st.rerun()

        with tab_roster:
            st.subheader("Roster del Equipo")
            jugadores = supabase.table("usuarios").select("*").eq("rol", "jugador").execute()
            for jug in jugadores.data:
                st.write(f"🏈 **{jug['nombre']}** | {jug['correo']}")

    # --- VISTA ATLETA (JUGADOR) ---
    else:
        st.title("Portal del Atleta")
        st.write("Ingresa los resultados de tus pruebas psicométricas.")
        
        poms_val = st.number_input("Puntaje POMS Total", min_value=0, step=1)
        acsi_val = st.number_input("Puntaje ACSI Total", min_value=0, step=1)
        
        if st.button("Enviar Resultados"):
            with st.spinner("Procesando y generando perfil..."):
                perfil = generar_perfil_ia(usuario_actual['nombre'], poms_val, acsi_val)
                nueva_eval = {
                    "jugador_id": usuario_actual["id"],
                    "poms_total": poms_val,
                    "acsi_total": acsi_val,
                    "perfil_ia": perfil
                }
                supabase.table("evaluaciones").insert(nueva_eval).execute()
            st.success("Resultados enviados correctamente. El staff revisará tu perfil.")
