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

# -------------------------------------------------------------
# 1. CONFIGURACIÓN GENERAL
# -------------------------------------------------------------
st.set_page_config(page_title="NutriPeso IA", page_icon="🥗", layout="wide")
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@st.cache_data
def load_data():
    df_p = pd.read_csv('CANASTA_BASICA_CON_ETIQUETAS.csv')
    df_n = pd.read_csv('ProductosMexicanos.csv')
    # Conversión vital para que la IA entienda el tiempo
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
# 3. INTERFAZ DEL CHAT
# -------------------------------------------------------------
st.title("🥗 NutriPeso IA: Tu Estratega de Ahorro y Salud")

if "messages" not in st.session_state:
    saludo = (
        f"¡Hola {nombre}! 👋 Soy NutriPeso IA. "
        f"Necesitas **{int(cal_meta)} kcal/día**. ¿Buscamos una receta o quieres saber qué productos de tu dieta subirán de precio en 2026? 🛒"
    )
    st.session_state.messages = [{"role": "assistant", "content": saludo}]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# -------------------------------------------------------------
# 4. LÓGICA PRINCIPAL DEL CHAT
# -------------------------------------------------------------
if prompt := st.chat_input("Escribe aquí…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):

        # --- A. CLASIFICACIÓN (Detección de intención) ---
        intent = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": SYSTEM_CLASSIFIER}, {"role": "user", "content": prompt}]
        ).choices[0].message.content.upper()

        # --- B. LÓGICA DE DIETAS ---
        dieta_info, plan_actual = "Sin plan específico.", {}

        if any(word in intent for word in ["DIETA", "COMER", "RECETA", "CENA", "GASTAR"]):
            api_nutri = NutriAPI()
            rango_cal = f"{int(cal_meta/4)}-{int(cal_meta/3)}"
            res_api = api_nutri.buscar_recetas(prompt, rango_cal)

            if res_api and "hits" in res_api and len(res_api["hits"]) > 0:
                receta = res_api["hits"][0]["recipe"]
                dieta_info = f"RECETA: {receta.get('label')}\nIngredientes: {', '.join(receta.get('ingredientLines', [])[:5])}"
                plan_actual["items"] = receta.get("label", "").upper().split()
            else:
                tipo = "vegana" if "VEGAN" in prompt.upper() else objetivo
                plan_actual = DIETAS_BASE.get(tipo, DIETAS_BASE["perder_peso"])
                dieta_info = f"PLAN LOCAL: {plan_actual.get('nombre')}\nSugerencia: {plan_actual.get('sugerencia')}"

        # --- C. MOTOR DE BÚSQUEDA ROBUSTO (CSV) ---
        raw_words = []
        if plan_actual.get("items"): raw_words.extend(plan_actual["items"])
        raw_words.extend(prompt.split())

        stop_words = ["QUIERO", "GUSTA", "GUSTARIA", "AGRADARIA", "PONLE", "QUITA", "BUSCA", "DIETA", "RECETA", "PARA", "ESTA", "OTRO", "TIPO"]
        keywords = [w.upper().replace(",", "").replace(".", "") for w in raw_words if len(w) > 3 and w.upper() not in stop_words]

        df_res = pd.DataFrame()
        if keywords:
            search_pattern = "|".join(keywords)
            df_res = df_p[df_p["unique_id"].str.contains(search_pattern, case=False, na=False)]

            if len(df_res["unique_id"].unique()) < 3:
                nombres_csv = df_p["unique_id"].unique().tolist()
                for k in keywords:
                    matches = difflib.get_close_matches(k, nombres_csv, n=3, cutoff=0.4)
                    df_res = pd.concat([df_res, df_p[df_p["unique_id"].isin(matches)]]).drop_duplicates()

        if not df_res.empty:
            df_res = df_res.sort_values(by=["unique_id", "ds"], ascending=[True, False])
            df_final_contexto = df_res.groupby("unique_id").head(6)

            if len(df_final_contexto["unique_id"].unique()) > 8:
                top_economicos = df_final_contexto.groupby("unique_id")["y"].mean().nsmallest(8).index
                df_final_contexto = df_final_contexto[df_final_contexto["unique_id"].isin(top_economicos)]
            
            contexto_precios = df_final_contexto.to_string(index=False)
        else:
            contexto_precios = "No hay datos para: " + ", ".join(keywords)

        # --- D. RESPUESTA FINAL CON ESTRATEGIA ---
        final_system = SYSTEM_ESTRATEGA.format(
            nombre=nombre, objetivo=objetivo, calorias=int(cal_meta), macros=macros, dieta_info=dieta_info
        )
        final_system += """
        \nREGLAS DE ORO:
        1. Si el usuario rechaza un alimento (ej: pollo), ignora los datos de pollo y busca opciones en los datos de 'CARNE' o 'RES' proporcionados.
        2. Analiza las 'Predicciones' 2026: Si el precio sube, recomienda stock (3-4 meses). Si baja, recomienda compra mínima.
        3. Siempre menciona el nombre exacto del corte de carne encontrado en los datos.
        """

        full_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": final_system},
                {"role": "system", "content": f"CONTEXTO DE PRECIOS ACTUALIZADO:\n{contexto_precios}"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4
        )

        answer = full_response.choices[0].message.content
        st.write(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
