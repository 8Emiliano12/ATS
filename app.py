import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import datetime

# --- CONFIGURACIÓN SEGURA ---
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
modelo_ia = genai.GenerativeModel('gemini-2.5-flash')

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
        st.error(f"Error de base de datos: {e}")

def generar_perfil_ia(nombre, detalles_prueba):
    try:
        with open("manual.txt", "r", encoding="utf-8") as f:
            manual = f.read()
        prompt = f"Actúa como Psicólogo de Pumas CU. Evalúa utilizando ESTE manual:\n\n{manual}\n\nJUGADOR: {nombre}\nRESULTADOS:\n{detalles_prueba}\n\nGenera el perfil psicológico estructurado y 2 recomendaciones específicas."
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
    res_user = supabase.table("usuarios").select("*").eq("id", st.session_state.usuario["id"]).execute()
    if len(res_user.data) > 0:
        usuario_actual = res_user.data[0]
        st.session_state.usuario = usuario_actual
    else:
        usuario_actual = st.session_state.usuario

    st.sidebar.title(f"Bienvenido, {usuario_actual['nombre']}")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.usuario = None
        st.rerun()

    # ==========================================
    # VISTA STAFF (PSICÓLOGO)
    # ==========================================
    if usuario_actual["rol"] == "psicologo":
        st.title("Panel de Control - Staff Psicológico")
        t_buzon, t_agenda, t_roster = st.tabs(["📥 Buzón de Evaluaciones", "🗓️ Agenda de Citas", "👥 Roster y Asignación"])
        
        # --- TAB: BUZÓN ---
        with t_buzon:
            st.subheader("Evaluaciones Pendientes de Revisión")
            evaluaciones = supabase.table("evaluaciones").select("*, usuarios(nombre)").order("id", desc=True).execute()
            
            pendientes = [ev for ev in evaluaciones.data if ev.get("estado") != "Revisada"]
            revisadas = [ev for ev in evaluaciones.data if ev.get("estado") == "Revisada"]
            
            if not pendientes:
                st.info("No hay evaluaciones nuevas pendientes de revisión.")
                
            for ev in pendientes:
                nombre_jugador = ev['usuarios']['nombre'] if ev['usuarios'] else "Desconocido"
                tipo = ev.get("tipo_prueba", "Evaluación")
                
                with st.expander(f"🔴 NUEVA - {nombre_jugador} (Prueba: {tipo})", expanded=False):
                    st.write("**Perfil IA Generado:**")
                    st.write(ev.get("perfil_ia", "No generado"))
                    
                    st.markdown("---")
                    notas = st.text_area("Tus notas y observaciones para el atleta:", key=f"nota_{ev['id']}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("💾 Guardar y Marcar Revisada", key=f"rev_{ev['id']}"):
                            supabase.table("evaluaciones").update({"notas_psicologo": notas, "estado": "Revisada"}).eq("id", ev["id"]).execute()
                            st.success("Enviado al historial del atleta.")
                            st.rerun()
                    with col2:
                        if st.button("🗑️ Borrar Prueba", key=f"del_{ev['id']}"):
                            supabase.table("evaluaciones").delete().eq("id", ev["id"]).execute()
                            st.rerun()

            if revisadas:
                st.markdown("### Historial de Pruebas Revisadas")
                for ev in revisadas:
                    nombre_jugador = ev['usuarios']['nombre'] if ev['usuarios'] else "Desconocido"
                    tipo = ev.get("tipo_prueba", "Evaluación")
                    with st.expander(f"🟢 REVISADA - {nombre_jugador} (Prueba: {tipo})"):
                        st.write("**Perfil IA:**\n", ev.get("perfil_ia", ""))
                        st.write("**Tus Notas:**\n", ev.get("notas_psicologo", "Sin notas previas."))

        # --- TAB: AGENDA ---
        with t_agenda:
            st.subheader("Citas Solicitadas por Atletas")
            citas = supabase.table("citas").select("*, usuarios(nombre)").order("id", desc=True).execute()
            
            if not citas.data:
                st.info("No hay citas programadas por el momento.")
            
            for cita in citas.data:
                nombre = cita['usuarios']['nombre'] if cita['usuarios'] else "Desconocido"
                estado_icono = "📅" if cita['estado'] == "Pendiente" else "✅"
                with st.expander(f"{estado_icono} {nombre} - {cita['fecha']} a las {cita['hora']}"):
                    st.write(f"**Motivo:** {cita.get('motivo', 'No especificado')}")
                    st.write(f"**Estado Actual:** {cita.get('estado', 'Pendiente')}")
                    
                    if cita['estado'] == "Pendiente":
                        if st.button("Confirmar Cita", key=f"conf_cita_{cita['id']}"):
                            supabase.table("citas").update({"estado": "Confirmada"}).eq("id", cita["id"]).execute()
                            st.success("Cita confirmada.")
                            st.rerun()
                    if st.button("Cancelar
