# © 2025 Pablo Díaz-Masa. Licenciado bajo CC BY-NC-ND 4.0.
# Ver LICENSE o https://creativecommons.org/licenses/by-nc-nd/4.0/

# firestore_utils.py
import firebase_admin
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from firebase_admin.firestore import ArrayUnion
import streamlit as st

# --- Función para inicializar Firestore (solo una vez) ---
@st.cache_resource
def get_firestore_client():
    """Inicializa la app de Firebase/Firestore y devuelve el cliente de Firestore.
    """
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    return firestore.client()

# --- Obtener el cliente de Firestore ---
db = get_firestore_client()

# ─────────────────── FUNCIONES DE UTILIDAD PARA FIRESTORE ────────────────────

def add_document(db_client, user_id: str, collection_name: str, data: dict):
    """Añade un nuevo documento a una colección especificada dentro de la subcolección del usuario actual."""
    user_doc_ref = db_client.collection("usuarios").document(user_id)
    return user_doc_ref.collection(collection_name).add(data)

def get_all_documents(db_client, user_id: str, collection_name: str):
    """Obtiene todos los documentos de una colección especificada dentro de la subcolección del usuario actual."""
    user_doc_ref = db_client.collection("usuarios").document(user_id)
    return user_doc_ref.collection(collection_name).stream()

def get_document(db_client, user_id: str, collection_name: str, document_id: str):
    """Obtiene un documento específico por su ID de una colección dentro de la subcolección del usuario actual."""
    user_doc_ref = db_client.collection("usuarios").document(user_id)
    doc_ref = user_doc_ref.collection(collection_name).document(document_id)
    return doc_ref.get()

def update_document(db_client, user_id: str, collection_name: str, document_id: str, data: dict):
    """Actualiza un documento específico por su ID en una colección dentro de la subcolección del usuario actual."""
    user_doc_ref = db_client.collection("usuarios").document(user_id)
    doc_ref = user_doc_ref.collection(collection_name).document(document_id)
    doc_ref.update(data)

def delete_document(db_client, user_id: str, collection_name: str, document_id: str):
    """Elimina un documento específico por su ID de una colección dentro de la subcolección del usuario actual."""
    user_doc_ref = db_client.collection("usuarios").document(user_id)
    user_doc_ref.collection(collection_name).document(document_id).delete()

def get_documents_by_field(db_client, user_id: str, collection_name: str, field_name: str, field_value):
    """Obtiene documentos de una colección donde un campo específico coincide con un valor dentro de la subcolección del usuario actual."""
    user_doc_ref = db_client.collection("usuarios").document(user_id)
    docs = user_doc_ref.collection(collection_name).where(filter=FieldFilter(field_name, "==", field_value)).stream()
    return docs

def create_new_conversation(db_client, user_id: str, initial_data: dict):
    """Creates a new conversation document and returns its ID."""
    conversations_ref = db_client.collection("usuarios").document(user_id).collection("conversaciones")
    doc_ref = conversations_ref.add(initial_data)
    return doc_ref[1].id

def save_conversation_turn(db_client, user_id: str, conversation_id: str, turn_data: dict):
    """Saves a single conversation turn to a specific conversation document."""
    doc_ref = db_client.collection("usuarios").document(user_id).collection("conversaciones").document(conversation_id)
    
    doc_ref.update({
        'turns': ArrayUnion([turn_data])
    })