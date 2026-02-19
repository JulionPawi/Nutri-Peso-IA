import streamlit as st
import pandas as pd
from openai import OpenAI
import os
from dotenv import load_dotenv
import difflib

# --- IMPORTACIONES DE ARCHIVOS LOCALES ---
from calculators import calcular_mifflin_st_jeor, distribuir_macros, buscador_nutripeso, limpiar_nombre_producto
from prompts import SYSTEM_CLASSIFIER, SYSTEM_ESTRATEGA, SYSTEM_CONCEPTUAL
from biblioteca_dietas import DIETAS_BASE
from api_dieta import NutriAPI

# -------------------------------------------------------------
# 1. CONFIGURACIÓN GENERAL
# -------------------------------------------------------------
st.set_page_config(page_title="NutriPeso IA", page_icon="🥗", layout="wide")
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@st.cache_data
def load_data():
    # Asegúrate de que el nombre del archivo coincida exactamente con tu carpeta
    df_p = pd.read_csv('CANASTA_BASICA_CON_ETIQUETAS.csv')
    df_n = pd.read_csv('ProductosMexicanos.csv')
    df_p['ds'] = pd.to_datetime(df_p['ds'])
    return df_p, df_n

df_p, df_n = load_data()

# -------------------------------------------------------------
# 2. SIDEBAR – Perfil nutricional
# -------------------------------------------------------------
with st.sidebar:
    st.header("🏃 Mi Perfil Físico")
    nombre = st.text_input("¿Cómo te llamas?", "Julio")

    col_p, col_a = st.columns(2)
    with col_p:
        peso = st.number_input("Peso (kg):", 40.0, 160.0, 75.0)
    with col_a:
        altura = st.number_input("Altura (cm):", 120, 230, 170)

    edad = st.number_input("Edad:", 15, 90, 25)
    genero = st.radio("Género:", ["H", "M"], horizontal=True)

    nivel_actividad = st.select_slider(
        "Actividad física:",
        options=[1.2, 1.375, 1.55, 1.725],
        format_func=lambda x: {1.2: "Sedentario", 1.375: "Ligero", 1.55: "Moderado", 1.725: "Intenso"}[x]
    )

    objetivo = st.selectbox("Objetivo:", ["perder_peso", "ganar_musculo"])

    cal_meta = calcular_mifflin_st_jeor(peso, altura, edad, genero, nivel_actividad)
    macros = distribuir_macros(cal_meta, objetivo)

    st.markdown("---")
    st.success(f"🔥 Meta diaria: {int(cal_meta)} kcal")
    st.write(f"Prot: {int(macros['proteina'])}g | Grasas: {int(macros['grasas'])}g | Carbs: {int(macros['carbs'])}g")

# -------------------------------------------------------------
# 3. INTERFAZ DEL CHAT (Historial)
# -------------------------------------------------------------
st.title("🥗 NutriPeso IA: Tu Estratega de Ahorro y Salud")

if "messages" not in st.session_state:
    saludo = f"""¡Hola {nombre}! 👋 Soy **NutriPeso IA**.

Basado en tu perfil, tu meta ideal es de **{int(cal_meta)} kcal/día**. Mi misión es que comas bien sin que tu cartera sufra. 🥗💰

📉 **¿Por dónde empezamos hoy?**

1. Puedo diseñarte una **receta optimizada** con los precios de hoy en CDMX.
2. O puedo darte el **pronóstico de precios 2026** para que te anticipes a las alzas en el súper.

¿Qué prefieres? 🛒"""
    st.session_state.messages = [{"role": "assistant", "content": saludo}]

