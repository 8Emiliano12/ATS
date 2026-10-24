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
                    
                    with st.expander("📋 Ver Respuestas del Atleta (Detalle)"):
                        st.text(ev.get("respuestas_detalladas", "Respuestas individuales no guardadas en versiones anteriores."))

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
                        with st.expander("📋 Ver Respuestas del Atleta (Detalle)"):
                            st.text(ev.get("respuestas_detalladas", "Respuestas individuales no guardadas en versiones anteriores."))
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
                    if st.button("Cancelar / Borrar Cita", key=f"del_cita_{cita['id']}"):
                        supabase.table("citas").delete().eq("id", cita["id"]).execute()
                        st.rerun()

        # --- TAB: ROSTER ---
        with t_roster:
            st.subheader("Asignar Pruebas al Roster")
            jugadores = supabase.table("usuarios").select("*").eq("rol", "jugador").execute()
            for jug in jugadores.data:
                with st.expander(f"🏈 {jug['nombre']} | Asignada: {jug.get('pruebas_desbloqueadas', 'Ninguna')}"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        prueba_sel = st.selectbox("Selecciona la prueba a enviar:", ["Ninguna", "POMS", "ACSI-28", "IPED", "GEQ", "Todas"], key=f"sel_{jug['id']}")
                    with col2:
                        st.write("") 
                        st.write("")
                        if st.button("Enviar", key=f"btn_{jug['id']}"):
                            supabase.table("usuarios").update({"pruebas_desbloqueadas": prueba_sel}).eq("id", jug["id"]).execute()
                            st.success(f"Prueba actualizada para {jug['nombre']}")
                            st.rerun()

    # ==========================================
    # VISTA ATLETA (JUGADOR)
    # ==========================================
    else:
        st.title("Portal del Atleta")
        t_prueba, t_historial, t_cita = st.tabs(["📋 Prueba Pendiente", "📁 Mi Historial", "📅 Agendar Cita"])
        
        # --- TAB: PRUEBA PENDIENTE ---
        with t_prueba:
            prueba_asignada = usuario_actual.get("pruebas_desbloqueadas", "Ninguna")
            
            if prueba_asignada == "Ninguna":
                st.info("No tienes pruebas asignadas en este momento. El staff psicológico te notificará cuando debas realizar una evaluación.")
            else:
                st.write(f"Tienes asignada la evaluación: **{prueba_asignada}**. Responde con honestidad.")
                
                # --- POMS ---
                if prueba_asignada in ["POMS", "Todas"]:
                    with st.expander("📝 Abrir Cuestionario POMS", expanded=True):
                        items_poms = [
                            "Enfadado", "Agotado", "Lleno de energía", "Amable", "Con los nervios de punta", 
                            "Infeliz", "Malhumorado", "Fatigado", "Enérgico", "Comprensivo", 
                            "Nervioso", "Triste", "Irritable", "Cansado", "Activo", 
                            "Servicial", "Tenso", "Desesperanzado", "Molesto", "Débil", 
                            "Animado", "Amistoso", "Agitado", "Solo", "Resentido", 
                            "Exhausto", "Vigoroso", "Considerado con los demás", "Inquieto", "Melancólico"
                        ]
                        opciones_poms = ["0 (Nada)", "1 (Un poco)", "2 (Moderadamente)", "3 (Bastante)", "4 (Muchísimo)"]
                        respuestas_poms = [st.selectbox(f"{i+1}. {item}", opciones_poms, key=f"poms_{i}") for i, item in enumerate(items_poms)]
                            
                        if st.button("Enviar POMS"):
                            valores = [int(r.split(" ")[0]) for r in respuestas_poms]
                            colera = sum([valores[0], valores[6], valores[12], valores[18], valores[24]])
                            fatiga = sum([valores[1], valores[7], valores[13], valores[19], valores[25]])
                            vigor = sum([valores[2], valores[8], valores[14], valores[20], valores[26]])
                            amistad = sum([valores[3], valores[9], valores[15], valores[21], valores[27]])
                            tension = sum([valores[4], valores[10], valores[16], valores[22], valores[28]])
                            depresion = sum([valores[5], valores[11], valores[17], valores[23], valores[29]])
                            
                            detalles = f"[POMS] Cólera: {colera}, Fatiga: {fatiga}, Vigor: {vigor}, Amistad: {amistad}, Tensión: {tension}, Depresión: {depresion}"
                            
                            # Generar texto crudo para el psicólogo
                            resp_crudas = "\n".join([f"{item}: {resp}" for item, resp in zip(items_poms, respuestas_poms)])
                            
                            with st.spinner("Enviando y analizando..."):
                                perfil = generar_perfil_ia(usuario_actual['nombre'], detalles)
                                supabase.table("evaluaciones").insert({
                                    "jugador_id": usuario_actual["id"], 
                                    "tipo_prueba": "POMS", 
                                    "poms_total": sum(valores), 
                                    "acsi_total": 0, 
                                    "perfil_ia": perfil,
                                    "respuestas_detalladas": resp_crudas
                                }).execute()
                                supabase.table("usuarios").update({"pruebas_desbloqueadas": "Ninguna"}).eq("id", usuario_actual["id"]).execute()
                            st.success("Enviado exitosamente.")
                            st.rerun()

                # --- ACSI-28 ---
                if prueba_asignada in ["ACSI-28", "Todas"]:
                    with st.expander("📝 Abrir Cuestionario ACSI-28", expanded=True):
                        items_acsi = [
                            "Diaria o semanalmente establezco metas muy especificas que guian lo que hago.",
                            "Obtengo el maximo provecho de mi talento y habilidades.",
                            "Cuando un entrenador me dice como corregir un error, tiendo a tomarlo como algo personal y me molesta.",
                            "Puedo concentrarme y bloquear las distracciones.",
                            "Permanezco positivo y entusiasta durante la competencia, sin importar como vayan las cosas.",
                            "Tiendo a rendir mejor bajo presion porque pienso con mayor claridad.",
                            "Me preocupa bastante lo que otros piensen de mi rendimiento.",
                            "Tiendo a planificar mucho como alcanzar mis metas.",
                            "Me siento seguro de que jugare bien.",
                            "Cuando un entrenador me critica, me molesto mas de lo que me ayuda.",
                            "Me resulta facil evitar que pensamientos distractores interfieran.",
                            "Me presiono demasiado preocupandome por como rendire.",
                            "Establezco mis propias metas para cada entrenamiento.",
                            "No necesito que me impulsen a entrenar; doy el 100 por ciento.",
                            "Si un entrenador me critica o me grita, corrijo el error sin alterarme.",
                            "Manejo muy bien las situaciones inesperadas.",
                            "Cuando las cosas van mal, me digo que mantenga la calma y funciona.",
                            "Cuanta mas presion hay, mas disfruto la competencia.",
                            "Durante la competencia me preocupa cometer errores o fallar.",
                            "Tengo mi plan de juego preparado antes de competir.",
                            "Cuando me siento demasiado tenso, puedo relajarme rapidamente.",
                            "Las situaciones de presion son desafios que acepto.",
                            "Imagino que ocurrira si fracaso.",
                            "Mantengo el control emocional sin importar como vayan las cosas.",
                            "Me resulta facil dirigir mi atencion a un solo objetivo.",
                            "Cuando no alcanzo mis metas, me esfuerzo aun mas.",
                            "Mejoro escuchando atentamente las indicaciones del entrenador.",
                            "Cometo menos errores bajo presion porque me concentro mejor."
                        ]
                        opciones_acsi = ["0 - Casi nunca", "1 - A veces", "2 - A menudo", "3 - Casi siempre"]
                        respuestas_acsi = [st.selectbox(f"{i+1}. {item}", opciones_acsi, key=f"acsi_{i}") for i, item in enumerate(items_acsi)]
                            
                        if st.button("Enviar ACSI-28"):
                            v = [int(r.split(" ")[0]) for r in respuestas_acsi]
                            detalles = f"[ACSI-28] Adversidad: {sum(v[0:4])}, Presión: {sum(v[4:8])}, Metas: {sum(v[8:12])}, Concentración: {sum(v[12:16])}, Libre Preocupación: {sum(v[16:20])}, Confianza: {sum(v[20:24])}, Entrenabilidad: {sum(v[24:28])} (Total: {sum(v)})"
                            
                            # Generar texto crudo
                            resp_crudas = "\n".join([f"P{i+1}: {resp}" for i, resp in enumerate(respuestas_acsi)])
                            
                            with st.spinner("Enviando y analizando..."):
                                perfil = generar_perfil_ia(usuario_actual['nombre'], detalles)
                                supabase.table("evaluaciones").insert({
                                    "jugador_id": usuario_actual["id"], 
                                    "tipo_prueba": "ACSI-28", 
                                    "poms_total": 0, 
                                    "acsi_total": sum(v), 
                                    "perfil_ia": perfil,
                                    "respuestas_detalladas": resp_crudas
                                }).execute()
                                supabase.table("usuarios").update({"pruebas_desbloqueadas": "Ninguna"}).eq("id", usuario_actual["id"]).execute()
                            st.success("Enviado exitosamente.")
                            st.rerun()

                # --- IPED ---
                if prueba_asignada in ["IPED", "Todas"]:
                    with st.expander("📝 Abrir Cuestionario IPED", expanded=True):
                        items_iped = [
                            "Me veo mas como un ganador que como un perdedor durante las competiciones.",
                            "Puedo mantener un flujo de energia positiva en situaciones dificiles.",
                            "Me resulta facil concentrarme y bloquear distracciones.",
                            "Imagino con claridad mis ejecuciones tecnicas antes de competir.",
                            "Estoy altamente motivado para entrenar lo mejor que puedo cada dia.",
                            "Puedo transformar los errores en oportunidades de aprendizaje durante el juego.",
                            "Mantengo una actitud positiva y constructiva con mis companeros y entrenadores.",
                            "Creo firmemente en mi capacidad como deportista para alcanzar el exito.",
                            "Controlo la ira y la frustracion cuando las cosas no salen como quiero.",
                            "Puedo enfocar mi atencion de inmediato en el siguiente punto o jugada.",
                            "Practico mentalmente mis habilidades fisicas y tacticas con frecuencia.",
                            "Las metas que me he propuesto me hacen trabajar duro constantemente.",
                            "Puedo disfrutar de la competicion incluso en momentos de alta presion.",
                            "Me comunico de manera respetuosa y abierta sobre mis responsabilidades en el equipo.",
                            "Mantengo la confianza en mi mismo aun cuando pierdo o cometo errores.",
                            "Elimino emociones negativas rapidamente para volver a concentrarme.",
                            "Mantengo el foco en la tarea presente sin pensar en errores pasados.",
                            "Visualizo soluciones exitosas a situaciones dificiles antes de que ocurran.",
                            "Siento un genuino entusiasmo y disfrute al practicar mi deporte.",
                            "Me lleno de sensacion de desafio e inspiracion en situaciones complejas."
                        ]
                        opciones_iped = ["1 - Casi nunca", "2 - Pocas veces", "3 - A veces", "4 - A menudo", "5 - Casi siempre"]
                        respuestas_iped = [st.selectbox(f"{i+1}. {item}", opciones_iped, key=f"iped_{i}") for i, item in enumerate(items_iped)]
                            
                        if st.button("Enviar IPED"):
                            v = [int(r.split(" ")[0]) for r in respuestas_iped]
                            detalles = f"[IPED] AC:{sum(v[0:3])}, CAN:{sum(v[3:6])}, CAT:{sum(v[6:9])}, CVI:{sum(v[9:12])}, NM:{sum(v[12:15])}, CAP:{sum(v[15:18])}, CAC:{sum(v[18:20])}"
                            
                            resp_crudas = "\n".join([f"P{i+1}: {resp}" for i, resp in enumerate(respuestas_iped)])
                            
                            with st.spinner("Enviando y analizando..."):
                                perfil = generar_perfil_ia(usuario_actual['nombre'], detalles)
                                supabase.table("evaluaciones").insert({
                                    "jugador_id": usuario_actual["id"], 
                                    "tipo_prueba": "IPED", 
                                    "poms_total": 0, 
                                    "acsi_total": 0, 
                                    "perfil_ia": perfil,
                                    "respuestas_detalladas": resp_crudas
                                }).execute()
                                supabase.table("usuarios").update({"pruebas_desbloqueadas": "Ninguna"}).eq("id", usuario_actual["id"]).execute()
                            st.success("Enviado exitosamente.")
                            st.rerun()

                # --- GEQ ---
                if prueba_asignada in ["GEQ", "Todas"]:
                    with st.expander("📝 Abrir Cuestionario GEQ", expanded=True):
                        items_geq = [
                            "No disfruto formar parte de las actividades sociales de este equipo.",
                            "No estoy satisfecho(a) con la cantidad de tiempo de juego o participacion que tengo.",
                            "No voy a extrañar a los miembros de este equipo cuando termine la temporada.",
                            "No estoy satisfecho(a) con el nivel de deseo de ganar de mi equipo.",
                            "Algunos de mis mejores amigos estan en este equipo.",
                            "Este equipo no me brinda suficientes oportunidades para mejorar mi rendimiento personal.",
                            "Prefiero asistir a otras reuniones sociales que a las reuniones del equipo.",
                            "No me gusta el estilo de juego o trabajo de este equipo.",
                            "Para mi, este equipo es uno de los grupos sociales mas importantes a los que pertenezco.",
                            "Nuestro equipo esta unido para alcanzar sus objetivos de rendimiento.",
                            "Los miembros de nuestro equipo prefieren salir por su cuenta que reunirse como equipo.",
                            "Todos asumimos la responsabilidad por cualquier derrota o bajo rendimiento del equipo.",
                            "Los miembros de nuestro equipo rara vez conviven juntos fuera del deporte.",
                            "Los miembros de nuestro equipo tienen aspiraciones contradictorias respecto al rendimiento del equipo.",
                            "A los miembros de nuestro equipo les gustaria pasar tiempo juntos fuera de la temporada.",
                            "Si algun miembro tiene problemas durante el entrenamiento, todos quieren ayudarle para que vuelva a integrarse.",
                            "Los miembros de nuestro equipo no permanecen unidos fuera de los entrenamientos y los partidos.",
                            "Los miembros de nuestro equipo no se comunican libremente sobre las responsabilidades de cada atleta durante la competencia."
                        ]
                        respuestas_geq = [st.slider(f"{i+1}. {item}", 1, 9, 5, key=f"geq_{i}") for i, item in enumerate(items_geq)]
                            
                        if st.button("Enviar GEQ"):
                            tarea = round(sum(respuestas_geq[:9]) / 9, 2)
                            social = round(sum(respuestas_geq[9:]) / 9, 2)
                            detalles = f"[GEQ] Promedio Tarea: {tarea}, Promedio Social: {social}"
                            
                            resp_crudas = "\n".join([f"P{i+1}: Valor {resp}" for i, resp in enumerate(respuestas_geq)])
                            
                            with st.spinner("Enviando y analizando..."):
                                perfil = generar_perfil_ia(usuario_actual['nombre'], detalles)
                                supabase.table("evaluaciones").insert({
                                    "jugador_id": usuario_actual["id"], 
                                    "tipo_prueba": "GEQ", 
                                    "poms_total": 0, 
                                    "acsi_total": 0, 
                                    "perfil_ia": perfil,
                                    "respuestas_detalladas": resp_crudas
                                }).execute()
                                supabase.table("usuarios").update({"pruebas_desbloqueadas": "Ninguna"}).eq("id", usuario_actual["id"]).execute()
                            st.success("Enviado exitosamente.")
                            st.rerun()

        # --- TAB: HISTORIAL DEL ATLETA ---
        with t_historial:
            st.subheader("Mis Evaluaciones y Observaciones del Staff")
            mis_evals = supabase.table("evaluaciones").select("*").eq("jugador_id", usuario_actual["id"]).order("id", desc=True).execute()
            
            if not mis_evals.data:
                st.info("Aún no tienes evaluaciones registradas.")
                
            for ev in mis_evals.data:
                estado_tag = "🟢 Revisada" if ev.get("estado") == "Revisada" else "⏳ En Revisión"
                tipo = ev.get("tipo_prueba", "Evaluación Psicológica")
                
                with st.expander(f"{estado_tag} - Prueba: {tipo}"):
                    st.write("**Notas del Staff Psicológico:**")
                    if ev.get("notas_psicologo"):
                        st.info(ev["notas_psicologo"])
                    else:
                        st.write("El psicólogo aún no ha dejado observaciones adicionales.")

        # --- TAB: AGENDAR CITA ---
        with t_cita:
            st.subheader("Solicitar Cita con el Servicio Psicológico")
            st.write("Selecciona la fecha, hora y el motivo por el cual deseas agendar una sesión.")
            
            col_d, col_t = st.columns(2)
            with col_d:
                fecha_cita = st.date_input("Fecha preferida", min_value=datetime.date.today())
            with col_t:
                hora_cita = st.time_input("Hora preferida", datetime.time(12, 00))
                
            motivo_cita = st.text_area("Motivo de la sesión (Opcional - confidencial)", placeholder="Ej. Estrés pre-competitivo, manejo de ansiedad, etc.")
            
            if st.button("Enviar Solicitud de Cita"):
                nueva_cita = {
                    "jugador_id": usuario_actual["id"],
                    "fecha": str(fecha_cita),
                    "hora": str(hora_cita)[:5],
                    "motivo": motivo_cita,
                    "estado": "Pendiente"
                }
                try:
                    supabase.table("citas").insert(nueva_cita).execute()
                    st.success("Tu solicitud de cita ha sido enviada al staff. Te confirmarán pronto.")
                except Exception as e:
                    st.error(f"Error interno de Supabase: {e}")
