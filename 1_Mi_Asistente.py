# © 2025 Pablo Díaz-Masa. Licenciado bajo CC BY-NC-ND 4.0.
# Ver LICENSE o https://creativecommons.org/licenses/by-nc-nd/4.0/

# 1_Mi_Asistente.py

import os
import json
import base64
import mimetypes
import pathlib
from datetime import datetime

import nest_asyncio
import streamlit as st
from google import genai
from google.genai import types

# Firestore utilities
from firestore_utils import db, get_all_documents, get_document, update_document, create_new_conversation, save_conversation_turn, delete_document
from gcs_utils import read_text_from_gcs

# ──────────────────────────────────────────────────────────────
# AJUSTES BÁSICOS Y CONTROL DE ACCESO
# ──────────────────────────────────────────────────────────────
nest_asyncio.apply()
st.set_page_config(page_title="Mi Asistente", page_icon="🗣️")

if not st.session_state.get("password_entered", False):
    st.warning("Por favor, inicia sesión en la página principal para acceder.")
    st.stop()

current_user_id = st.session_state.get("user_id")

if not current_user_id:
    st.error("No se pudo obtener el ID de usuario. Por favor, reinicia la aplicación y asegúrate de iniciar sesión.")
    st.stop()

# ──────────────────────────────────────────────────────────────
# FUNCIONES DE UTILIDAD PARA CARGAR CONOCIMIENTO
# ──────────────────────────────────────────────────────────────
def file_to_part(rel_path: str) -> types.Part:
    """Convierte un objeto de GCS a Part de GenAI (solo texto)."""
    return types.Part.from_text(text=get_file_content(rel_path))

def get_file_content(rel_path: str) -> str:
    """Lee un objeto de GCS como texto UTF-8."""
    try:
        return read_text_from_gcs(rel_path)
    except Exception as e:
        st.error(f"Error al leer {rel_path} en GCS: {e}")
        return ""

def load_user_profile_from_firestore(user_id: str) -> dict:
    """Devuelve el perfil del usuario almacenado en Firestore (puede ser {{}})."""
    doc = db.collection("usuarios").document(user_id).get()
    return doc.to_dict() if doc.exists else {}

def load_sujetos_from_firestore(user_id: str) -> list[dict]:
    """Devuelve la lista de sujetos (colección 'sujetos')."""
    docs = (
        db.collection("usuarios")
        .document(user_id)
        .collection("sujetos")
        .stream()
    )
    return [d.to_dict() for d in docs]

def load_memories_from_firestore(user_id: str) -> list[dict]:
    """Devuelve las memorias ordenadas por fecha_registro."""
    docs = (
        db.collection("usuarios")
        .document(user_id)
        .collection("memorias")
        .order_by("fecha_registro")
        .stream()
    )
    out = []
    for d in docs:
        mem = d.to_dict() or {}
        mem["id"] = d.id
        out.append(mem)
    return out

# ──────────────────────────────────────────────────────────────
# GESTIÓN DE MEMORIAS
# ──────────────────────────────────────────────────────────────
def guardar_memoria(memoria: str) -> str:
    """Inserta una nueva memoria en Firestore."""
    try:
        memory_data = {
            "memoria": memoria,
            "fecha_registro": datetime.now().strftime("%Y/%m/%d %H:%M"),
        }
        (
            db.collection("usuarios")
            .document(current_user_id)
            .collection("memorias")
            .document()
            .set(memory_data)
        )
        return f"Memoria guardada exitosamente: '{memoria}'"
    except Exception as e:
        st.error(f"Error al guardar memoria en Firestore: {e}")
        return f"Error interno al guardar la memoria: {e}"

# Declaración de la función de guardado de memorias para el LLM
guardar_memoria_function_declaration = types.FunctionDeclaration(
    name="guardar_memoria",
    description=(
        "Guarda una pieza de información proporcionada por el usuario como una memoria persistente. "
        "Deben ser piezas que el usuario pida recordar explícitamente o datos relevantes para futuras conversaciones relacionadas con tus objetivos."
        "Guarda la información en una frase gramaticalmente correcta que se refiera al usuario o a otra persona concreta."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "memoria": types.Schema(
                type=types.Type.STRING,
                description="La frase o dato clave que el LLM debe guardar como memoria.",
            )
        },
        required=["memoria"],
    ),
)

