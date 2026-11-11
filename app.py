import streamlit as st
import pandas as pd
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

def login(correo_input, password_input):
    correo_limpio = correo_input.strip().lower()
    password_limpio = password_input.strip()
    try:
        res = supabase.table("usuarios").select("*").eq("correo", correo_limpio).eq("password", password_limpio).execute()
        if len(res.data) > 0:
            st.session_state.usuario = res.data[0]
            st.rerun()
        else:
            st.error("Credenciales incorrectas. Verifica mayúsculas y espacios.")
    except Exception as e:
        st.error(f"Error de conexión: {e}")

def registrar(correo, password, nombre):
    try:
        nuevo = {"correo": correo.strip().lower(), "password": password.strip(), "nombre": nombre.strip(), "rol": "jugador", "pruebas_desbloqueadas": "Ninguna", "periodo_asignado": "No definido"}
        supabase.table("usuarios").insert(nuevo).execute()
        st.success("Registro exitoso. Inicia sesión.")
    except Exception as e:
        st.error(f"Error de base de datos: {e}")

def generar_perfil_ia(nombre, detalles_prueba):
    try:
        with open("manual.txt", "r", encoding="utf-8") as f:
            manual = f.read()
        prompt = f"""Actúa como Psicólogo Deportivo de Pumas CU. Evalúa utilizando ESTE manual:

{manual}

JUGADOR: {nombre}
RESULTADOS:
{detalles_prueba}

INSTRUCCIÓN CRÍTICA: Escribe un perfil psicológico MUY CONCRETO, DIRECTO y BREVE para el psicólogo a cargo. NO uses introducciones largas ni texto laborioso. Ve directo al grano usando viñetas (bullet points) para destacar los hallazgos principales de los puntajes y finaliza con 2 recomendaciones prácticas y claras."""
        respuesta = modelo_ia.generate_content(prompt)
        return respuesta.text
    except Exception as e:
        return f"Error real de Gemini: {e}"

