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
    df_p = pd.read_csv('CANASTA_BASICA_CON_ETIQUETAS.csv')
    df_n = pd.read_csv('ProductosMexicanos.csv')
    return df_p, df_n

df_p, df_n = load_data()

# 2. SIDEBAR: PERFIL NUTRICIONAL
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

    cal_meta = calcular_mifflin_st_jeor(peso, altura, edad, genero, nivel_actividad)
    macros = distribuir_macros(cal_meta, objetivo)

    st.markdown("---")
    st.success(f"🔥 Meta: {int(cal_meta)} kcal/día")
    st.write(f"P: {int(macros['proteina'])}g | G: {int(macros['grasas'])}g | C: {int(macros['carbs'])}g")

# 3. INTERFAZ DE CHAT
st.title("🥗 NutriPeso IA")

if "messages" not in st.session_state:
    saludo = f"¡Hola {nombre}! 👋 Soy NutriPeso IA. Hoy necesitamos {int(cal_meta)} kcal para {objetivo.replace('_', ' ')}. ¿Comenzamos con tu plan o buscamos precios?"
    st.session_state.messages = [{"role": "assistant", "content": saludo}]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input("Escribe aquí..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        # A. Clasificar Intención
        intent = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role":"system","content":SYSTEM_CLASSIFIER},{"role":"user","content":prompt}]
        ).choices[0].message.content.upper()

        # B. Lógica de Dietas (Híbrido API + Local)
        dieta_info = "Sin plan específico."
        plan_actual = {} # Para guardar los ingredientes si es dieta

        if "DIETA" in intent or "COMER" in prompt.upper() or "GASTAR" in prompt.upper():
            api_nutri = NutriAPI()
            rango_cal = f"{int(cal_meta/4)}-{int(cal_meta/3)}"
            res_api = api_nutri.buscar_recetas(prompt, rango_cal)
            
            if res_api and "hits" in res_api and len(res_api["hits"]) > 0:
                receta = res_api["hits"][0]["recipe"]
                dieta_info = f"API: {receta.get('label')}. Cal: {int(receta.get('calories'))}. Ingredientes: {', '.join(receta.get('ingredientLines', [])[:5])}"
                # Extraemos palabras clave para buscar en CSV
                plan_actual['items'] = receta.get('label', '').upper().split()
            else:
                tipo = "vegana" if "VEGAN" in prompt.upper() else objetivo
                plan_actual = DIETAS_BASE.get(tipo, DIETAS_BASE.get("perder_peso", {}))
                dieta_info = f"PLAN: {plan_actual.get('nombre')}. Sugerencia: {plan_actual.get('sugerencia')}. Tips: {plan_actual.get('tips')}"

        # C. BÚSQUEDA DINÁMICA EN CSV (CONECTADA)
        # Si estamos hablando de dietas, usamos los 'items' del plan. Si no, la palabra del usuario.
        items_a_buscar = plan_actual.get('items', [])
        if items_a_buscar:
            query_busqueda = "|".join(items_a_buscar)
        else:
            query_busqueda = prompt.upper().split()[0]

        df_res = df_p[df_p['unique_id'].str.contains(query_busqueda, case=False, na=False)]
        
        # Si no hay nada, intentamos con coincidencias cercanas
        if df_res.empty:
            nombres = df_p['unique_id'].unique().tolist()
            cercanos = difflib.get_close_matches(query_busqueda.split('|')[0], nombres, n=3, cutoff=0.3)
            df_res = df_p[df_p['unique_id'].isin(cercanos)]

        contexto_precios = df_res.sort_values(by='ds', ascending=False).head(15).to_string(index=False)

        # D. Generación de Respuesta Final
        final_system = SYSTEM_ESTRATEGA.format(
            nombre=nombre, 
            objetivo=objetivo, 
            calorias=int(cal_meta), 
            macros=macros, 
            dieta_info=dieta_info
        )
        
        if "CONCEPTUAL" in intent:
            final_system += f"\n{SYSTEM_CONCEPTUAL}"

        full_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": final_system},
                {"role": "system", "content": f"DATOS DE PRECIOS DEL CSV (USA ESTO PARA RESPONDER): \n{contexto_precios}"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )
        
        answer = full_response.choices[0].message.content
        st.write(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