available_tools = [types.Tool(function_declarations=[guardar_memoria_function_declaration])]
function_map = {"guardar_memoria": guardar_memoria}

# ──────────────────────────────────────────────────────────────
# CONOCIMIENTO INICIAL
# ──────────────────────────────────────────────────────────────
def get_initial_knowledge_prompt() -> str:
    """Genera el prompt inicial combinando los recursos estáticos en GCS + Firestore."""
    fp = []

    # Recursos estáticos en GCS
    gcs_files = [
        ("conocimiento/instrucciones_LLM.txt", "n instrucciones de comportamiento para el LLM"),
        ("conocimiento/info_factorCT.txt", " información sobre el trato de personas según el modelo comportamental (Factor CT)"),
        ("conocimiento/tablas_componentes.json", "n las tablas de Componentes Temperamentales que indican cómo tratar a las personas para diferentes objetivos según sus componentes"),
        ("conocimiento/definicion_info_sujetos.txt", " el esquema de los datos de personas. Cada persona que ha caracterizado este usuario tiene los siguientes campos"),
    ]
    for rel_path, desc in gcs_files:
        content = get_file_content(rel_path)
        if content:
            fp.append(f"\nA continuación se presenta{desc}:\n{content}")
        else:
            st.warning(f"No se pudo leer {rel_path} en GCS")

    # Secciones de Firestore
    #  Perfil del usuario
    profile = load_user_profile_from_firestore(current_user_id)
    if profile:
        fp.append("\nA continuación se presenta información sobre el usuario que te escribe e interactúa contigo:\n" + json.dumps(profile, ensure_ascii=False, indent=2))
    else:
        st.info("No se encontró perfil del usuario en Firestore; se omite sección de usuario.")

    #  Personas caracterizadas del usuario
    sujetos = load_sujetos_from_firestore(current_user_id)
    if sujetos:
        fp.append(
            "\nA continuación se presenta información sobre las personas con las que se relaciona el usuario, rellenada por el propio usuario:\n"
            + json.dumps(sujetos, ensure_ascii=False, indent=2)
        )
    else:
        st.info("No se encontraron sujetos en Firestore; se omite sección de sujetos.")

    #  Memorias almacenadas previamente
    memories = load_memories_from_firestore(current_user_id)
    if memories:
        fp.append(
            "\nPor último, estas son las memorias que has guardado como LLM en interacciones anteriores con el usuario. Debes tenerlas en cuenta a la hora de responder:\n"
            + json.dumps(memories, ensure_ascii=False, indent=2)
        )

    print("\n\n".join(fp))
    return "\n\n".join(fp)


# ──────────────────────────────────────────────────────────────
# GESTIÓN DEL ESTADO DE LA CONVERSACIÓN
# ──────────────────────────────────────────────────────────────
# Función para inicializar/reiniciar el estado de la conversación
def initialize_conversation_state():
    # Solo inicializamos la primera vez que se carga la página
    
    if "messages" not in st.session_state:
        st.session_state.messages = []
        init_txt = get_initial_knowledge_prompt()
        if init_txt:
            st.session_state.messages.append(
                {"role": "user", "content": init_txt, "is_knowledge_prompt": True}
            )

    if "save_conversation_enabled" not in st.session_state:
        st.session_state.save_conversation_enabled = False
    if "current_conversation_id" not in st.session_state:
        st.session_state.current_conversation_id = None
    if "current_conversation_title" not in st.session_state:
        st.session_state.current_conversation_title = f"Conversación {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    if "show_save_dialog" not in st.session_state:
        st.session_state.show_save_dialog = False

# Inicializar
initialize_conversation_state()

