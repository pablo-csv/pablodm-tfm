# Más allá de la intuición — Código del TFM

Este repositorio contiene el **código fuente** del Trabajo Fin de Máster  
*“Más allá de la intuición: desarrollo y evaluación de una aplicación basada en inteligencia artificial generativa para la gestión de las relaciones interpersonales”*.

---

## 📂 Ficheros principales

- `Inicio.py` — Pantalla inicial y autenticación básica (solo para demo). **⚠️ Atención**: este sistema de login es mínimo y no seguro.  
- `1_Mi_Asistente.py` — Asistente conversacional con Gemini y gestión de memorias en Firestore.  
- `2_Mi_Gente.py` — Gestión de personas/sujetos, incluyendo datos, componentes temperamentales y capacidades (usa fichero ESCO).  
- `3_Mi_Perfil.py` — Perfil del usuario y sus memorias.  
- `firestore_utils.py` — Funciones auxiliares para conexión a Firestore.  
- `gcs_utils.py` — Funciones auxiliares para conexión a Google Cloud Storage.  
- `requirements.txt` — Dependencias del proyecto.  
- `skills_es.csv` — Lista de habilidades ESCO en español (para autocompletado).  
- `TFM_Pablo_Díaz_Masa_COMPLETO.pdf` — Memoria completa del TFM.

---

## ⚠️ Advertencia de seguridad

Este código es un **prototipo académico**. La autenticación implementada en `Inicio.py` es muy básica y **no debe usarse en producción sin modificaciones**.  
Cualquier uso real debería incorporar mecanismos adecuados de **autenticación y autorización**.

---

## 🧾 Licencia / License

Este código se distribuye bajo la misma licencia que la memoria del TFM:

- **Español:** Creative Commons **Atribución-NoComercial-SinObraDerivada 4.0 Internacional (CC BY-NC-ND 4.0)**.  
- **English:** Creative Commons **Attribution-NonCommercial-NoDerivatives 4.0 International (CC BY-NC-ND 4.0)**.

Véase <https://creativecommons.org/licenses/by-nc-nd/4.0/>.

