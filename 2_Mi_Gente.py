# © 2025 Pablo Díaz-Masa. Licenciado bajo CC BY-NC-ND 4.0.
# Ver LICENSE o https://creativecommons.org/licenses/by-nc-nd/4.0/

import streamlit as st
import json
import os
from copy import deepcopy
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from firestore_utils import get_firestore_client, add_document, get_all_documents, update_document, delete_document
from gcs_utils import read_csv_from_gcs

current_user_id = st.session_state.get("user_id")

if not current_user_id:
    st.warning("Por favor, inicia sesión en la página principal para acceder.")
    st.stop()

# CONFIGURACIÓN GENERAL
FIRESTORE_COLLECTION = "sujetos" #

@st.cache_data(show_spinner=False)
def load_tech_skills() -> list[str]:
    df = read_csv_from_gcs("ESCO/skills_es.csv")
    return df["preferredLabel"].str.capitalize().tolist()

TECH_SKILLS_BASE = load_tech_skills()

SOFT_SKILLS_BASE = [
    "Trabajo en equipo", "Comunicación", "Liderazgo",
    "Gestión del tiempo", "Resolución de conflictos",
    "Pensamiento crítico", "Adaptabilidad", "Creatividad",
    "Organización", "Negociación", "Inteligencia Emocional",
    "Proactividad", "Orientación al cliente"
]
IDIOMAS_BASE     = [
    "Español", "Inglés", "Francés", "Alemán", "Italiano",
    "Portugués", "Chino", "Japonés", "Árabe", "Ruso",
    "Catalán", "Gallego", "Euskera", "Polaco"
]
NIVELES_IDIOMA   = [
    "Conocimiento bajo", "Básico", "Intermedio",
    "Avanzado", "Hablante nativo"
]

ESFERAS_BASE = {
    "laboral":     ["Jefe", "Subordinado", "Colega", "Mentor", "Cliente", "Proveedor", "Socio"],
    "familiar":    ["Padre", "Madre", "Hijo", "Hija", "Hermano", "Hermana",
                     "Sobrino", "Sobrina", "Abuelo", "Abuela", "Nieto", "Nieta", "Tío", "Tía", "Primo", "Prima"],
    "sentimental": ["Pareja", "Novio", "Novia", "Esposo", "Esposa", "Ex-pareja"],
    "académica":   ["Profesor", "Alumno", "Tutor", "Compañero", "Mentor", "Mentee"],
    "asistencial": ["Cuidador", "Paciente", "Médico", "Terapeuta", "Enfermero", "Asistente social"],
    "contractual": ["Cliente", "Proveedor", "Socio", "Consultor", "Prestamista",
                     "Inspector", "Becario", "Empleado", "Contratista", "Arrendador", "Arrendatario"],
}

NIVELES_RELACION = ["Muy bajo", "Bajo", "Medio", "Alto", "Muy alto"]

# UTILIDADES FIRESTORE
def load_data_from_firestore() -> list[dict]:
    """
    Carga la lista de sujetos desde Firestore.
    Devuelve una lista vacía si la colección no tiene documentos.
    """
    try:
        db = get_firestore_client()
        docs = get_all_documents(db, current_user_id, FIRESTORE_COLLECTION)
        personas = []
        for doc in docs:
            persona_data = doc.to_dict()
            persona_data["ID"] = doc.id
            personas.append(persona_data)
        return personas
    except Exception as err:
        st.error(f"Error al cargar datos desde Firestore: {err}. Se cargará una lista vacía.")
        return []

# FUNCIÓN DE VALIDACIÓN
def validar_persona(persona: dict) -> tuple[bool, str]:
    """
    Comprueba campos obligatorios y el rango de los componentes temperamentales.
    """
    nombre = persona.get("datos_personales", {}).get("nombre", "").strip()
    if not nombre:
        return False, "El nombre es obligatorio."
    
    temps = persona.get("componentes_temperamentales", {})
    if len(temps) != 7:
        return False, "Faltan puntajes temperamentales. Deben ser 7."
    for k, v in temps.items():
        if not isinstance(v, (int, float)) or not (0 <= v <= 17):
            return False, f"El valor de '{k}' debe ser un número entre 0 y 17."
    return True, ""

# INICIALIZACIÓN DE SESIÓN
if "password_entered" not in st.session_state:
    st.session_state.password_entered = True 

