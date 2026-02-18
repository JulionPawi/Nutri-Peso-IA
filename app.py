import streamlit as st
import pandas as pd
from openai import OpenAI
import os
from dotenv import load_dotenv
import difflib

# Importaciones locales
from calculators import calcular_mifflin_st_jeor, distribuir_macros
from prompts import SYSTEM_CLASSIFIER, SYSTEM_ESTRATEGA, SYSTEM_CONCEPTUAL
from biblioteca_dietas import DIETAS_BASE

st.set_page_config(page_title="NutriPeso IA", page_icon="🥗", layout="wide")
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@st.cache_data
def load_data():
    df_p = pd.read_csv('CANASTA_BASICA_CON_ETIQUETAS.csv')
    df_n = pd.read_csv('ProductosMexicanos.csv')
    return df_p, df_n

df_p, df_n = load_data()

# --- SIDEBAR: PERFIL DEL USUARIO ---
with st.sidebar:
    st.header("🏃 Perfil Nutricional")
    nombre = st.text_input("¿Cómo te llamas?", "Julio")
    peso = st.number_input("Peso (kg):", 40, 160, 75)
    altura = st.number_input("Altura (cm):", 120, 230, 170)
    edad = st.number_input("Edad:", 15, 90, 25)
    genero = st.radio("Género:", ["H", "M"], horizontal=True)
    objetivo = st.selectbox("Objetivo:", ["perder_peso", "ganar_musculo"])
    
    cal_meta = calcular_mifflin_st_jeor(peso, altura, edad, genero, 1.375)
    macros = distribuir_macros(cal_meta, objetivo)
    
    st.success(f"🔥 Meta: {int(cal_meta)} kcal/día")
    st.write(f"P: {int(macros['proteina'])}g | G: {int(macros['grasas'])}g | C: {int(macros['carbs'])}g")

# --- CHAT INTERFACE ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": f"¡Hola {nombre}! 👋 Soy NutriPeso IA. Te ayudaré a comer bien y ahorrar. ¿Quieres armar una dieta para {objetivo} o checar precios?"}]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input("Dime qué buscas..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    # 1. Clasificar Intención
    intent = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"system","content":SYSTEM_CLASSIFIER},{"role":"user","content":prompt}]
    ).choices[0].message.content.upper()

    # 2. Obtener Info de Dieta si aplica
    dieta_info = "Sin plan específico."
    if "DIETA" in intent or "VEGAN" in prompt.upper() or "GLUTEN" in prompt.upper():
        tipo = "vegana" if "VEGAN" in prompt.upper() else "perder_peso"
        if "MUSCULO" in prompt.upper(): tipo = "ganar_musculo"
        plan = DIETAS_BASE.get(tipo, DIETAS_BASE["perder_peso"])
        dieta_info = f"Plan: {plan['nombre']}. Tips: {plan['tips']}. Sugerencia: {plan['sugerencia']}"

    # 3. Búsqueda de Precios
    df_res = df_p[df_p['unique_id'].str.contains(prompt.upper().split()[0], case=False, na=False)]
    contexto_datos = df_res.sort_values(by='ds', ascending=False).head(8).to_string(index=False)

    # 4. Respuesta Final
    sys_prompt = SYSTEM_ESTRATEGA.format(nombre=nombre, objetivo=objetivo, calorias=int(cal_meta), macros=macros, dieta_info=dieta_info)
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "system", "content": f"DATOS CSV:\n{contexto_datos}"},
            {"role": "user", "content": prompt}
        ]
    )
    
    res_text = response.choices[0].message.content
    st.chat_message("assistant").write(res_text)
    st.session_state.messages.append({"role": "assistant", "content": res_text})
