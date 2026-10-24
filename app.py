import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import datetime

# --- CONFIGURACIÓN SEGURA ---
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
modelo_ia = genai.GenerativeModel('gemini-1.5-pro')

st.set_page_config(page_title="ATS Pumas CU", page_icon="🏈", layout="wide")

if "usuario" not in st.session_state:
    st.session_state.usuario = None

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

# --- PANTALLAS ---
if st.session_state.usuario is None:
    st.title("Acceso ATS Pumas CU 🏈")
    tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrarse"])
    
    with tab1:
        c_login = st.text_input("Correo")
        p_login = st.text_input("Contraseña", type="password")
        if st.button("Ingresar"): login(c_login, p_login)
            
    with tab2:
        n_reg = st.text_input("Nombre completo")
        c_reg = st.text_input("Correo institucional")
        p_reg = st.text_input("Crear Contraseña", type="password")
        if st.button("Registrarse"): registrar(c_reg, p_reg, n_reg)

else:
    usr = st.session_state.usuario
    col1, col2 = st.columns([8, 2])
    col1.title(f"Panel de {usr['nombre']}")
    if col2.button("Cerrar Sesión"):
        st.session_state.usuario = None
        st.rerun()
        
    st.divider()

    if usr['rol'] == 'jugador':
        evals = supabase.table("evaluaciones").select("*").eq("jugador_id", usr['id']).execute()
        if evals.data:
            st.info("Último Feedback:")
            st.write(f"**Psicólogo:** {evals.data[-1].get('recomendacion_psicologo', '-')}")
            st.write(f"**Staff:** {evals.data[-1].get('comentario_staff', '-')}")
            
        if usr['pruebas_desbloqueadas'] != "Ninguna":
            st.warning(f"Pruebas pendientes: {usr['pruebas_desbloqueadas']}")
            poms = st.number_input("POMS Total", min_value=0)
            acsi = st.number_input("ACSI Total", min_value=0)
            if st.button("Enviar Resultados"):
                with st.spinner("Procesando y guardando de forma segura..."):
                    perfil = generar_perfil_ia(usr['nombre'], poms, acsi)
                    supabase.table("evaluaciones").insert({"jugador_id": usr['id'], "poms_total": poms, "acsi_total": acsi, "perfil_ia": perfil}).execute()
                    supabase.table("usuarios").update({"pruebas_desbloqueadas": "Ninguna"}).eq("id", usr['id']).execute()
                st.success("Enviado al área de psicología.")
                st.rerun()
        else:
            st.success("No hay pruebas pendientes.")

    elif usr['rol'] == 'psicologo':
        tab_ev, tab_jg = st.tabs(["Evaluaciones", "Roster"])
        with tab_ev:
            todas = supabase.table("evaluaciones").select("*, usuarios(nombre)").execute()
            for ev in reversed(todas.data):
                with st.expander(f"{ev['usuarios']['nombre']} - {ev['fecha'][:10]}"):
                    st.write(f"**POMS:** {ev['poms_total']} | **ACSI:** {ev['acsi_total']}")
                    st.write("**Perfil IA:**", ev['perfil_ia'])
                    r = st.text_area("Recomendación al Jugador", value=ev.get('recomendacion_psicologo') or "", key=f"r_{ev['id']}")
                    s = st.text_area("Comentario Staff", value=ev.get('comentario_staff') or "", key=f"s_{ev['id']}")
                    if st.button("Guardar Feedback", key=f"b_{ev['id']}"):
                        supabase.table("evaluaciones").update({"recomendacion_psicologo": r, "comentario_staff": s}).eq("id", ev['id']).execute()
                        st.success("Guardado.")
                        
        with tab_jg:
            jugadores = supabase.table("usuarios").select("*").eq("rol", "jugador").execute()
            for j in jugadores.data:
                c1, c2, c3 = st.columns(3)
                c1.write(j['nombre'])
                c2.write(f"Estado: {j['pruebas_desbloqueadas']}")
                if c3.button("Asignar Pruebas", key=f"asg_{j['id']}"):
                    supabase.table("usuarios").update({"pruebas_desbloqueadas": "POMS y ACSI"}).eq("id", j['id']).execute()
                    st.rerun()