if not st.session_state.get("password_entered", False):
    st.warning("Por favor, inicia sesión en la página principal para acceder.")
    st.stop()

# Inicialización de variables de estado si no existen
if "personas" not in st.session_state:
    st.session_state.personas = load_data_from_firestore()
if "modo" not in st.session_state:
    st.session_state.modo = "listar"
if "persona_id_editar" not in st.session_state:
    st.session_state.persona_id_editar = None

# ENCABEZADO
st.title("👥 Mi Gente ")
#st.caption("Gestiona fichas detalladas de tus personas de referencia.")

# NUEVA PERSONA
col_head1, col_head2 = st.columns([3, 1])
with col_head2:
    if st.button("➕ Nueva persona"):
        st.session_state.modo = "nuevo"
        st.session_state.persona_id_editar = None
        st.rerun()

# FORMULARIO
def formulario_persona(persona: dict, es_nueva: bool):
    """
    Genera la interfaz de usuario para crear o modificar una persona.
    Devuelve el diccionario de la persona con los datos ingresados.
    """
    persona_temp = deepcopy(persona)

    st.subheader("Datos del Sujeto")

    # --- ID único ---
    if es_nueva:
        #st.info("El ID de la persona se generará automáticamente al guardar.")
        st.info("Completa los campos")
    else:
        st.info("Edita los campos pertinentes")
        st.session_state.persona_id_editar = persona_temp.get("ID")


    # --- Datos Personales ---
    with st.expander("📄 Datos personales", expanded=False):
        dp = persona_temp.setdefault("datos_personales", {})
        dp["nombre"] = st.text_input(
            "Nombre o apodo *",
            dp.get("nombre", ""),
            help="Cómo te refieres a esta persona. No se necesitan apellidos a menos que sean distintivos"
        )
        dp["sexo"]   = st.selectbox(
            "Sexo",
            ["", "Varón", "Mujer"],
            index=["", "Varón", "Mujer"].index(dp.get("sexo", ""))
        )
        dp["edad"]   = st.number_input(
            "Edad (años)",
            min_value=0, max_value=120, value=dp.get("edad", 0), step=1
        )
        dp["estado_civil"] = st.text_input(
            "Estado civil",
            dp.get("estado_civil", "")
        )
        dp["puesto_trabajo"] = st.text_input(
            "Puesto / profesión",
            dp.get("puesto_trabajo", "")
        )
        dp["otros_datos"] = st.text_area(
            "Otros datos",
            dp.get("otros_datos", ""),
            help="Cualquier otro dato relevante (ej: discapacidad, nacionalidad, cómo se comporta, etc.)"
        )

    # --- Componentes Temperamentales ---
    with st.expander("🧬 Componentes temperamentales*", expanded=False):
        st.markdown("Asigna una puntuación (entre 0 y 17) para cada componente temperamental. Estos campos son obligatorios.")
        ct = persona_temp.setdefault("componentes_temperamentales", {})
        for comp in ["Normaloide", "Histeroide", "Mánico", "Depresivo",
                     "Autístico", "Paranoide", "Epileptoide"]:
            ct[comp] = st.number_input(
                comp,
                min_value=0.0, max_value=17.0,
                value=float(ct.get(comp, 0.0)),
                step=0.5, format="%.1f",
                help=f"Puntuación para el componente '{comp}' (0-17)."
            )

    # ---------- Capacidades ----------
    with st.expander("💡 Capacidades", expanded=False):
        caps = persona_temp.setdefault("capacidades", {})

        st.markdown("##### Habilidades técnicas")
        current_tech_skills = caps.get("Habilidades técnicas", [])
        all_tech_skills_options = sorted(list(set(TECH_SKILLS_BASE + current_tech_skills)))
        
        selected_tech_skills = st.multiselect(
            "Selecciona o añade habilidades técnicas",
            options=all_tech_skills_options,
            default=current_tech_skills,
            help="Selecciona habilidades de la lista y pulsa Enter"
        )
        new_tech_skills_input = st.text_input("Añadir otras habilidades técnicas (separadas por coma)", "")
        if new_tech_skills_input:
            new_skills = [s.strip() for s in new_tech_skills_input.split(',') if s.strip()]
            selected_tech_skills = sorted(list(set(selected_tech_skills + new_skills)))
        caps["Habilidades técnicas"] = selected_tech_skills

        st.markdown("##### Soft skills")
        current_soft_skills = caps.get("Soft skills", [])
        all_soft_skills_options = sorted(list(set(SOFT_SKILLS_BASE + current_soft_skills)))

        selected_soft_skills = st.multiselect(
            "Selecciona o añade soft skills",
            options=all_soft_skills_options,
            default=current_soft_skills,
            help="Selecciona soft skills de la lista y pulsa Enter"
        )
        new_soft_skills_input = st.text_input("Añadir otras soft skills (separadas por coma)", "")
        if new_soft_skills_input:
            new_skills = [s.strip() for s in new_soft_skills_input.split(',') if s.strip()]
            selected_soft_skills = sorted(list(set(selected_soft_skills + new_skills)))
        caps["Soft skills"] = selected_soft_skills

        st.markdown("##### Idiomas")
        st.info("Añade cada idioma y su nivel")
        idiomas_actual = caps.get("Idiomas", [])
        df_idiomas = pd.DataFrame(idiomas_actual or [{"Idioma": "", "Nivel": ""}])
        
        all_idiomas_options = sorted(list(set(IDIOMAS_BASE + [i["Idioma"] for i in idiomas_actual if i["Idioma"]])))

        df_editado = st.data_editor(
            df_idiomas,
            num_rows="dynamic",
            column_config={
                "Idioma": st.column_config.SelectboxColumn(
                    "Idioma", options=all_idiomas_options, required=False,
                    help="Selecciona un idioma"
                ),
                "Nivel": st.column_config.SelectboxColumn(
                    "Nivel", options=[""] + NIVELES_IDIOMA, required=False,
                    help="Nivel de dominio del idioma"
                ),
            },
            hide_index=True,
            use_container_width=True,
        )
        caps["Idiomas"] = [
            {"Idioma": row["Idioma"], "Nivel": row["Nivel"]}
            for _, row in df_editado.iterrows()
            if row["Idioma"] and row["Nivel"]
        ]

    # Relaciones
    with st.expander("🔗 Relaciones", expanded=False):
        rel = persona_temp.setdefault("relaciones", {})
        esf = rel.setdefault("esferas", {})
        
        st.markdown("##### Esferas de relación")
        st.info("Selecciona la relación de la persona contigo en las diferentes esferas")

        for esfera_key, base_options in ESFERAS_BASE.items():
            current_esfera_roles = esf.get(esfera_key, [])
            all_esfera_options = sorted(list(set(base_options + current_esfera_roles)))
            
            selected_roles = st.multiselect(
                esfera_key.capitalize(),
                options=all_esfera_options,
                default=current_esfera_roles,
                help=f"Roles de la persona en la esfera {esfera_key}."
            )
            esf[esfera_key] = selected_roles

        otras_esferas_str = "\n".join(esf.get("otras", []))
        otras_esferas_input = st.text_area(
            "Otras esferas (una por línea)",
            value=otras_esferas_str,
            help="Introduce cualquier otra esfera de relación (ej: religiosa, política, club social, etc.)"
        )
        esf["otras"] = [line.strip() for line in otras_esferas_input.splitlines() if line.strip()]

        carac = rel.setdefault("características", {})
        st.markdown("##### Características de la relación")

        carac["formalidad"] = st.selectbox(
            "Nivel de formalidad", NIVELES_RELACION,
            index=NIVELES_RELACION.index(carac.get("formalidad", "Medio"))
            if carac.get("formalidad") in NIVELES_RELACION else NIVELES_RELACION.index("Medio")
        )
        carac["amistad"] = st.selectbox(
            "Nivel de amistad", NIVELES_RELACION,
            index=NIVELES_RELACION.index(carac.get("amistad", "Medio"))
            if carac.get("amistad") in NIVELES_RELACION else NIVELES_RELACION.index("Medio")
        )
        carac["conflicto"] = st.selectbox(
            "Nivel de conflicto", NIVELES_RELACION,
            index=NIVELES_RELACION.index(carac.get("conflicto", "Medio"))
            if carac.get("conflicto") in NIVELES_RELACION else NIVELES_RELACION.index("Medio")
        )
        carac["otras"] = st.text_area(
            "Añade otras características",
            carac.get("otras", ""),
            help="Cualquier otra característica relevante del vínculo (respuesta abierta)"
        )
    
    # Guardar y Cancelar
    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button("💾 Guardar", use_container_width=True):
            ok, msg = validar_persona(persona_temp)
            if not ok:
                st.error(msg)
            else:
                db = get_firestore_client()
                persona_to_save = {k: v for k, v in persona_temp.items() if k != "ID"}

                if es_nueva:
                    try:
                        doc_ref = add_document(db, current_user_id, FIRESTORE_COLLECTION, persona_to_save)
                        st.success(f"Persona '{persona_temp['datos_personales']['nombre']}' creada correctamente.")
                    except Exception as e:
                        st.error(f"Error al crear la persona: {e}")
                else:
                    try:
                        update_document(db, current_user_id, FIRESTORE_COLLECTION, st.session_state.persona_id_editar, persona_to_save)
                        st.success(f"Persona '{persona_temp['datos_personales']['nombre']}' actualizada correctamente.")
                    except Exception as e:
                        st.error(f"Error al actualizar la persona: {e}")

                st.session_state.modo = "listar"
                st.session_state.personas = load_data_from_firestore()
                st.rerun()
    with col_cancel:
        if st.button("Cancelar", type="secondary", use_container_width=True):
            st.session_state.modo = "listar"
            st.rerun()

