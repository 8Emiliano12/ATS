import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai

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
            evaluaciones = supabase.table("evaluaciones").select("*, usuarios(nombre)").order("id", desc=True).execute()
            
            for ev in evaluaciones.data:
                nombre_jugador = ev['usuarios']['nombre'] if ev['usuarios'] else "Desconocido"
                
                with st.expander(f"Evaluación de {nombre_jugador} (Visualizar)"):
                    st.write("**Perfil IA Generado:**")
                    st.write(ev.get("perfil_ia", "No generado"))
                    
                    if st.button("🗑️ Borrar Prueba", key=f"del_{ev['id']}"):
                        supabase.table("evaluaciones").delete().eq("id", ev["id"]).execute()
                        st.warning("Prueba eliminada.")
                        st.rerun()

        with tab_roster:
            st.subheader("Roster del Equipo")
            jugadores = supabase.table("usuarios").select("*").eq("rol", "jugador").execute()
            for jug in jugadores.data:
                st.write(f"🏈 **{jug['nombre']}** | {jug['correo']}")

    # --- VISTA ATLETA (JUGADOR) ---
    else:
        st.title("Portal del Atleta")
        st.write("Responde los siguientes cuestionarios con honestidad. El sistema analizará tus respuestas.")
        
        t_poms, t_acsi, t_iped, t_geq = st.tabs(["POMS", "ACSI-28", "IPED", "GEQ"])
        
        # 1. POMS
        with t_poms:
            st.subheader("Cuestionario POMS - Perfil de Estados de Ánimo")
            st.write("Indique cómo se siente en este preciso momento.")
            items_poms = ["Enfadado", "Agotado", "Lleno de energía", "Amable", "Con los nervios de punta", "Infeliz", "Malhumorado", "Fatigado", "Enérgico", "Comprensivo", "Nervioso", "Triste", "Irritable", "Cansado", "Activo", "Servicial", "Tenso", "Desesperanzado", "Molesto", "Débil", "Animado", "Amistoso", "Agitado", "Solo", "Resentido", "Exhausto", "Vigoroso", "Considerado con los demás", "Inquieto", "Melancólico"]
            opciones_poms = ["0 (Nada)", "1 (Un poco)", "2 (Moderadamente)", "3 (Bastante)", "4 (Muchísimo)"]
            
            respuestas_poms = []
            for i, item in enumerate(items_poms):
                respuestas_poms.append(st.selectbox(f"{i+1}. {item}", opciones_poms, key=f"poms_{i}"))
                
            if st.button("Enviar POMS"):
                # Extracción simple de valores (0 a 4)
                valores = [int(r.split(" ")[0]) for r in respuestas_poms]
                # Agrupación técnica por subescalas del POMS (5 items c/u aprox)
                colera = sum([valores[0], valores[6], valores[12], valores[18], valores[24]])
                fatiga = sum([valores[1], valores[7], valores[13], valores[19], valores[25]])
                vigor = sum([valores[2], valores[8], valors[14], valores[20], valores[26]])
                amistad = sum([valores[3], valores[9], valores[15], valores[21], valores[27]])
                tension = sum([valores[4], valores[10], valores[16], valores[22], valores[28]])
                depresion = sum([valores[5], valores[11], valores[17], valores[23], valores[29]])
                
                detalles = f"[POMS] Cólera: {colera}, Fatiga: {fatiga}, Vigor: {vigor}, Amistad: {amistad}, Tensión: {tension}, Depresión: {depresion}"
                with st.spinner("Enviando y analizando..."):
                    perfil = generar_perfil_ia(usuario_actual['nombre'], detalles)
                    supabase.table("evaluaciones").insert({"jugador_id": usuario_actual["id"], "poms_total": 0, "acsi_total": 0, "perfil_ia": perfil}).execute()
                st.success("POMS enviado exitosamente.")

        # 2. ACSI-28
        with t_acsi:
            st.subheader("ACSI-28 - Habilidades de Afrontamiento Deportivo")
            items_acsi = ["Establezco metas específicas...", "Obtengo el máximo provecho de mi talento...", "Tiendo a tomar los errores como algo personal...", "Puedo concentrarme y bloquear distracciones...", "Permanezco positivo durante la competencia...", "Rindo mejor bajo presión...", "Me preocupa lo que otros piensen...", "Planifico cómo alcanzar mis metas...", "Me siento seguro de que jugaré bien...", "Cuando me critican, me molesto...", "Evito pensamientos distractores...", "Me presiono demasiado...", "Establezco metas para cada entrenamiento...", "No necesito que me impulsen; doy el 100%...", "Si me critican, corrijo el error sin alterarme...", "Manejo bien las situaciones inesperadas...", "Mantengo la calma cuando las cosas van mal...", "Disfruto más cuando hay presión...", "Me preocupa cometer errores...", "Tengo un plan de juego antes de competir...", "Puedo relajarme rápidamente...", "Acepto las situaciones de presión...", "Imagino qué ocurrirá si fracaso...", "Mantengo el control emocional...", "Dirijo mi atención a un solo objetivo...", "Si no alcanzo metas, me esfuerzo más...", "Mejoro escuchando indicaciones...", "Cometo menos errores bajo presión..."]
            opciones_acsi = ["0 - Casi nunca", "1 - A veces", "2 - A menudo", "3 - Casi siempre"]
            
            respuestas_acsi = []
            for i, item in enumerate(items_acsi):
                respuestas_acsi.append(st.selectbox(f"{i+1}. {item}", opciones_acsi, key=f"acsi_{i}"))
                
            if st.button("Enviar ACSI-28"):
                valores_acsi = [int(r.split(" ")[0]) for r in respuestas_acsi]
                # Agrupación general de ACSI
                adver = sum(valores_acsi[0:4])
                presion = sum(valores_acsi[4:8])
                metas = sum(valores_acsi[8:12])
                concen = sum(valores_acsi[12:16])
                preocup = sum(valores_acsi[16:20])
                confianza = sum(valores_acsi[20:24])
                entrena = sum(valores_acsi[24:28])
                total = sum(valores_acsi)
                
                detalles = f"[ACSI-28] Adversidad: {adver}, Presión: {presion}, Metas: {metas}, Concentración: {concen}, Libre Preocupación: {preocup}, Confianza: {confianza}, Entrenabilidad: {entrena} (Total: {total})"
                with st.spinner("Enviando y analizando..."):
                    perfil = generar_perfil_ia(usuario_actual['nombre'], detalles)
                    supabase.table("evaluaciones").insert({"jugador_id": usuario_actual["id"], "poms_total": 0, "acsi_total": 0, "perfil_ia": perfil}).execute()
                st.success("ACSI-28 enviado exitosamente.")

        # 3. IPED
        with t_iped:
            st.subheader("IPED - Inventario Psicológico de Ejecución Deportiva")
            items_iped = ["Me veo más como un ganador que como perdedor...", "Mantengo flujo de energía en situaciones difíciles...", "Fácil concentrarme y bloquear distracciones...", "Imagino mis ejecuciones antes de competir...", "Estoy altamente motivado para entrenar...", "Transformo errores en aprendizaje...", "Actitud positiva con compañeros...", "Creo en mi capacidad para el éxito...", "Controlo la ira y frustración...", "Enfoco atención en la siguiente jugada...", "Practico mentalmente habilidades físicas...", "Las metas me hacen trabajar duro...", "Disfruto la competición bajo presión...", "Me comunico de manera abierta...", "Mantengo confianza al cometer errores...", "Elimino emociones negativas rápidamente...", "Foco en tarea sin pensar en errores pasados...", "Visualizo soluciones exitosas...", "Siento entusiasmo al practicar...", "Sensación de desafío en situaciones complejas..."]
            opciones_iped = ["1 - Casi nunca", "2 - Pocas veces", "3 - A veces", "4 - A menudo", "5 - Casi siempre"]
            
            respuestas_iped = []
            for i, item in enumerate(items_iped):
                respuestas_iped.append(st.selectbox(f"{i+1}. {item}", opciones_iped, key=f"iped_{i}"))
                
            if st.button("Enviar IPED"):
                v_iped = [int(r.split(" ")[0]) for r in respuestas_iped]
                detalles = f"[IPED] AC:{sum(v_iped[0:3])}, CAN:{sum(v_iped[3:6])}, CAT:{sum(v_iped[6:9])}, CVI:{sum(v_iped[9:12])}, NM:{sum(v_iped[12:15])}, CAP:{sum(v_iped[15:18])}, CAC:{sum(v_iped[18:20])}"
                with st.spinner("Enviando y analizando..."):
                    perfil = generar_perfil_ia(usuario_actual['nombre'], detalles)
                    supabase.table("evaluaciones").insert({"jugador_id": usuario_actual["id"], "poms_total": 0, "acsi_total": 0, "perfil_ia": perfil}).execute()
                st.success("IPED enviado exitosamente.")

        # 4. GEQ
        with t_geq:
            st.subheader("GEQ - Cuestionario de Cohesión Grupal")
            items_geq = ["No disfruto actividades sociales del equipo...", "No estoy satisfecho con mi tiempo de juego...", "No extrañaré al equipo al terminar...", "No estoy satisfecho con el deseo de ganar...", "Algunos de mis mejores amigos están aquí...", "El equipo no me brinda oportunidades para mejorar...", "Prefiero otras reuniones sociales...", "No me gusta el estilo de trabajo del equipo...", "El equipo es uno de mis grupos sociales más importantes...", "Equipo unido para alcanzar objetivos...", "Miembros prefieren salir por su cuenta...", "Asumimos responsabilidad por bajo rendimiento...", "Rara vez convivimos fuera del deporte...", "Aspiraciones contradictorias sobre el rendimiento...", "Nos gustaría pasar tiempo juntos fuera de temporada...", "Si alguien tiene problemas, todos ayudan...", "No permanecemos unidos fuera de entrenamientos...", "No nos comunicamos libremente sobre responsabilidades..."]
            
            respuestas_geq = []
            for i, item in enumerate(items_geq):
                respuestas_geq.append(st.slider(f"{i+1}. {item}", 1, 9, 5, key=f"geq_{i}"))
                
            if st.button("Enviar GEQ"):
                # División básica para Tarea y Social
                tarea = round(sum(respuestas_geq[:9]) / 9, 2)
                social = round(sum(respuestas_geq[9:]) / 9, 2)
                detalles = f"[GEQ] Promedio Tarea: {tarea}, Promedio Social: {social}"
                
                with st.spinner("Enviando y analizando..."):
                    perfil = generar_perfil_ia(usuario_actual['nombre'], detalles)
                    supabase.table("evaluaciones").insert({"jugador_id": usuario_actual["id"], "poms_total": 0, "acsi_total": 0, "perfil_ia": perfil}).execute()
                st.success("GEQ enviado exitosamente.")
