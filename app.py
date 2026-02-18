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
        f"Basado en tu perfil, necesitas **{int(cal_meta)} kcal/día**. "
        "¿Analizamos precios de la carne, armamos una receta o vemos qué comprar para estoquear? 🛒"
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

        # --- A. CLASIFICACIÓN (GPT-4o-mini) ---
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
                dieta_info = f"RECETA: {receta.get('label')}\nCalorías: {int(receta.get('calories'))}"
                plan_actual["items"] = receta.get("label", "").upper().split()
            else:
                tipo = "vegana" if "VEGAN" in prompt.upper() else objetivo
                plan_actual = DIETAS_BASE.get(tipo, DIETAS_BASE["perder_peso"])
                dieta_info = f"PLAN: {plan_actual.get('nombre')}\nSugerencia: {plan_actual.get('sugerencia')}"

        # --- C. BÚSQUEDA Y FILTRO DE RELEVANCIA (16 CORTES -> TOP 8 BARATOS) ---
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
            
            # Ordenar por fecha para ver predicciones 2026 arriba
            df_res = df_res.sort_values(by=["unique_id", "ds"], ascending=[True, False])
            
            # Agrupar y tomar 6 registros por producto
            df_final_contexto = df_res.groupby("unique_id").head(6)

            # Lógica de seguridad para múltiples cortes (ej. 16 cortes de res)
            productos_encontrados = df_final_contexto["unique_id"].unique()
            if len(productos_encontrados) > 8:
                # Seleccionamos solo los 8 con el precio promedio más bajo
                top_economicos = df_final_contexto.groupby("unique_id")["y"].mean().nsmallest(8).index
                df_final_contexto = df_final_contexto[df_final_contexto["unique_id"].isin(top_economicos)]
            
            contexto_precios = df_final_contexto.to_string(index=False)
        else:
            contexto_precios = "No se encontraron datos de precios."

        # --- D. RESPUESTA FINAL CON ESTRATEGIA DE COMPRA ---
        final_system = SYSTEM_ESTRATEGA.format(
            nombre=nombre, objetivo=objetivo, calorias=int(cal_meta), macros=macros, dieta_info=dieta_info
        )
        
        final_system += """
        \nESTRATEGIA DE SUMINISTROS:
        1. Si las 'Predicciones' muestran alza > 5%, recomienda COMPRAR STOCK (3-4 meses) de inmediato.
        2. Si el precio bajará, recomienda COMPRA MÍNIMA MENSUAL.
        3. Si hay muchos cortes parecidos, enfócate en recomendar el más económico del listado.
        """

        full_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": final_system},
                {"role": "system", "content": f"DATOS DE PRECIOS FILTRADOS (TOP 8 ECONÓMICOS):\n{contexto_precios}"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4
        )

        answer = full_response.choices[0].message.content
        st.write(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