def generar_resumen_expediente(nombre, historial_texto):
    try:
        prompt = f"""Actúa como Psicólogo Deportivo de Pumas CU. Este es el historial consolidado de las pruebas psicométricas del atleta {nombre} a lo largo de diferentes periodos:

{historial_texto}

INSTRUCCIÓN CRÍTICA: Escribe un Resumen de Expediente MUY CONCRETO y DIRECTO en viñetas. Analiza la evolución del jugador cruzando la información de las distintas pruebas aplicadas y los periodos. Destaca fortalezas generales, áreas de riesgo persistentes y da una conclusión clínica breve. No uses introducciones laboriosas."""
        respuesta = modelo_ia.generate_content(prompt)
        return respuesta.text
    except Exception as e:
        return f"Error de Gemini: {e}"

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

    def marcar_prueba_completada(prueba_hecha):
        asignadas_str = usuario_actual.get("pruebas_desbloqueadas", "Ninguna")
        if asignadas_str == "Todas":
            lista = ["POMS", "ACSI-28", "IPED", "GEQ", "CPRD"]
        else:
            lista = [p.strip() for p in asignadas_str.split(",") if p.strip() != "Ninguna"]
            
        if prueba_hecha in lista:
            lista.remove(prueba_hecha)
            
        nuevo_estado = ", ".join(lista) if len(lista) > 0 else "Ninguna"
        nuevo_periodo = usuario_actual.get("periodo_asignado", "No definido") if nuevo_estado != "Ninguna" else "No definido"
        
        supabase.table("usuarios").update({
            "pruebas_desbloqueadas": nuevo_estado,
            "periodo_asignado": nuevo_periodo
        }).eq("id", usuario_actual["id"]).execute()

    if usuario_actual["rol"] == "psicologo":
        st.title("Panel de Control - Staff Psicológico")
        t_buzon, t_agenda, t_roster, t_expediente = st.tabs(["📥 Buzón", "🗓️ Agenda", "👥 Roster", "📁 Expedientes"])
        
        with t_buzon:
            st.subheader("Evaluaciones Pendientes de Revisión")
            evaluaciones = supabase.table("evaluaciones").select("*, usuarios(nombre)").order("id", desc=True).execute()
            pendientes = [ev for ev in evaluaciones.data if ev.get("estado") != "Revisada"]
            
            if not pendientes:
                st.info("No hay evaluaciones nuevas pendientes de revisión.")
                
            for ev in pendientes:
                nombre_jugador = ev['usuarios']['nombre'] if ev['usuarios'] else "Desconocido"
                tipo = ev.get("tipo_prueba", "Evaluación")
                periodo = ev.get("periodo", "No definido")
                
                with st.expander(f"🔴 NUEVA - {nombre_jugador} | {tipo} ({periodo})", expanded=False):
                    with st.expander("📋 Ver Respuestas del Atleta (Detalle)"):
                        st.text(ev.get("respuestas_detalladas", "Sin detalles."))

                    st.write("**Perfil IA Generado:**")
                    st.write(ev.get("perfil_ia", "No generado"))
                    
                    st.markdown("---")
                    notas = st.text_area("Tus notas y observaciones para el atleta:", key=f"nota_{ev['id']}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("💾 Marcar Revisada", key=f"rev_{ev['id']}"):
                            supabase.table("evaluaciones").update({"notas_psicologo": notas, "estado": "Revisada"}).eq("id", ev["id"]).execute()
                            st.success("Enviado al historial del atleta.")
                            st.rerun()
                    with col2:
                        if st.button("🤖 Regenerar IA", key=f"regen_{ev['id']}"):
                            with st.spinner("Reescribiendo análisis clínico..."):
                                det = f"Prueba: {tipo}\nPuntaje Total/Índices: {ev.get('puntaje_total', 'N/A')}\nRespuestas extraídas:\n{ev.get('respuestas_detalladas', '')}"
                                n_perfil = generar_perfil_ia(nombre_jugador, det)
                                supabase.table("evaluaciones").update({"perfil_ia": n_perfil}).eq("id", ev["id"]).execute()
                            st.rerun()
                    with col3:
                        if st.button("🗑️ Borrar Prueba", key=f"del_{ev['id']}"):
                            supabase.table("evaluaciones").delete().eq("id", ev["id"]).execute()
                            st.rerun()

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
                            st.rerun()
                    if st.button("Cancelar / Borrar Cita", key=f"del_cita_{cita['id']}"):
                        supabase.table("citas").delete().eq("id", cita["id"]).execute()
                        st.rerun()

        with t_roster:
            st.subheader("Asignar Pruebas al Roster")
            jugadores = supabase.table("usuarios").select("*").eq("rol", "jugador").execute()
            for jug in jugadores.data:
                estado_actual = jug.get('pruebas_desbloqueadas', 'Ninguna')
                periodo_actual = jug.get('periodo_asignado', 'No definido')
                with st.expander(f"🏈 {jug['nombre']} | Asignada: {estado_actual} ({periodo_actual})"):
                    col1, col2, col3 = st.columns([2, 2, 1])
                    with col1:
                        prueba_sel = st.multiselect("Pruebas a enviar:", ["POMS", "ACSI-28", "IPED", "GEQ", "CPRD"], key=f"sel_p_{jug['id']}")
                    with col2:
                        periodo_sel = st.selectbox("Etapa actual:", ["General", "Específico", "Pre temporada", "Pre competitivo", "Descarga"], key=f"sel_t_{jug['id']}")
                    with col3:
                        st.write("") 
                        st.write("")
                        if st.button("Enviar", key=f"btn_{jug['id']}"):
                            pruebas_texto = ", ".join(prueba_sel) if len(prueba_sel) > 0 else "Ninguna"
                            supabase.table("usuarios").update({
                                "pruebas_desbloqueadas": pruebas_texto,
                                "periodo_asignado": periodo_sel
                            }).eq("id", jug["id"]).execute()
                            st.success(f"Prueba actualizada para {jug['nombre']}")
                            st.rerun()

        with t_expediente:
            st.subheader("Expedientes Clínicos de Atletas")
            jugadores_exp = supabase.table("usuarios").select("*").eq("rol", "jugador").execute()
            for jug in jugadores_exp.data:
                with st.expander(f"📁 Expediente: {jug['nombre']}"):
                    evals_jugador = supabase.table("evaluaciones").select("*").eq("jugador_id", jug["id"]).order("id", desc=False).execute()
                    if not evals_jugador.data:
                        st.warning("Este atleta aún no tiene pruebas registradas.")
                    else:
                        st.markdown("**Historial de Pruebas Aplicadas:**")
                        historial_texto = ""
                        for e in evals_jugador.data:
                            tipo = e.get("tipo_prueba", "Prueba")
                            periodo = e.get("periodo", "No definido")
                            perfil_ia = e.get("perfil_ia", "Sin análisis")
                            notas_psic = e.get("notas_psicologo", "Sin notas")
                            
                            with st.expander(f"- **{tipo}** ({periodo}) - Estado: {e.get('estado')}"):
                                st.write("**Análisis IA Original:**")
                                st.write(perfil_ia)
                                if st.button("🤖 Regenerar Perfil IA", key=f"regen_exp_{e['id']}"):
                                    with st.spinner("La IA está reevaluando la prueba..."):
                                        det = f"Prueba: {tipo}\nPuntaje Total/Índices: {e.get('puntaje_total', 'N/A')}\nRespuestas:\n{e.get('respuestas_detalladas', '')}"
                                        n_perfil = generar_perfil_ia(jug['nombre'], det)
                                        supabase.table("evaluaciones").update({"perfil_ia": n_perfil}).eq("id", e["id"]).execute()
                                    st.rerun()
                                    
                            historial_texto += f"\n--- PRUEBA: {tipo} | PERIODO: {periodo} ---\nAnálisis IA original: {perfil_ia}\nNotas del Psicólogo: {notas_psic}\n"
                        
                        st.markdown("---")
                        st.markdown("**📊 Evolución Gráfica (Puntajes Totales):**")
                        df_evals = pd.DataFrame(evals_jugador.data)
                        for prueba_nombre in ["POMS", "ACSI-28", "IPED", "GEQ", "CPRD"]:
                            df_p = df_evals[df_evals["tipo_prueba"] == prueba_nombre]
                            if len(df_p) > 1:
                                st.write(f"*{prueba_nombre}*")
                                chart_data = df_p[["periodo", "puntaje_total"]].copy()
                                chart_data = chart_data.rename(columns={"periodo": "Etapa", "puntaje_total": "Puntaje"})
                                st.line_chart(chart_data.set_index("Etapa"))
                            elif len(df_p) == 1:
                                st.caption(f"Falta una evaluación más de {prueba_nombre} para mostrar la gráfica de tendencia.")

                        st.markdown("---")
                        st.markdown("**Resumen Consolidado del Expediente:**")
                        resumen_actual = jug.get("resumen_expediente")
                        if resumen_actual:
                            st.info(resumen_actual)
                        else:
                            st.write("Aún no se ha generado un resumen consolidado para este atleta.")
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("🧠 Generar Reporte (IA)", key=f"resumen_{jug['id']}"):
                                with st.spinner("Integrando historial y generando resumen clínico..."):
                                    nuevo_resumen = generar_resumen_expediente(jug['nombre'], historial_texto)
                                    supabase.table("usuarios").update({"resumen_expediente": nuevo_resumen}).eq("id", jug["id"]).execute()
                                st.success("Resumen generado exitosamente.")
                                st.rerun()
                        with col2:
                            if st.button("🗑️ Borrar Todo el Expediente", key=f"del_exp_{jug['id']}"):
                                supabase.table("evaluaciones").delete().eq("jugador_id", jug["id"]).execute()
                                supabase.table("usuarios").update({"resumen_expediente": ""}).eq("id", jug["id"]).execute()
                                st.rerun()

    else:
        st.title("Portal del Atleta")
        t_prueba, t_historial, t_cita = st.tabs(["📋 Prueba Pendiente", "📁 Mi Historial", "📅 Agendar Cita"])
        
        with t_prueba:
            prueba_asignada = usuario_actual.get("pruebas_desbloqueadas", "Ninguna")
            periodo_asignado = usuario_actual.get("periodo_asignado", "No definido")
            
            def tiene_prueba(nombre):
                if prueba_asignada == "Todas": return True
                return nombre in prueba_asignada
            
            if prueba_asignada == "Ninguna":
                st.info("No tienes pruebas asignadas en este momento. El staff psicológico te notificará cuando debas realizar una evaluación.")
            else:
                st.write(f"Tienes las siguientes evaluaciones asignadas para la etapa: **{periodo_asignado}**")
                
                if tiene_prueba("POMS"):
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
                            
                            total_poms = sum(valores)
                            detalles = (
                                f"[POMS. Recuerda que Vigor y Amistad son positivos, el resto negativos.]\n"
                                f"Cólera: {colera}, Fatiga: {fatiga}, Vigor: {vigor}, Amistad: {amistad}, Tensión: {tension}, Depresión: {depresion}"
                            )
                            resp_crudas = "\n".join([f"{item}: {resp}" for item, resp in zip(items_poms, respuestas_poms)])
                            
                            with st.spinner("Enviando y analizando..."):
                                perfil = generar_perfil_ia(usuario_actual['nombre'], detalles)
                                supabase.table("evaluaciones").insert({
                                    "jugador_id": usuario_actual["id"], 
                                    "tipo_prueba": "POMS", 
                                    "periodo": periodo_asignado,
                                    "puntaje_total": total_poms,
                                    "perfil_ia": perfil,
                                    "respuestas_detalladas": resp_crudas
                                }).execute()
                                marcar_prueba_completada("POMS")
                            st.success("POMS Enviado exitosamente.")
                            st.rerun()

                if tiene_prueba("ACSI-28"):
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
                            total_acsi = sum(v)
                            
                            met = sum([v[0], v[7], v[12], v[19]])
                            cnf = sum([v[1], v[8], v[13], v[25]])
                            ent = sum([v[2], v[9], v[14], v[26]])
                            con = sum([v[3], v[10], v[15], v[24]])
                            adv = sum([v[4], v[16], v[20], v[23]])
                            pre = sum([v[5], v[17], v[21], v[27]])
                            lib = sum([v[6], v[11], v[18], v[22]])
                            
                            detalles = (
                                f"[ACSI-28. Máximo 12 puntos por subescala. Puntajes altos son muy positivos (fortaleza mental).]\n"
                                f"Adversidad: {adv}, Presión: {pre}, Metas: {met}, Concentración: {con}, "
                                f"Libre Preocupación: {lib}, Confianza: {cnf}, Entrenabilidad: {ent} (Total: {total_acsi})"
                            )
                            resp_crudas = "\n".join([f"P{i+1}: {resp}" for i, resp in enumerate(respuestas_acsi)])
                            
                            with st.spinner("Enviando y analizando..."):
                                perfil = generar_perfil_ia(usuario_actual['nombre'], detalles)
                                supabase.table("evaluaciones").insert({
                                    "jugador_id": usuario_actual["id"], 
                                    "tipo_prueba": "ACSI-28", 
                                    "periodo": periodo_asignado,
                                    "puntaje_total": total_acsi,
                                    "perfil_ia": perfil,
                                    "respuestas_detalladas": resp_crudas
                                }).execute()
                                marcar_prueba_completada("ACSI-28")
                            st.success("ACSI-28 Enviado exitosamente.")
                            st.rerun()

                if tiene_prueba("IPED"):
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
                            ac_score = v[0] + v[7] + v[14]
                            can_score = v[1] + v[8] + v[15]
                            cat_score = v[2] + v[9] + v[16]
                            cvi_score = v[3] + v[10] + v[17]
                            nm_score = v[4] + v[11] + v[18]
                            cap_score = v[5] + v[12] + v[19]
                            cac_score = v[6] + v[13]
                            
                            total_iped = sum(v)
                            
                            detalles = (
                                f"[IPED - Escala corta. Máximo 15 pts por dimensión (CAC máx 10). "
                                f"Puntajes cercanos al máximo indican un excelente dominio mental, NO déficit.] \n"
                                f"AC:{ac_score}, CAN:{can_score}, CAT:{cat_score}, CVI:{cvi_score}, "
                                f"NM:{nm_score}, CAP:{cap_score}, CAC:{cac_score}"
                            )
                            resp_crudas = "\n".join([f"P{i+1}: {resp}" for i, resp in enumerate(respuestas_iped)])
                            
                            with st.spinner("Enviando y analizando..."):
                                perfil = generar_perfil_ia(usuario_actual['nombre'], detalles)
                                supabase.table("evaluaciones").insert({
                                    "jugador_id": usuario_actual["id"], 
                                    "tipo_prueba": "IPED", 
                                    "periodo": periodo_asignado,
                                    "puntaje_total": total_iped,
                                    "perfil_ia": perfil,
                                    "respuestas_detalladas": resp_crudas
                                }).execute()
                                marcar_prueba_completada("IPED")
                            st.success("IPED Enviado exitosamente.")
                            st.rerun()

                if tiene_prueba("GEQ"):
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
                            social_scores = [respuestas_geq[i] for i in range(0, 18, 2)]
                            tarea_scores = [respuestas_geq[i] for i in range(1, 18, 2)]
                            
                            tarea = round(sum(tarea_scores) / 9, 2)
                            social = round(sum(social_scores) / 9, 2)
                            total_geq = sum(respuestas_geq)
                            
                            detalles = f"[GEQ. Escala del 1 al 9. Puntajes altos muestran gran cohesión de equipo.]\nPromedio Tarea: {tarea}, Promedio Social: {social}"
                            resp_crudas = "\n".join([f"P{i+1}: Valor {resp}" for i, resp in enumerate(respuestas_geq)])
                            
                            with st.spinner("Enviando y analizando..."):
                                perfil = generar_perfil_ia(usuario_actual['nombre'], detalles)
                                supabase.table("evaluaciones").insert({
                                    "jugador_id": usuario_actual["id"], 
                                    "tipo_prueba": "GEQ", 
                                    "periodo": periodo_asignado,
                                    "puntaje_total": total_geq,
                                    "perfil_ia": perfil,
                                    "respuestas_detalladas": resp_crudas
                                }).execute()
                                marcar_prueba_completada("GEQ")
                            st.success("GEQ Enviado exitosamente.")
                            st.rerun()

                if tiene_prueba("CPRD"):
                    with st.expander("📝 Abrir Cuestionario CPRD (55 ítems)", expanded=True):
                        items_cprd = [
                            "1. Suelo tener problemas concentrándome mientras compito.",
                            "2. Mientras duermo, suelo darle muchas vueltas a la competición en la que voy a participar.",
                            "3. Tengo una gran confianza en mi técnica.",
                            "4. Algunas veces no me encuentro motivado(a) para entrenar.",
                            "5. Me llevo muy bien con otros miembros del equipo.",
                            "6. Rara vez me encuentro tan tenso(a) como para que mi tensión interfiera negativamente en mi rendimiento.",
                            "7. A menudo ensayo mentalmente lo que debo hacer justo antes de comenzar mi participación en una competición.",
                            "8. En la mayoría de competiciones confío en que lo haré bien.",
                            "9. Cuando lo hago mal suelo perder la concentración.",
                            "10. No se necesita mucho para que se debilite mi confianza en mí mismo(a).",
                            "11. Me importa más mi propio rendimiento que el rendimiento del equipo.",
                            "12. A menudo estoy muerto(a) de miedo en los momentos anteriores al comienzo de mi participación en una competencia.",
                            "13. Cuando cometo un error me cuesta olvidarlo para volver a concentrarme rápidamente en lo que tengo que hacer.",
                            "14. Cualquier pequeña lesión o un mal entrenamiento puede debilitar mi confianza en mi mismo(a).",
                            "15. Establezco metas u objetivos que debo alcanzar y normalmente los consigo.",
                            "16. Algunas veces siento una intensa ansiedad mientras estoy participando en una prueba.",
                            "17. Durante mi actuación en una competición mi atención parece fluctuar una y otra vez entre lo que tengo que hacer y otras cosas.",
                            "18. Me gusta trabajar con mis compañeros de equipo.",
                            "19. Tengo frecuentes dudas respecto a mis posibilidades de hacerlo bien en una competición.",
                            "20. Gasto mucha energía intentando estar tranquilo(a) antes de que comience una competición.",
                            "21. Cuando comienzo haciéndolo mal, mi confianza baja rápidamente.",
                            "22. Pienso que el espíritu de equipo es muy importante.",
                            "23. Cuando practico mentalmente lo que tengo que hacer, me 'veo' haciéndolo como si estuviera viéndome desde una pantalla de televisión.",
                            "24. Generalmente, puedo seguir participando con confianza, aunque se trate de una de mis peores actuaciones.",
                            "25. Cuando me preparo para participar en una prueba, intento imaginarme, desde mi propia perspectiva, lo que veré, haré o notaré cuando la situación sea real.",
                            "26. Mi confianza en mí mismo(a) es muy inestable.",
                            "27. Cuando mi equipo pierde me encuentro mal con independencia de mi rendimiento individual.",
                            "28. Cuando cometo un error en una competición me pongo muy ansioso.",
                            "29. En este momento, lo más importante en mi vida es hacer bien mi deporte.",
                            "30. Soy eficaz controlando mi tensión.",
                            "31. Mi deporte es toda mi vida.",
                            "32. Tengo fe en mi mismo(a).",
                            "33. Suelo encontrarme motivado(a) para superarme día a día.",
                            "34. A menudo pierdo la concentración durante la competición como consecuencia de las decisiones de los árbitros o jueces que considero desacertadas.",
                            "35. Cuando cometo un error durante una competición suele preocuparme lo que piensen otras personas como el entrenador o los compañeros.",
                            "36. El día anterior a una competición me encuentro habitualmente demasiado nervioso(a) o preocupado(a).",
                            "37. Suelo marcarme objetivos cuya consecución depende de mi al 100% en lugar de objetivos que no dependen sólo de mí.",
                            "38. Creo que la aportación específica de todos los miembros de un equipo es sumamente importante para la obtención del éxito del equipo.",
                            "39. No merece la pena dedicar tanto tiempo y esfuerzo como yo le dedico al deporte.",
                            "40. En las competiciones suelo animarme con palabras, pensamientos o imágenes.",
                            "41. A menudo pierdo la concentración durante una competición por preocuparme o ponerme a pensar en el resultado final.",
                            "42. Suelo aceptar bien las críticas e intento aprender de ellas.",
                            "43. Me concentro con facilidad en aquello que es lo más importante en cada momento de una competición.",
                            "44. Me cuesta aceptar que se destaque más la labor de otros miembros del equipo que la mía.",
                            "45. Cuando finaliza una competición analizo mi rendimiento de forma objetiva y específica.",
                            "46. A menudo pierdo la concentración en la competición a consecuencia de la actuación o los comentarios poco deportivos de los adversarios.",
                            "47. Me preocupan mucho las decisiones que respecto a mí pueda tomar el entrenador durante una competición.",
                            "48. No ensayo mentalmente, como parte de mi plan de entrenamiento, situaciones que debo corregir o mejorar.",
                            "49. Durante los entrenamientos suelo estar muy concentrado(a) en lo que tengo que hacer.",
                            "50. Suelo establecer objetivos prioritarios antes de cada sesión de entrenamiento y de cada competición.",
                            "51. Mi confianza en la competición depende en gran medida de los éxitos o fracasos en las competiciones anteriores.",
                            "52. Mi motivación depende en gran medida del reconocimiento que obtengo de los demás.",
                            "53. Las instrucciones, comentarios y gestos del entrenador suelen interferir negativamente en mi concentración durante la competición.",
                            "54. Suelo confiar en mí mismo(a) aun en los momentos más difíciles de una competición.",
                            "55. Estoy dispuesto(a) a cualquier esfuerzo por ser cada vez mejor."
                        ]
                        
                        opciones_cprd = ["1 - Totalmente en Desacuerdo", "2 - Moderadamente en Desacuerdo", "3 - Ni de acuerdo Ni en desacuerdo", "4 - Moderadamente de Acuerdo", "5 - Totalmente de Acuerdo"]
                        respuestas_cprd = [st.selectbox(item, opciones_cprd, key=f"cprd_{i}") for i, item in enumerate(items_cprd)]
                            
                        if st.button("Enviar CPRD"):
                            v = [int(r.split(" - ")[0]) for r in respuestas_cprd]
                            
                            def inv(val):
                                return 6 - val
                                
                            ce_score = sum([
                                inv(v[1]), inv(v[6]), inv(v[8]), v[12], inv(v[13]), inv(v[17]), inv(v[21]), 
                                inv(v[26]), v[28], inv(v[33]), inv(v[37]), inv(v[40]), v[43], v[45], 
                                inv(v[47]), v[49], inv(v[50]), v[51], inv(v[53]), inv(v[54])
                            ])
                            ier_score = sum([
                                inv(v[3]), inv(v[9]), v[15], inv(v[18]), inv(v[20]), v[25], 
                                inv(v[30]), inv(v[34]), inv(v[35]), inv(v[39]), inv(v[42]), v[46]
                            ])
                            mot_score = sum([
                                v[2], inv(v[7]), v[10], inv(v[16]), inv(v[23]), v[27], inv(v[38]), v[48]
                            ])
                            hm_score = sum([
                                v[0], v[5], v[14], v[22], inv(v[24]), v[29], v[31], inv(v[32]), v[41]
                            ])
                            ch_score = sum([
                                v[4], v[11], v[19], v[36], v[44], v[52]
                            ])
                            
                            total_cprd = ce_score + ier_score + mot_score + hm_score + ch_score
                            
                            detalles = (
                                f"[CPRD. ESCALA DEL 1 AL 5 INVERTIDA MATEMÁTICAMENTE: "
                                f"A MAYOR PUNTAJE, MEJOR CAPACIDAD Y SALUD MENTAL. PUNTOS BAJOS = RIESGO CLINICO.]\n"
                                f"Control Estrés: {ce_score}/100, Influencia Evaluación: {ier_score}/60, Motivación: {mot_score}/40, "
                                f"Habilidad Mental: {hm_score}/45, Cohesión: {ch_score}/30. (Total: {total_cprd}/275)"
                            )
                            
                            resp_crudas = "\n".join([f"P{i+1}: {resp}" for i, resp in enumerate(respuestas_cprd)])
                            
                            with st.spinner("Enviando y analizando..."):
                                perfil = generar_perfil_ia(usuario_actual['nombre'], detalles)
                                supabase.table("evaluaciones").insert({
                                    "jugador_id": usuario_actual["id"], 
                                    "tipo_prueba": "CPRD", 
                                    "periodo": periodo_asignado,
                                    "puntaje_total": total_cprd,
                                    "perfil_ia": perfil,
                                    "respuestas_detalladas": resp_crudas
                                }).execute()
                                marcar_prueba_completada("CPRD")
                            st.success("CPRD Enviado exitosamente.")
                            st.rerun()

        with t_historial:
            st.subheader("Mi Expediente y Citas")
            mis_citas = supabase.table("citas").select("*").eq("jugador_id", usuario_actual["id"]).order("id", desc=True).execute()
            
            if not mis_citas.data:
                st.info("No has solicitado ninguna cita por el momento.")
            else:
                for cita in mis_citas.data:
                    estado_cita = cita.get("estado", "Pendiente")
                    if estado_cita == "Pendiente":
                        st.warning(f"⏳ **En Revisión:** Cita solicitada para el {cita['fecha']} a las {cita['hora']}")
                    elif estado_cita == "Confirmada":
                        st.success(f"✅ **Aceptada:** Tienes una cita confirmada el {cita['fecha']} a las {cita['hora']}")
                    else:
                        st.info(f"ℹ️ **{estado_cita}:** {cita['fecha']} a las {cita['hora']}")

            st.markdown("---")
            st.markdown("### 🧠 Evaluaciones y Observaciones del Staff")
            mis_evals = supabase.table("evaluaciones").select("*").eq("jugador_id", usuario_actual["id"]).order("id", desc=True).execute()
            
            if not mis_evals.data:
                st.info("Aún no tienes evaluaciones registradas.")
            else:
                df_mis_evals = pd.DataFrame(mis_evals.data).sort_values(by="id", ascending=True)
                st.markdown("**📊 Mi Evolución Gráfica:**")
                for prueba_nombre in ["POMS", "ACSI-28", "IPED", "GEQ", "CPRD"]:
                    df_p = df_mis_evals[df_mis_evals["tipo_prueba"] == prueba_nombre]
                    if len(df_p) > 1:
                        st.write(f"*{prueba_nombre}*")
                        chart_data = df_p[["periodo", "puntaje_total"]].copy()
                        chart_data = chart_data.rename(columns={"periodo": "Etapa", "puntaje_total": "Puntaje"})
                        st.line_chart(chart_data.set_index("Etapa"))
                
                st.markdown("---")
                for ev in mis_evals.data:
                    estado_tag = "🟢 Revisada" if ev.get("estado") == "Revisada" else "⏳ En Revisión"
                    tipo = ev.get("tipo_prueba", "Evaluación Psicológica")
                    periodo = ev.get("periodo", "No definido")
                    
                    with st.expander(f"{estado_tag} - {tipo} ({periodo})"):
                        st.write(f"**Puntaje Total Calculado:** {ev.get('puntaje_total', 'N/A')}")
                        
                        with st.expander("📄 Ver mis respuestas enviadas"):
                            st.text(ev.get("respuestas_detalladas", "Respuestas no disponibles."))
                        
                        st.write("**Notas del Staff Psicológico:**")
                        if ev.get("notas_psicologo"):
                            st.info(ev["notas_psicologo"])
                        else:
                            st.write("El psicólogo aún no ha dejado observaciones adicionales.")

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