# ──────────────────────────────────────────────────────────────
# LÓGICA SIDEBAR
# ──────────────────────────────────────────────────────────────
def enable_saving():
    """Habilita el guardado de la conversación actual."""
    if not st.session_state.save_conversation_enabled:
        st.session_state.save_conversation_enabled = True
        
        if st.session_state.current_conversation_id is None:
            initial_data = {
                "title": st.session_state.current_conversation_title,
                "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "turns": [msg for msg in st.session_state.messages if not msg.get("is_knowledge_prompt", False)]
            }
            
            st.session_state.current_conversation_id = create_new_conversation(db, current_user_id, initial_data)
            #st.success(f"Conversación marcada para guardar.")
            st.toast("✅ Conversación guardada. Los mensajes futuros se guardarán automáticamente.")
    else:
        st.info("El guardado ya está habilitado para esta conversación.")

def delete_conversation():
    """Elimina la conversación actual de Firestore y reinicia el estado."""
    if st.session_state.current_conversation_id:
        try:
            delete_document(db, current_user_id, "conversaciones", st.session_state.current_conversation_id)
            
            #st.success(f"Conversación eliminada de Firestore.")
            st.toast("🗑️ Conversación eliminada.")
        except Exception as e:
            st.error(f"Error al eliminar la conversación de Firestore: {e}")
    
    reset_conversation_state()
    st.rerun()

def load_conversation(conversation_id):
    """Carga una conversación específica de Firestore en el st.session_state.messages."""
    doc = get_document(db, current_user_id, "conversaciones", conversation_id)
    if doc.exists:
        data = doc.to_dict()
        
        reset_conversation_state() 
        
        st.session_state.messages.extend(data.get("turns", []))
        
        st.session_state.current_conversation_id = conversation_id
        st.session_state.save_conversation_enabled = True # Ya se guardan futuras interacciones
        st.session_state.current_conversation_title = data.get("title", f"Conversación {conversation_id[:6]}")
        st.info(f"Conversación '{st.session_state.current_conversation_title}' cargada desde Firestore.")
    else:
        st.error("Conversación no encontrada.")

def reset_conversation_state():
    """Reinicia el estado de la conversación para una nueva sesión, incluyendo el prompt inicial."""
    st.session_state.messages = []
    init_txt = get_initial_knowledge_prompt()
    if init_txt:
        st.session_state.messages.append(
            {"role": "user", "content": init_txt, "is_knowledge_prompt": True}
        )

    st.session_state.save_conversation_enabled = False
    st.session_state.current_conversation_id = None
    st.session_state.current_conversation_title = f"Conversación {datetime.now().strftime('%Y-%m-%d %H:%M')}"

def handle_new_conversation():
    """Gestiona el inicio de una nueva conversación, preguntando si guardar la actual si no está guardada."""
    
    # Comprobamos si hay mensajes en el chat actual (ignorando el prompt inicial si existe)
    chat_messages = [msg for msg in st.session_state.messages if not msg.get("is_knowledge_prompt", False)]
    
    # Solo mostramos el diálogo de guardar si hay mensajes Y la conversación actual no está ya guardándose
    if chat_messages and not st.session_state.save_conversation_enabled:
        st.session_state.show_save_dialog = True
        st.rerun()
    else:
        # Si el chat está vacío o ya está guardándose, simplemente iniciamos una nueva conversación
        reset_conversation_state()
        st.rerun()

