# © 2025 Pablo Díaz-Masa. Licenciado bajo CC BY-NC-ND 4.0.
# Ver LICENSE o https://creativecommons.org/licenses/by-nc-nd/4.0/

import streamlit as st
import json
import os
from copy import deepcopy
import pandas as pd
from datetime import datetime
from google.cloud.firestore import Query
import matplotlib.pyplot as plt
import seaborn as sns

from firestore_utils import db
from gcs_utils import read_csv_from_gcs
# ---------------------------------------------------------------

current_user_id = st.session_state.get("user_id")

if not current_user_id:
    st.warning("Por favor, inicia sesión en la página principal para acceder.")
    st.stop()

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

# ─────────────────── FUNCIONES PARA INTERACTUAR CON FIRESTORE ───────────────────────────

def load_user_profile_from_firestore(user_id: str) -> dict:
    """Carga el perfil del usuario desde Firestore."""
    doc_ref = db.collection('usuarios').document(user_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return {}

def save_user_profile_to_firestore(user_id: str, profile_data: dict) -> None:
    """Guarda el perfil del usuario en Firestore."""
    doc_ref = db.collection('usuarios').document(user_id)
    doc_ref.set(profile_data, merge=True) # merge=True para actualizar o crear
    st.success("Perfil guardado correctamente en Firestore.")

def delete_user_profile_from_firestore(user_id: str) -> None:
    """Elimina el perfil completo del usuario y sus subcolecciones (como memorias) de Firestore."""

    # Eliminar las memorias asociadas
    memories_ref = db.collection('usuarios').document(user_id).collection('memorias')
    for doc in memories_ref.stream():
        doc.reference.delete()
    
    # Eliminar el documento del perfil
    db.collection('usuarios').document(user_id).delete()
    st.success("Tu perfil y sus memorias han sido eliminados de Firestore.")


def load_memories_from_firestore(user_id: str) -> list:
    """Carga las memorias para un usuario específico desde Firestore."""
    memories = []
    docs = db.collection('usuarios').document(user_id).collection('memorias').order_by('fecha_registro', direction=Query.DESCENDING).stream()
    for doc in docs:
        memory = doc.to_dict()
        memory['id'] = doc.id
        memories.append(memory)
    return memories

def save_memory_to_firestore(user_id: str, memory_data: dict) -> str:
    """Guarda una nueva memoria o actualiza una existente en Firestore."""
    memory_id = memory_data.get('id')
    if memory_id:
        doc_ref = db.collection('usuarios').document(user_id).collection('memorias').document(memory_id)
        data_to_save = {k: v for k, v in memory_data.items() if k != 'id'}
        doc_ref.set(data_to_save, merge=True)
        return memory_id
    else:
        doc_ref = db.collection('usuarios').document(user_id).collection('memorias').document()
        doc_ref.set(memory_data)
        return doc_ref.id

def delete_memory_from_firestore(user_id: str, memory_id: str) -> None:
    """Elimina una memoria específica de Firestore."""
    db.collection('usuarios').document(user_id).collection('memorias').document(memory_id).delete()


# ─────────────────── FUNCIÓN DE VALIDACIÓN ────────────────────
def validar_perfil_usuario(profile: dict) -> tuple[bool, str]:
    """
    Comprueba campos obligatorios y el rango de los componentes temperamentales para el perfil del usuario.
    """
    nombre = profile.get("datos_personales", {}).get("nombre", "").strip()
    if not nombre:
        return False, "El nombre es obligatorio."
    
    temps = profile.get("componentes_temperamentales", {})
    if len(temps) != 7:
        return False, "Faltan puntajes temperamentales. Deben ser 7."
    for k, v in temps.items():
        if not isinstance(v, (int, float)) or not (0 <= v <= 17):
            return False, f"El valor de '{k}' debe ser un número entre 0 y 17."
    return True, ""

# ─────────────────── INICIALIZACIÓN DE SESIÓN ─────────────────
if not st.session_state.get('password_entered', False):
    st.warning("Por favor, inicia sesión en la página principal para acceder.")
    st.stop()

if "user_profile" not in st.session_state:
    st.session_state.user_profile = load_user_profile_from_firestore(current_user_id)

if "modo_perfil" not in st.session_state:
    st.session_state.modo_perfil = "mostrar" if st.session_state.user_profile else "editar"

if "memories" not in st.session_state:
    st.session_state.memories = load_memories_from_firestore(current_user_id)

# ─────────────────── ENCABEZADO ───────────────────────────────
st.title("👤 Mi Perfil")
#st.caption("Gestiona tu información personal que el modelo podría usar, así como configuraciones.")

# ─────────────────── FORMULARIO DEL PERFIL ─────────────
def formulario_perfil_usuario(profile: dict):
    """
    Genera la interfaz de usuario para crear o modificar el perfil del usuario.
    Devuelve el diccionario del perfil con los datos ingresados.
    """
    profile_temp = deepcopy(profile)

    st.subheader("Datos de tu Perfil")

    # --- Datos Personales ---
    with st.expander("📄 Datos personales", expanded=True):
        dp = profile_temp.setdefault("datos_personales", {})
        dp["nombre"] = st.text_input(
            "Tu nombre o apodo *",
            dp.get("nombre", ""),
            help="Cómo quieres que el sistema  te conozca"
        )
        dp["sexo"]   = st.selectbox(
            "Sexo",
            ["", "Varón", "Mujer"],
            index=["", "Varón", "Mujer"].index(dp.get("sexo", ""))
        )
        dp["edad"]   = st.number_input(
            "Tu edad (años)",
            min_value=0, max_value=120, value=dp.get("edad", 0), step=1
        )
        dp["estado_civil"] = st.text_input(
            "Tu estado civil",
            dp.get("estado_civil", "")
        )
        dp["puesto_trabajo"] = st.text_input(
            "Tu puesto / profesión",
            dp.get("puesto_trabajo", "")
        )
        dp["otros_datos"] = st.text_area(
            "Otros datos sobre ti",
            dp.get("otros_datos", ""),
            help="Cualquier otro dato pertinente (ej: discapacidad, nacionalidad, cómo te comportas, etc.)."
        )

    # --- Componentes Temperamentales ---
    with st.expander("🧬 Componentes temperamentales*", expanded=False):
        st.markdown("Asigna una puntuación (entre 0 y 17) para cada componente temperamental. Estos campos son obligatorios.")
        ct = profile_temp.setdefault("componentes_temperamentales", {})
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
        caps = profile_temp.setdefault("capacidades", {})

        st.markdown("##### Habilidades técnicas")
        current_tech_skills = caps.get("Habilidades técnicas", [])
        all_tech_skills_options = sorted(list(set(TECH_SKILLS_BASE + current_tech_skills)))
        
        selected_tech_skills = st.multiselect(
            "Selecciona o añade tus habilidades técnicas",
            options=all_tech_skills_options,
            default=current_tech_skills,
            help="Selecciona habilidades de la lista o escribe nuevas y pulsa Enter. Puedes añadir varias."
        )
        new_tech_skills_input = st.text_input("Añadir otras habilidades técnicas sobre ti (separadas por coma)", "")
        if new_tech_skills_input:
            new_skills = [s.strip() for s in new_tech_skills_input.split(',') if s.strip()]
            selected_tech_skills = sorted(list(set(selected_tech_skills + new_skills)))
        caps["Habilidades técnicas"] = selected_tech_skills

        st.markdown("##### Soft skills")
        current_soft_skills = caps.get("Soft skills", [])
        all_soft_skills_options = sorted(list(set(SOFT_SKILLS_BASE + current_soft_skills)))

        selected_soft_skills = st.multiselect(
            "Selecciona o añade tus soft skills",
            options=all_soft_skills_options,
            default=current_soft_skills,
            help="Selecciona soft skills de la lista o escribe nuevas y pulsa Enter. Puedes añadir varias."
        )
        new_soft_skills_input = st.text_input("Añadir otras soft skills sobre ti (separadas por coma)", "")
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
                    help="Tu nivel de dominio del idioma"
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
    
    # ---------- Guardar y Cancelar ----------
    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button("💾 Guardar Perfil", use_container_width=True):
            ok, msg = validar_perfil_usuario(profile_temp)
            if not ok:
                st.error(msg)
            else:
                st.session_state.user_profile = profile_temp
                save_user_profile_to_firestore(current_user_id, st.session_state.user_profile)
                st.session_state.modo_perfil = "mostrar"
                st.rerun()
    with col_cancel:
        if st.button("Cancelar", type="secondary", use_container_width=True):
            st.session_state.modo_perfil = "mostrar"
            st.rerun()

# ─────────────────── SECCIÓN DE MEMORIAS ───────────────────────────
def show_memories_section():
    st.subheader("Memorias guardadas")
    
    # Add new memory
    with st.expander("➕ Añadir nueva memoria", expanded=False):
        new_memory_text = st.text_area("Escribe la nueva memoria:")
        if st.button("Guardar memoria"):
            if new_memory_text:
                memory_data = {
                    "memoria": new_memory_text,
                    "fecha_registro": datetime.now().strftime("%Y/%m/%d %H:%M")
                }
                new_memory_id = save_memory_to_firestore(current_user_id, memory_data)
                st.session_state.memories = load_memories_from_firestore(current_user_id)
                st.toast(
                    "Memoria guardada correctamente.",
                    icon="✅")
                st.rerun()
            else:
                st.warning("Por favor, escribe algo para añadir una memoria.")

    if not st.session_state.memories:
        st.info("Aún no tienes memorias guardadas.")
    else:
        for i, memory in enumerate(st.session_state.memories):
            with st.container(border=True):
                col_text, col_button = st.columns([0.9, 0.1]) # 90% para el texto, 10% para el botón

                with col_text:
                    st.write(f"{memory.get('memoria', 'N/A')}")
                    st.caption(f"{memory.get('fecha_registro', 'N/A')}")
                
                with col_button:
                    if st.button(f'🗑️', key=f"delete_memory_{memory.get('id', i)}", use_container_width=True):
                        delete_memory_from_firestore(current_user_id, memory['id'])
                        st.session_state.memories = load_memories_from_firestore(current_user_id)
                        st.toast(
                            "Memoria eliminada correctamente.",
                            icon="✅")
                        st.rerun()

# ─────────────────── FLUJO PRINCIPAL DE LA APLICACIÓN ──────────────────────────
if st.session_state.modo_perfil == "editar":
    formulario_perfil_usuario(st.session_state.user_profile)

else:
    if not st.session_state.user_profile:
        st.info("Aún no has configurado tu perfil. Haz clic en 'Editar Perfil' para comenzar.")
        if st.button("✏️ Editar Perfil"):
            st.session_state.modo_perfil = "editar"
            st.rerun()
    else:
        #st.subheader("Tu Perfil Actual")
        nombre = st.session_state.user_profile.get("datos_personales", {}).get("nombre", "Sin nombre")
        #st.markdown(f"### Información de {nombre}")

        with st.expander("📄 Datos personales", expanded=False):
            dp = st.session_state.user_profile.get("datos_personales", {})
            if dp:
                st.write(f"**Nombre:** {dp.get('nombre', 'N/A')}")
                st.write(f"**Sexo:** {dp.get('sexo', 'N/A')}")
                st.write(f"**Edad:** {dp.get('edad', 'N/A')}")
                st.write(f"**Estado civil:** {dp.get('estado_civil', 'N/A')}")
                st.write(f"**Puesto / profesión:** {dp.get('puesto_trabajo', 'N/A')}")
                st.write(f"**Otros datos:** {dp.get('otros_datos', 'N/A')}")
            else:
                st.info("No hay datos personales registrados en tu perfil.")

        with st.expander("🧬 Componentes temperamentales", expanded=False):
            ct_data = st.session_state.user_profile.get("componentes_temperamentales", {})
            if ct_data and all(comp in ct_data for comp in ["Normaloide", "Histeroide", "Mánico", "Depresivo", "Autístico", "Paranoide", "Epileptoide"]):
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
                st.info("Ingresa los 7 valores de los componentes temperamentales en modo edición para ver la gráfica.")
            else:
                st.info("No hay componentes temperamentales registrados en tu perfil.")

        with st.expander("💡 Capacidades", expanded=False):
            caps = st.session_state.user_profile.get("capacidades", {})
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

        #show_memories_section()

        col_edit, col_delete = st.columns(2)
        with col_edit:
            if st.button("✏️ Editar perfil", use_container_width=True):
                st.session_state.modo_perfil = "editar"
                st.rerun()
        with col_delete:
            if st.button("🗑️ Eliminar perfil", use_container_width=True):
                st.session_state.confirm_delete_profile = True
                st.rerun()

        show_memories_section()
        

    if st.session_state.get("confirm_delete_profile", False):
        st.warning(f"¿Estás seguro de eliminar definitivamente tu perfil, {nombre}? Esta acción no se puede deshacer.")
        col_confirm_yes, col_confirm_no = st.columns(2)
        with col_confirm_yes:
            if st.button("✅ Sí, eliminar mi perfil", key="confirm_delete_yes", use_container_width=True):
                # Eliminar el perfil de Firestore
                delete_user_profile_from_firestore(current_user_id)
                
                # Resetear el estado local
                st.session_state.user_profile = {}
                st.session_state.memories = []
                st.session_state.modo_perfil = "editar"
                st.session_state.confirm_delete_profile = False
                st.success("Tu perfil ha sido eliminado.")
                st.rerun()
        with col_confirm_no:
            if st.button("❌ No, cancelar", key="confirm_delete_no", use_container_width=True):
                st.session_state.confirm_delete_profile = False
                st.rerun()