# Mostrar mensajes previos
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# -------------------------------------------------------------
# 4. LÓGICA UNIFICADA DEL CHAT
# -------------------------------------------------------------
# USAR SOLO UN chat_input PARA EVITAR EL ERROR DuplicateElementId
if prompt := st.chat_input("Escribe aquí…", key="chat_nutripeso"):
    
    # Mostrar mensaje del usuario inmediatamente
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        # --- A. CLASIFICACIÓN ---
        intent_res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": SYSTEM_CLASSIFIER}, {"role": "user", "content": prompt}]
        )
        intent = intent_res.choices[0].message.content.upper()

        # --- B. INICIALIZACIÓN DE VARIABLES PARA EL PROMPT ---
        dieta_info = "No se generó un plan específico en este turno."
        plan_actual = {}
        contexto_precios = "No hay datos de precios específicos para esta consulta."
        
        # Extraemos palabras clave básicas del prompt
        stop_words = {"QUIERO", "GUSTA", "BUSCA", "DIETA", "PRECIO", "CUANTO", "ESTA", "PARA", "CON", "LAS", "LOS"}
        keywords = [w.upper().strip(",.") for w in prompt.split() if w.upper() not in stop_words and len(w) > 3]

        # --- C. LÓGICA DE DIETAS (Si se detecta intención de comer/receta) ---
        if any(word in intent for word in ["DIETA", "COMER", "RECETA", "CENA", "CONCEPTUAL"]):
            api_nutri = NutriAPI()
            rango_cal = f"{int(cal_meta/4)}-{int(cal_meta/3)}"
            recetas_encontradas = api_nutri.buscar_recetas(prompt, rango_cal)

            if recetas_encontradas:
                receta = recetas_encontradas[0]
                dieta_info = (
                    f"🍳 **RECETA:** {receta['nombre']}\n"
                    f"🔥 **Calorías:** {receta['calorias']} kcal\n"
                    f"🛒 **Ingredientes:** {', '.join(receta['ingredientes'][:5])}"
                )
                plan_actual = {"nombre": receta['nombre'], "items": receta['ingredientes']}
                # Enriquecemos keywords con los ingredientes de la receta
                keywords.extend([str(i).split()[-1].upper() for i in receta['ingredientes'][:3]])
            else:
                tipo = "vegana" if "VEGAN" in prompt.upper() else objetivo
                plan_local = DIETAS_BASE.get(tipo, DIETAS_BASE.get("perder_peso"))
                dieta_info = f"🏠 **PLAN LOCAL:** {plan_local.get('nombre')}\n💡 {plan_local.get('sugerencia')}"
                plan_actual = plan_local

        # --- D. MOTOR DE BÚSQUEDA DE PRECIOS ---
        if keywords or "PRECIOS" in intent:
            df_resultados = buscador_inteligente_ia(prompt, df_p, client)
            
            if not df_resultados.empty:
                df_resultados['nombre_amigable'] = df_resultados['unique_id'].apply(limpiar_nombre_producto)
                contexto_precios = "DATOS DE LA CANASTA BÁSICA (CDMX):\n"
                for _, row in df_resultados.iterrows():
                    # Formateamos fecha y precio
                    fecha_str = row['ds'].strftime('%Y-%m-%d')
                    contexto_precios += f"- {row['nombre_amigable']}: ${row['y']} MXN (Fecha: {fecha_str})\n"
            else:
                contexto_precios = "No hay coincidencias exactas, sugiere alternativas económicas basadas en la canasta básica general."

        # --- E. RESPUESTA FINAL CON GPT-4O ---
        # Construimos el sistema con toda la información recolectada
        final_system = SYSTEM_ESTRATEGA.format(
            nombre=nombre, 
            objetivo=objetivo, 
            calorias=int(cal_meta), 
            macros=macros, 
            dieta_info=dieta_info
        )
        
        # Añadimos las reglas y el contexto de precios al sistema
        final_system += f"\n\nCONTEXTO DE PRECIOS ACTUALES:\n{contexto_precios}"
        final_system += "\n\nREGLA: Analiza los precios y ofrece una estrategia de ahorro clara para el usuario."

        full_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": final_system},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4
        )

        answer = full_response.choices[0].message.content
        st.write(answer)
        
        # Guardar en el historial para la próxima vuelta
        st.session_state.messages.append({"role": "assistant", "content": answer})
