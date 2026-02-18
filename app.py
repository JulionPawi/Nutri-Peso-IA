import streamlit as st
import pandas as pd
from openai import OpenAI
import os
from dotenv import load_dotenv
import difflib
# Importamos nuestros prompts del archivo independiente
from prompts import SYSTEM_CLASSIFIER, SYSTEM_ESTRATEGA, SYSTEM_CONCEPTUAL

# 1. CONFIGURACIÓN
st.set_page_config(page_title="NutriPeso IA Pro", page_icon="🥗", layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@st.cache_data
def load_data():
    df_p = pd.read_csv('CANASTA_BASICA_CON_ETIQUETAS.csv')
    df_n = pd.read_csv('ProductosMexicanos.csv')
    return df_p, df_n

df_p, df_n = load_data()

# 2. INTERFAZ SIDEBAR
with st.sidebar:
    st.title("⚙️ Panel de Control")
    nombre = st.text_input("Tu nombre:", "Julio")
    st.markdown("---")
    if st.button("Limpiar Conversación"):
        st.session_state.messages = []
        st.rerun()

# 3. CHAT PRINCIPAL
st.title("🥗 NutriPeso IA")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("¿En qué puedo ayudarte?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # PASO A: Clasificar Intención
        intent = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": SYSTEM_CLASSIFIER}, {"role": "user", "content": prompt}]
        ).choices[0].message.content.upper()

        contexto_datos = ""
        final_system_prompt = SYSTEM_ESTRATEGA

        # PASO B: Lógica de Búsqueda Segun Intención
        if "PRECIOS" in intent or "CONCEPTUAL" in intent:
            # Relacionar conceptos (Ej: 'algo dulce' -> 'Jugo')
            if "CONCEPTUAL" in intent:
                traduccion = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "system", "content": "Traduce el deseo a 2 términos de inventario (Ej: 'antojo' -> 'GALLETAS, CHOCOLATE'). Solo palabras."}, {"role": "user", "content": prompt}]
                ).choices[0].message.content
                termino_busqueda = traduccion.upper()
                final_system_prompt = SYSTEM_CONCEPTUAL
            else:
                termino_busqueda = prompt.upper()

            # Búsqueda en CSV
            df_encontrado = df_p[df_p['unique_id'].str.contains(termino_busqueda.replace(",", "|"), case=False, na=False)]
            
            if df_encontrado.empty:
                nombres = df_p['unique_id'].unique().tolist()
                cercanos = difflib.get_close_matches(termino_busqueda, nombres, n=3, cutoff=0.3)
                if cercanos:
                    df_encontrado = df_p[df_p['unique_id'].isin(cercanos)]

            contexto_datos = df_encontrado.sort_values(by='ds', ascending=False).head(10).to_string(index=False)

        # PASO C: Respuesta Final
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"{final_system_prompt}\nDATOS:\n{contexto_datos}"},
                {"role": "user", "content": f"Usuario: {nombre}. Mensaje: {prompt}"}
            ],
            temperature=0.4
        )
        
        answer = response.choices[0].message.content
        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