# FLUJO PRINCIPAL DE LA APLICACIÓN
if st.session_state.modo == "nuevo":
    formulario_persona({}, es_nueva=True)

elif st.session_state.modo == "editar":
    persona_sel_id = st.session_state.persona_id_editar
    persona_sel = next((p for p in st.session_state.personas if p.get("ID") == persona_sel_id), None)
    
    if persona_sel:
        st.write(f"### Editar persona **{persona_sel.get('datos_personales', {}).get('nombre', 'Sin nombre')}**")
        formulario_persona(persona_sel, es_nueva=False)
    else:
        st.error("No se encontró la persona para editar. Volviendo al listado.")
        st.session_state.modo = "listar"
        st.rerun()

else:
    #st.subheader("Personas caracterizadas")
    if not st.session_state.personas:
        st.info("Aún no tienes registros. Crea una nueva persona para empezar.")

    if "confirm_delete_id" not in st.session_state:
        st.session_state.confirm_delete_id = None
    if "confirm_delete_name" not in st.session_state:
        st.session_state.confirm_delete_name = None

    for p in st.session_state.personas:
        nombre = p.get("datos_personales", {}).get("nombre", "Sin nombre")
        persona_firestore_id = p.get("ID", "N/A")

        with st.expander(f"**{nombre}**"):
            st.markdown("##### Datos personales")
            #st.json(p.get("datos_personales", {}))
            dp = p.get("datos_personales", {})
            if dp:
                st.write(f"**Nombre:** {dp.get('nombre', 'N/A')}")
                st.write(f"**Sexo:** {dp.get('sexo', 'N/A')}")
                st.write(f"**Edad:** {dp.get('edad', 'N/A')}")
                st.write(f"**Estado civil:** {dp.get('estado_civil', 'N/A')}")
                st.write(f"**Puesto / profesión:** {dp.get('puesto_trabajo', 'N/A')}")
                st.write(f"**Otros datos:** {dp.get('otros_datos', 'N/A')}")
            else:
                st.info("No hay datos personales registrados.")

            st.markdown("##### Componentes temperamentales")
            # Aquí va el bloque de la gráfica de componentes temperamentales
            ct_data = p.get("componentes_temperamentales", {})
            if ct_data and all(comp in ct_data for comp in ["Normaloide", "Histeroide", "Mánico", "Depresivo", "Autístico", "Paranoide", "Epileptoide"]):
                # Mostrar valores como texto antes de la gráfica
                for comp in ["Normaloide", "Histeroide", "Mánico", "Depresivo", "Autístico", "Paranoide", "Epileptoide"]:
                    st.write(f"- **{comp}:** {ct_data.get(comp, 'N/A')}")
                df_temperamentos = pd.DataFrame(ct_data.items(), columns=['Componente', 'Puntuación'])
                df_temperamentos['Puntuación'] = df_temperamentos['Puntuación'].astype(float)

                orden_componentes = ["Normaloide", "Histeroide", "Mánico", "Depresivo", "Autístico", "Paranoide", "Epileptoide"]
                df_temperamentos['Componente'] = pd.Categorical(df_temperamentos['Componente'], categories=orden_componentes, ordered=True)
                df_temperamentos = df_temperamentos.sort_values('Componente')

                fig, ax = plt.subplots(figsize=(8, 2))

                sns.barplot(x='Puntuación', y='Componente', data=df_temperamentos, ax=ax, color='#808080', height=0.7)

                ax.set_xlim(0, 17)

                ax.set_facecolor('none')
                fig.patch.set_alpha(0)

                ax.set_xlabel("")
                ax.set_ylabel("")

                ax.set_xticks([])
                ax.set_xticklabels([])

                ax.tick_params(axis='y', labelsize=10, length=0, colors='#808080')

                for spine in ax.spines.values():
                    spine.set_visible(False)

                ax.grid(False)

                plt.tight_layout()

                st.pyplot(fig)
                plt.close(fig)
            elif ct_data:
                st.info("Ingresa los 7 valores de los componentes temperamentales para ver la gráfica en modo edición.")
            else:
                st.info("No hay componentes temperamentales registrados.")

            st.markdown("##### Capacidades")
            caps = p.get("capacidades", {})
            if caps:
                st.markdown("**Habilidades técnicas:**")
                st.write(", ".join(caps.get("Habilidades técnicas", [])) or "No especificadas")

                st.markdown("**Soft skills:**")
                st.write(", ".join(caps.get("Soft skills", [])) or "No especificadas")

                st.markdown("**Idiomas:**")
                idiomas = caps.get("Idiomas", [])
                if idiomas:
                    for lang in idiomas:
                        st.write(f"- {lang.get('Idioma', 'N/A')}: {lang.get('Nivel', 'N/A')}")
                else:
                    st.write("No especificados")
            else:
                st.write("No hay capacidades registradas.")

            st.markdown("##### Relaciones")
            rel = p.get("relaciones", {})
            if rel:
                st.markdown("**Esferas:**")
                esferas = rel.get("esferas", {})
                if esferas:
                    for esfera_key, roles in esferas.items():
                        if roles:
                            st.write(f"- **{esfera_key.capitalize()}:** {', '.join(roles)}")
                else:
                    st.write("No hay esferas de relación especificadas.")

                st.markdown("**Características del vínculo:**")
                carac = rel.get("características", {})
                if carac:
                    st.write(f"Formalidad: {carac.get('formalidad', 'N/A')}")
                    st.write(f"Amistad: {carac.get('amistad', 'N/A')}")
                    st.write(f"Conflicto: {carac.get('conflicto', 'N/A')}")
                    st.write(f"Otras: {carac.get('otras', 'N/A')}")
                else:
                    st.write("No hay características del vínculo especificadas.")
            else:
                st.write("No hay relaciones registradas.")

            # Botones de acción para editar o borrar la persona
            col_e, col_b = st.columns(2)
            with col_e:
                if st.button("✏️ Editar", key=f"edit_{persona_firestore_id}", use_container_width=True):
                    st.session_state.modo = "editar"
                    st.session_state.persona_id_editar = persona_firestore_id
                    st.rerun()
            with col_b:
                if st.button("🗑️ Borrar", key=f"del_{persona_firestore_id}", use_container_width=True):
                    st.session_state.confirm_delete_id = persona_firestore_id
                    st.session_state.confirm_delete_name = nombre
                    st.rerun()

    if st.session_state.confirm_delete_id is not None:
        st.warning(f"¿Estás seguro de eliminar definitivamente a '{st.session_state.confirm_delete_name}'?")
        col_confirm_yes, col_confirm_no = st.columns(2)
        with col_confirm_yes:
            if st.button("✅ Sí, borrar", key="confirm_yes", use_container_width=True):
                try:
                    db = get_firestore_client()
                    delete_document(db, current_user_id, FIRESTORE_COLLECTION, st.session_state.confirm_delete_id)
                    st.success(f"Persona '{st.session_state.confirm_delete_name}' eliminada correctamente.")
                except Exception as e:
                    st.error(f"Error al eliminar la persona: {e}")
                
                st.session_state.confirm_delete_id = None
                st.session_state.confirm_delete_name = None
                st.session_state.personas = load_data_from_firestore()
                st.rerun()
        with col_confirm_no:
            if st.button("❌ No, cancelar", key="confirm_no", use_container_width=True):
                st.session_state.confirm_delete_id = None
                st.session_state.confirm_delete_name = None
                st.rerun()