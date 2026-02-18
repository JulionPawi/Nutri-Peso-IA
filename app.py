import streamlit as st
import pandas as pd
from openai import OpenAI
import os
from dotenv import load_dotenv
import difflib

# --- IMPORTACIONES DE TUS MÓDULOS ---
from calculators import calcular_mifflin_st_jeor, distribuir_macros
from prompts import SYSTEM_CLASSIFIER, SYSTEM_ESTRATEGA
from api_dieta import NutriAPI
from biblioteca_dietas import DIETAS_BASE

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="NutriPeso IA Pro", page_icon="🥗", layout="wide")
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@st.cache_data
def load_data():
    df_p = pd.read_csv('CANASTA_BASICA_CON_ETIQUETAS.csv')
    df_p['ds'] = pd.to_datetime(df_p['ds'])
    return df_p

df_p = load_data()

# --- SIDEBAR: CÁLCULOS REALES ---
with st.sidebar:
    st.header("🏃 Mi Perfil")
    nombre = st.text_input("Nombre:", "Julio")
    peso = st.number_input("Peso (kg):", 40.0, 160.0, 75.0)
    altura = st.number_input("Altura (cm):", 120, 230, 170)
    edad = st.number_input("Edad:", 15, 90, 25)
    genero = st.radio("Género:", ["H", "M"], horizontal=True)
    nivel_actividad = st.select_slider("Actividad:", options=[1.2, 1.375, 1.55, 1.725])
    objetivo = st.selectbox("Objetivo:", ["perder_peso", "ganar_musculo"])

    cal_meta = calcular_mifflin_st_jeor(peso, altura, edad, genero, nivel_actividad)
    macros = distribuir_macros(cal_meta, objetivo)
    st.success(f"🔥 Meta: {int(cal_meta)} kcal")

# --- MEMORIA DE SESIÓN ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": f"¡Hola {nombre}! Soy tu estratega. ¿Qué cocinamos hoy?"}]
if "ultimo_plan" not in st.session_state:
    st.session_state.ultimo_plan = None

# --- CHAT INTERFACE ---
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input("Escribe aquí…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        # 1. CLASIFICACIÓN (Detección de intención)
        intent = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": SYSTEM_CLASSIFIER}, {"role": "user", "content": prompt}]
        ).choices[0].message.content.upper()

        # 2. MOTOR DE DIETAS (API + Local)
        dieta_info = "Buscando opciones..."
        keywords_para_csv = prompt.upper().split()

        if any(word in intent for word in ["DIETA", "RECETA", "COMER"]):
            api_nutri = NutriAPI()
            # Buscamos en la API con un rango calórico por comida
            rango_cal = f"{int(cal_meta/4)}-{int(cal_meta/2)}"
            res_api = api_nutri.buscar_recetas(prompt, rango_cal)

            if res_api and res_api.get("hits"):
                receta = res_api["hits"][0]["recipe"]
                dieta_info = f"RECETA API: {receta.get('label')}. Ingredientes: {', '.join(receta.get('ingredientLines', [])[:5])}"
                # Extraemos ingredientes de la receta para buscarlos en el CSV de precios
                keywords_para_csv.extend(receta.get('label', '').upper().split())
            else:
                plan_base = DIETAS_BASE.get(objetivo, DIETAS_BASE["perder_peso"])
                dieta_info = f"PLAN LOCAL: {plan_base['nombre']}. {plan_base['sugerencia']}"
                keywords_para_csv.extend(plan_base.get("items", []))

        # 3. MOTOR HÍBRIDO DE BÚSQUEDA (CSV PRECIOS)
        # A. Expansión Forzada (Carne de Res)
        if "RES" in keywords_para_csv or "CARNE" in keywords_para_csv:
            keywords_para_csv.extend(["BISTEC", "VACUNO", "AGUJAS", "CHAMBARETE", "MOLIDA"])

        # B. Limpieza de Stopwords
        stop_words = ["QUIERO", "DAME", "ESTE", "PLAN", "TIPO", "PARA", "CON", "UNAS"]
        keywords = [w for w in keywords_para_csv if len(w) > 3 and w not in stop_words]

        # C. Filtro de Categoría y Fuzzy Search
        df_res = df_p.copy()
        # Lógica de exclusión de la versión nueva
        es_bebida = any(w in prompt.upper() for w in ["COCA", "JUGO", "BEBIDA", "AGUA"])
        
        if es_bebida:
            df_res = df_res[df_res["unique_id"].str.contains("COLA|AGUA|JUGO|BEBIDA", case=False, na=False)]
        else:
            # Si no es bebida, quitamos las bebidas del resultado para no mezclar
            df_res = df_res[~df_res["unique_id"].str.contains("COLA|JUGO", case=False, na=False)]

        # D. Búsqueda por similitud (Recuperado)
        nombres_csv = df_res["unique_id"].unique().tolist()
        matches = []
        for k in keywords:
            # Encuentra palabras similares aunque estén mal escritas
            matches.extend(difflib.get_close_matches(k, nombres_csv, n=2, cutoff=0.5))
        
        df_final_contexto = df_res[df_res["unique_id"].isin(list(set(matches)))]
        contexto_precios = df_final_contexto.sort_values(by="ds", ascending=False).head(10).to_string(index=False)

        # 4. GENERACIÓN DE RESPUESTA ESTRATÉGICA
        final_system = SYSTEM_ESTRATEGA.format(
            nombre=nombre, objetivo=objetivo, calorias=int(cal_meta), 
            macros=macros, dieta_info=dieta_info
        )
        
        # Inyectamos reglas de la versión nueva para mayor control
        final_system += f"\nREGLA: Estás en modo {('BEBIDAS' if es_bebida else 'ALIMENTOS')}. Sé breve y cita precios reales del contexto."

        full_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": final_system},
                {"role": "system", "content": f"DATOS CSV (PRECIOS/PREDICCIONES):\n{contexto_precios}"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4
        )

        answer = full_response.choices[0].message.content
        st.write(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
        st.session_state.ultimo_plan = dieta_info
