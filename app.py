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
    # Asegúrate de que los nombres de los archivos coincidan con tu repo
    df_p = pd.read_csv('CANASTA_BASICA_CON_ETIQUETAS.csv')
    df_n = pd.read_csv('ProductosMexicanos.csv')
    # Convertir fecha a datetime para ordenar correctamente
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
        format_func=lambda x: {
            1.2: "Sedentario",
            1.375: "Ligero",
            1.55: "Moderado",
            1.725: "Intenso"
        }[x]
    )

    objetivo = st.selectbox("Objetivo:", ["perder_peso", "ganar_musculo"])

    cal_meta = calcular_mifflin_st_jeor(peso, altura, edad, genero, nivel_actividad)
    macros = distribuir_macros(cal_meta, objetivo)

    st.markdown("---")
    st.success(f"🔥 Meta diaria: {int(cal_meta)} kcal")
    st.write(f"Proteínas: {int(macros['proteina'])}g")
    st.write(f"Grasas: {int(macros['grasas'])}g")
    st.write(f"Carbohidratos: {int(macros['carbs'])}g")

# -------------------------------------------------------------
# 3. INTERFAZ DEL CHAT
# -------------------------------------------------------------
st.title("🥗 NutriPeso IA: Tu Estratega de Ahorro y Salud")

if "messages" not in st.session_state:
    saludo = (
        f"¡Hola {nombre}! 👋 Soy NutriPeso IA. "
        f"Basado en tu perfil, necesitas **{int(cal_meta)} kcal/día** para *{objetivo.replace('_',' ')}*. "
        "¿Quieres que busquemos una receta económica, un plan, o revisamos precios futuros? 🛒"
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

        # --- A. CLASIFICACIÓN (Uso de GPT-4o-mini para mayor precisión) ---
        intent = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_CLASSIFIER},
                {"role": "user", "content": prompt}
            ]
        ).choices[0].message.content.upper()

        # --- B. LÓGICA DE DIETAS ---
        dieta_info = "Sin plan específico."
        plan_actual = {}

        if any(word in intent for word in ["DIETA", "COMER", "RECETA", "CENA", "GASTAR"]):
            api_nutri = NutriAPI()
            rango_cal = f"{int(cal_meta/4)}-{int(cal_meta/3)}"
            res_api = api_nutri.buscar_recetas(prompt, rango_cal)

            if res_api and "hits" in res_api and len(res_api["hits"]) > 0:
                receta = res_api["hits"][0]["recipe"]
                dieta_info = (
                    f"RECETA API: {receta.get('label')}\n"
                    f"Calorías: {int(receta.get('calories'))}\n"
                    f"Ingredientes: {', '.join(receta.get('ingredientLines', [])[:5])}"
                )
                plan_actual["items"] = receta.get("label", "").upper().split()
            else:
                tipo = "vegana" if "VEGAN" in prompt.upper() else objetivo
                plan_actual = DIETAS_BASE.get(tipo, DIETAS_BASE["perder_peso"])
                dieta_info = (
                    f"PLAN LOCAL: {plan_actual.get('nombre')}\n"
                    f"Sugerencia: {plan_actual.get('sugerencia')}\n"
                    f"Tips: {plan_actual.get('tips')}"
                )

        # --- C. BÚSQUEDA EN CSV OPTIMIZADA (AJUSTE CLAVE) ---
        # Extraer términos significativos del plan o del prompt
        raw_terms = plan_actual.get("items") if plan_actual.get("items") else prompt.split()
        keywords = [w.upper() for w in raw_terms if len(w) > 3]
        search_pattern = "|".join(keywords)

        if search_pattern:
            df_res = df_p[df_p["unique_id"].str.contains(search_pattern, case=False, na=False)]
            
            if df_res.empty:
                nombres = df_p["unique_id"].unique().tolist()
                main_word = keywords[-1] if keywords else ""
                cercanos = difflib.get_close_matches(main_word, nombres, n=3, cutoff=0.3)
                df_res = df_p[df_p["unique_id"].isin(cercanos)]
            
            # Ordenar por fecha descendente para ver 2026 primero
            df_res = df_res.sort_values(by=["unique_id", "ds"], ascending=[True, False])
            
            # Tomar los 6 registros más recientes de CADA producto (historia + futuro)
            contexto_precios = df_res.groupby("unique_id").head(6).to_string(index=False)
        else:
            contexto_precios = "No hay datos específicos de precios para esta consulta."

        # --- D. GENERACIÓN DE RESPUESTA FINAL (CON FOCO EN PREDICCIONES) ---
        final_system = SYSTEM_ESTRATEGA.format(
            nombre=nombre,
            objetivo=objetivo,
            calorias=int(cal_meta),
            macros=macros,
            dieta_info=dieta_info
        )
        
        # Inyección de instrucción para predicciones
        final_system += "\nIMPORTANTE: Analiza las fechas y usa los datos marcados como 'Predicción' para asesorar sobre el futuro de los precios."

        if "CONCEPTUAL" in intent:
            final_system += f"\n{SYSTEM_CONCEPTUAL}"

        full_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": final_system},
                {"role": "system", "content": f"DATOS DE PRECIOS ENCONTRADOS:\n{contexto_precios}"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4 # Bajamos temperatura para más precisión en datos
        )

        answer = full_response.choices[0].message.content
        st.write(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