def load_conversation_history_sidebar():
    """Carga y muestra el historial de conversaciones en la sidebar, incluyendo el control de guardado."""
    
    # Nuevo botón de "Nueva conversación"
    st.sidebar.button("✨ Nueva conversación", on_click=handle_new_conversation, use_container_width=True)
    st.sidebar.divider()
    
    # Sección para guardar/nombrar la conversación actual
    st.sidebar.header("Conversación Actual")
    
    # Input para el título de la conversación
    new_title = st.sidebar.text_input("Título", 
                                      value=st.session_state.current_conversation_title, 
                                      key="title_input_sidebar")

    # Lógica para actualizar el título en Firestore si el usuario lo modifica
    if new_title != st.session_state.current_conversation_title and new_title and st.session_state.save_conversation_enabled:
        # Usar la función update_document que ya existe en firestore_utils
        update_document(db, current_user_id, "conversaciones", st.session_state.current_conversation_id, {"title": new_title})
        st.session_state.current_conversation_title = new_title
        st.toast(f"Título actualizado a: {new_title}")

    # Guardar o Eliminar
    if st.session_state.save_conversation_enabled:
        # Si el guardado está habilitado, mostramos el botón de eliminar
        if st.sidebar.button("🗑️ Eliminar conversación", on_click=delete_conversation, use_container_width=True):
            pass
        st.sidebar.success("Guardado automático habilitado.")
    else:
        # Si no está guardada, mostramos el botón de guardar
        if st.sidebar.button("💾 Guardar conversación", on_click=enable_saving, use_container_width=True):
            pass
        st.sidebar.info("Esta conversación no se está guardando.")

    st.sidebar.divider()
    
    # Sección del historial de conversaciones
    st.sidebar.subheader("Historial de Conversaciones")
    
    # Obtener todas las conversaciones del usuario desde Firestore
    conversations_docs = get_all_documents(db, current_user_id, "conversaciones")
    docs_list = list(conversations_docs)
    
    if not docs_list:
        st.sidebar.info("Aún no tienes conversaciones guardadas.")
        return

    sorted_docs = []
    for doc in docs_list:
        data = doc.to_dict()
        start_time_str = data.get("start_time")
        if start_time_str:
            try:
                start_time_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                start_time_dt = datetime.min
        else:
            start_time_dt = datetime.min
        
        sorted_docs.append((start_time_dt, doc))

    # Ordenar por fecha de inicio descendente
    sorted_docs.sort(key=lambda x: x[0], reverse=True)

    # Mostrar las conversaciones en la sidebar
    for _, doc in sorted_docs:
        doc_id = doc.id
        data = doc.to_dict()
        title = data.get("title", f"Conversación {doc_id[:6]}")
        
        # Botón para cargar la conversación
        if st.sidebar.button(title, key=f"load_conv_{doc_id}", use_container_width=True):
            load_conversation(doc_id)
            st.rerun()

# ──────────────────────────────────────────────────────────────
# FUNCIÓN DE LLAMADA A GEMINI
# ──────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_gemini_client() -> genai.Client:
    return genai.Client(vertexai=True, project="tfm-pablodm", location="global")

def stream_gemini_response(chat_history: list[dict]):
    client = get_gemini_client()

    # Construir historial
    contents: list[types.Content] = []
    for msg in chat_history:
        if msg.get("is_knowledge_prompt", False) and not msg["content"]:
            continue
        role_for_api = "user" if msg["role"] == "user" else "model"
        contents.append(types.Content(role=role_for_api, parts=[types.Part.from_text(text=msg["content"]) ]))

    cfg = types.GenerateContentConfig(
        temperature=0.1,
        seed=133,
        max_output_tokens=65_535,
        tools=available_tools,
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ],
    )

    full_response_text = ""
    try:
        with st.spinner("Pensando..."):
            while True:
                response_iter = client.models.generate_content_stream(
                    model="gemini-2.5-flash",   # Antes gemini-2.5-flash-preview-05-20
                    contents=contents,
                    config=cfg,
                )

                current_turn = ""
                function_call_detected = False

                for chunk in response_iter:
                    if chunk.candidates and chunk.candidates[0].content:
                        for part in chunk.candidates[0].content.parts:
                            if part.function_call:
                                function_call_detected = True
                                fname = part.function_call.name
                                fargs = {k: v for k, v in part.function_call.args.items()}

                                if fname in function_map:
                                    result = function_map[fname](**fargs)
                                    st.toast(
                                        f"✅ Memoria: '{fargs.get('memoria', '')[:40].strip()}...'.",
                                        icon="✅",
                                    )
                                    contents.append(
                                        types.Content(role="model", parts=[part])
                                    )
                                    contents.append(
                                        types.Content(
                                            role="function",
                                            parts=[
                                                types.Part.from_function_response(
                                                    name=fname, response={"result": result}
                                                )
                                            ],
                                        )
                                    )
                                    break
                                else:
                                    st.error(
                                        f"Error: El modelo intentó llamar a una función desconocida: {fname}"
                                    )
                                    yield "Lo siento, ocurrió un error interno."
                            else:
                                current_turn += part.text
                                full_response_text += part.text
                                yield full_response_text

                if not function_call_detected:
                    # Hemos terminado este turno
                    break
    except Exception as e:
        st.error(f"Error al generar respuesta del modelo: {e}")
        yield "Lo siento, hubo un error al procesar tu solicitud."

