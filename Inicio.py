# © 2025 Pablo Díaz-Masa. Licenciado bajo CC BY-NC-ND 4.0.
# Ver LICENSE o https://creativecommons.org/licenses/by-nc-nd/4.0/

import streamlit as st

st.set_page_config(
    page_title="Aplicación - TFM",
    page_icon="🤝",
    layout="wide"
)

# --- Lógica Básica de Autenticación (NO SEGURA)---
if not st.session_state.get('password_entered', False):
    st.markdown("## Login")

    col1, col2, col3 = st.columns([1, 1, 1])


    with col1:
        username_input = st.text_input("Usuario:")
        password_input = st.text_input("Contraseña:", type="password")

        if st.button("Acceder"):
            if password_input == 'OWN-PASSWORD':
                if username_input:
                    st.session_state.password_entered = True
                    st.session_state.user_id = username_input
                    st.rerun()
                else:
                    st.error("Por favor, introduce un nombre de usuario.")
            else:
                st.error("Contraseña incorrecta.")
        
        st.stop()

st.title("¡Bienvenido!")

st.markdown("""
    Esta aplicación está diseñada para ayudarte a mejorar tus relaciones personales y profesionales.
    Funciona como un entorno digital seguro donde puedes registrar información clave sobre las personas de tu entorno y sobre ti mismo.
    
    A través de este sistema, podrás:
    
    * **Recibir asistencia basada en modelos comportamentales:** El asistente utiliza conocimiento especializado para darte directrices sobre cómo tratar a las personas, supliendo posibles limitaciones de memoria o conocimiento.
    * **Gestionar un amplio contexto de información:** El sistema es capaz de asimilar y considerar una gran cantidad de datos sobre tus relaciones, lo que te permite tomar decisiones más informadas.
    * **Dialogar sobre gestión de relaciones:** Puedes explorar y analizar situaciones de relaciones personales que quizás no podrías discutir con otras personas, llegando a conclusiones más eficaces.
    * **Mantener un registro persistente:** Guarda información sobre tus contactos, conversaciones y experiencias pasadas, lo que te ayuda a conocerte mejor a ti mismo y a los demás a lo largo del tiempo.
    
    **Secciones de la Aplicación:**
    
    En la barra lateral izquierda encontrarás las siguientes secciones, cada una con un propósito específico:
    
    * 🗣️ **Mi Asistente:** Aquí podrás interactuar directamente con el asistente de IA. Haz preguntas sobre cómo manejar ciertas situaciones con personas, pide consejos basados en los perfiles que has creado, o simplemente explora nuevas formas de comunicarte.
    * 🤝 **Mi Gente:** En esta sección, puedes crear y gestionar los perfiles donde caracterizas a las personas con las que te relacionas. Añade sus componentes temperamentales, habilidades, idiomas y otros datos relevantes para que el asistente pueda ofrecerte un apoyo personalizado.
    * 👤 **Mi Perfil:** Aquí puedes configurar y actualizar tu propia información. Esto ayuda al asistente a entender mejor tu contexto y adaptar sus respuestas a tu temperamento y necesidades.
    
    **Consideraciones Importantes:**
    
    * Este sistema es una herramienta de apoyo, no un oráculo infalible ni un sustituto de tu esfuerzo personal.
    * El asistente está sujeto a errores y la responsabilidad final de aplicar los conocimientos recae en ti.
    * El objetivo es mejorar las relaciones, no manipular malintencionadamente a las personas.
    
    Selecciona una sección en la barra lateral para comenzar.
""")