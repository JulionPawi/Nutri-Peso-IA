import streamlit as st
import pandas as pd
from openai import OpenAI
import os
from dotenv import load_dotenv
import difflib

# --- IMPORTACIONES DE TUS ARCHIVOS LOCALES ---
from calculators import calcular_mifflin_st_jeor, distribuir_macros
from prompts import SYSTEM_CLASSIFIER, SYSTEM_ESTRATEGA, SYSTEM_CONCEPTUAL
from biblioteca_dietas import DIETAS_BASE
from api_dieta import NutriAPI

# 1. CONFIGURACIÓN INICIAL
st.set_page_config(page_title="NutriPeso IA", page_icon="🥗", layout="wide")
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@st.cache_data
def load_data():
    # Carga de tus bases de datos CSV
    df_p = pd.read_csv('CANASTA_BASICA_CON_ETIQUETAS.csv')
    df_n = pd.read_csv('ProductosMexicanos.csv')
    return df_p, df_n

df_p, df_n = load_data()

# 2. SIDEBAR: PERFIL NUTRICIONAL (Lo que antes era main_dieta)
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
        format_func=lambda x: {1.2:"Sedentario", 1.375:"Ligero", 1.55:"Moderado", 1.725:"Intenso"}[x]
    )
    
    objetivo = st.selectbox("Objetivo:", ["perder_peso", "ganar_musculo"])

    # Cálculos científicos automáticos
    cal_meta = calcular_mifflin_st_jeor(peso, altura, edad, genero, nivel_actividad)
    macros = distribuir_macros(cal_meta, objetivo)

    st.markdown("---")
    st.success(f"🔥 Meta: {int(cal_meta)} kcal/día")
    st.write(f"📊 **Macros sugeridos:**")
    st.write(f"Proteína: {int(macros['proteina'])}g")
    st.write(f"Grasas: {int(macros['grasas'])}g")
    st.write(f"Carbs: {int(macros['carbs'])}g")

# 3. INTERFAZ DE CHAT
st.title("🥗 NutriPeso IA: Tu Estratega de Ahorro y Salud")

# Saludo inicial proactivo
if "messages" not in st.session_state:
    saludo = f"¡Hola {nombre}! 👋 Soy NutriPeso IA. Basado en tu perfil, hoy necesitamos {int(cal_meta)} kcal para {objetivo.replace('_', ' ')}. ¿Quieres que busquemos una receta económica o checamos precios del súper?"
    st.session_state.messages = [{"role": "assistant", "content": saludo}]

# Mostrar historial
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# Lógica cuando el usuario escribe
if prompt := st.chat_input("Ej: ¿Qué puedo cenar para ganar músculo?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        # A. Clasificar Intención (IA rápida)
        intent = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"system","content":SYSTEM_CLASSIFIER},{"role":"user","content":prompt}]
        ).choices[0].message.content.upper()

        # B. Lógica de Dietas y Recetas (Híbrido API + Local)
        dieta_info = "Sin plan específico seleccionado."
        
        if "DIETA" in intent or "COMER" in prompt.upper() or "RECETA" in prompt.upper():
            # 1. Intentar con tu API de Edamam (api_dieta.py)
            api_nutri = NutriAPI()
            rango_cal = f"{int(cal_meta/4)}-{int(cal_meta/3)}" # Rango por una sola comida
            res_api = api_nutri.buscar_recetas(prompt, rango_cal)
            
            if res_api and "hits" in res_api and len(res_api["hits"]) > 0:
                receta = res_api["hits"][0]["recipe"]
                dieta_info = f"RECETA DE API: {receta['label']}. Calorías: {int(receta['calories'])}. Ingredientes: {', '.join(receta['ingredientLines'][:5])}. Link: {receta['url']}"
            else:
                # 2. Si falla la API, usar tu biblioteca local (biblioteca_dietas.py)
                tipo = "vegana" if "VEGAN" in prompt.upper() else objetivo
                plan = DIETAS_BASE.get(tipo, DIETAS_BASE["perder_peso"])
                dieta_info = f"PLAN LOCAL: {plan['nombre']}. Sugerencia: {plan['sugerencia']}. Tips: {plan['tips']}"

        # C. Búsqueda de Precios en CSV
        # Buscamos la primera palabra del prompt para mayor coincidencia
        termino_busqueda = prompt.upper().split()[0]
        df_res = df_p[df_p['unique_id'].str.contains(termino_busqueda, case=False, na=False)]
        
        # Si no hay exactos, buscar parecidos
        if df_res.empty:
            nombres = df_p['unique_id'].unique().tolist()
            cercanos = difflib.get_close_matches(termino_busqueda, nombres, n=3, cutoff=0.3)
            df_res = df_p[df_p['unique_id'].isin(cercanos)]

        contexto_precios = df_res.sort_values(by='ds', ascending=False).head(8).to_string(index=False)

        # D. Generación de Respuesta Final (IA Inteligente GPT-4o)
        # Inyectamos todos los cálculos y datos en el prompt
        final_system = SYSTEM_ESTRATEGA.format(
            nombre=nombre, 
            objetivo=objetivo, 
            calorias=int(cal_meta), 
            macros=macros, 
            dieta_info=dieta_info
        )
        
        # Si es una búsqueda conceptual (vaga), cambiamos al prompt conceptual
        if "CONCEPTUAL" in intent:
            final_system = f"{final_system}\n{SYSTEM_CONCEPTUAL}"

        full_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": final_system},
                {"role": "system", "content": f"DATOS DE PRECIOS ACTUALES:\n{contexto_precios}"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )
        
        answer = full_response.choices[0].message.content
        st.write(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