# ──────────────────────────────────────────────────────────────
# RENDER DEL HISTORIAL Y ENTRADA DE USUARIO
# ──────────────────────────────────────────────────────────────
st.title("🗣️ Mi Asistente")

# ──────────────────────────────────────────────────────────────
# CONTROL DE FLUJO PRINCIPAL Y DIÁLOGO DE GUARDADO
# ──────────────────────────────────────────────────────────────
if st.session_state.get("show_save_dialog", False):
    st.info("¿Deseas guardar la conversación actual antes de iniciar una nueva?")
    
    col_save, col_discard = st.columns(2)
    
    with col_save:
        if st.button("✅ Sí, guardar", use_container_width=True):
            # Guardamos la conversación actual si no se había guardado ya
            if not st.session_state.save_conversation_enabled:
                enable_saving()
            
            # Iniciamos la nueva conversación
            reset_conversation_state()
            st.session_state.show_save_dialog = False
            st.rerun()
            
    with col_discard:
        if st.button("❌ No, descartar", use_container_width=True):
            # Descartamos la conversación actual e iniciamos una nueva
            reset_conversation_state()
            st.session_state.show_save_dialog = False
            st.rerun()

with st.sidebar:
    load_conversation_history_sidebar()

# ──────────────────────────────────────────────────────────────
# HISTORIAL DE CHAT
# ──────────────────────────────────────────────────────────────
if not st.session_state.get("show_save_dialog", False):
    for msg in st.session_state.messages:
        if not msg.get("is_knowledge_prompt", False):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"], unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# ENTRADA DEL USUARIO
# ──────────────────────────────────────────────────────────────
if prompt := st.chat_input("Escribe tu mensaje", disabled=st.session_state.get("show_save_dialog", False)):
    with st.chat_message("user"):
        st.markdown(prompt, unsafe_allow_html=True)

    # Guardar en historial (local)
    user_message_data = {"role": "user", "content": prompt}
    st.session_state.messages.append(user_message_data)

    # Guardar el turno del usuario en Firestore si el guardado está habilitado
    if st.session_state.save_conversation_enabled and st.session_state.current_conversation_id:
        user_turn_data = {
            "role": "user",
            "content": prompt,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        # Llama a la función de guardado de turno que usa ArrayUnion
        save_conversation_turn(db, current_user_id, st.session_state.current_conversation_id, user_turn_data)

    # Llamar al modelo y mostrar la respuesta en streaming
    with st.chat_message("assistant"):
        placeholder = st.empty()
        assistant_reply = ""
        for chunk in stream_gemini_response(st.session_state.messages):
            assistant_reply = chunk
            placeholder.markdown(assistant_reply, unsafe_allow_html=True)

    # Añadir respuesta final al historial (local)
    assistant_message_data = {"role": "assistant", "content": assistant_reply}
    st.session_state.messages.append(assistant_message_data)
    
    # Guardar el turno del asistente en Firestore si el guardado está habilitado
    if st.session_state.save_conversation_enabled and st.session_state.current_conversation_id:
        assistant_turn_data = {
            "role": "assistant",
            "content": assistant_reply,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        # Llama a la función de guardado de turno que usa ArrayUnion
        save_conversation_turn(db, current_user_id, st.session_state.current_conversation_id, assistant_turn_data)

    st.rerun()