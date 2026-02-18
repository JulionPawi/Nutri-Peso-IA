import streamlit as st
import pandas as pd
from openai import OpenAI
import os
from dotenv import load_dotenv
import difflib

# --- IMPORTACIONES DE ARCHIVOS LOCALES ---
from calculators import calcular_mifflin_st_jeor, distribuir_macros
from prompts import SYSTEM_CLASSIFIER, SYSTEM_ESTRATEGA, SYSTEM_CONCEPTUAL
from biblioteca_dietas import DIETAS_BASE
from api_dieta import NutriAPI

# 1. CONFIGURACIÓN GENERAL
st.set_page_config(page_title="NutriPeso IA", page_icon="🥗", layout="wide")
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@st.cache_data
def load_data():
    df_p = pd.read_csv('CANASTA_BASICA_CON_ETIQUETAS.csv')
    df_n = pd.read_csv('ProductosMexicanos.csv')
    return df_p, df_n

df_p, df_n = load_data()

# 2. SIDEBAR – Perfil nutricional
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
    st.write(f"Proteínas: {int(macros['proteina'])}g")
    st.write(f"Grasas: {int(macros['grasas'])}g")
    st.write(f"Carbohidratos: {int(macros['carbs'])}g")

# 3. INTERFAZ DEL CHAT
st.title("🥗 NutriPeso IA: Tu Estratega de Ahorro y Salud")

if "messages" not in st.session_state:
    saludo = (
        f"¡Hola {nombre}! 👋 Soy NutriPeso IA. "
        f"Basado en tu perfil, necesitas **{int(cal_meta)} kcal/día** para *{objetivo.replace('_',' ')}*. "
        "¿Quieres que busquemos una receta económica, que armemos un plan, o revisamos precios del súper? 🛒"
    )
    st.session_state.messages = [{"role": "assistant", "content": saludo}]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# 4. LÓGICA PRINCIPAL DEL CHAT
if prompt := st.chat_input("Escribe aquí…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        # --- A. CLASIFICACIÓN ---
        intent_res = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": SYSTEM_CLASSIFIER}, {"role": "user", "content": prompt}]
        )
        intent = intent_res.choices[0].message.content.upper()

        # --- B. LÓGICA DE DIETAS (PROTEGIDA) ---
        dieta_info = "Sin plan específico."
        plan_actual = {"items": []} # Inicialización base para evitar KeyError

        # Palabras clave que activan la búsqueda de comida
        if any(word in intent for word in ["DIETA", "COMER", "RECETA", "CENA", "GASTAR"]) or any(word in prompt.upper() for word in ["DIETA", "RECETA", "COMER"]):
            api_nutri = NutriAPI()
            rango_cal = f"{int(cal_meta/4)}-{int(cal_meta/3)}"
            res_api = api_nutri.buscar_recetas(prompt, rango_cal)

            if res_api and "hits" in res_api and len(res_api["hits"]) > 0:
                receta = res_api["hits"][0]["recipe"]
                dieta_info = f"RECETA API: {receta.get('label')}\nCalorías: {int(receta.get('calories'))}\nIngredientes: {', '.join(receta.get('ingredientLines', [])[:5])}"
                plan_actual["items"] = receta.get("label", "").upper().split()
            else:
                tipo = "vegana" if "VEGAN" in prompt.upper() else objetivo
                plan_actual = DIETAS_BASE.get(tipo, DIETAS_BASE["perder_peso"])
                dieta_info = f"PLAN LOCAL: {plan_actual.get('nombre')}\nSugerencia: {plan_actual.get('sugerencia')}\nTips: {plan_actual.get('tips')}"

        # --- C. BÚSQUEDA EN CSV ---
        # Si plan_actual tiene items, los usamos; si no, usamos la palabra del prompt
        items_lista = plan_actual.get("items", [])
        if items_lista:
            search_terms = "|".join(items_lista)
        else:
            search_terms = prompt.upper().split()[0]

        df_res = df_p[df_p["unique_id"].str.contains(search_terms, case=False, na=False)]

        # Búsqueda de respaldo si no hay coincidencias directas
        if df_res.empty:
            nombres = df_p["unique_id"].unique().tolist()
            termino_para_difflib = search_terms.split("|")[0]
            cercanos = difflib.get_close_matches(termino_para_difflib, nombres, n=4, cutoff=0.25)
            df_res = df_p[df_p["unique_id"].isin(cercanos)]

        contexto_precios = df_res.sort_values("ds", ascending=False).head(15).to_string(index=False)

        # --- D. RESPUESTA FINAL ---
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
                {"role": "system", "content": f"DATOS DE PRECIOS:\n{contexto_precios}"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.55
        )

        answer = full_response.choices[0].message.content
        st.write(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
