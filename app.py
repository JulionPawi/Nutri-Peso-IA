import streamlit as st
import pandas as pd
from openai import OpenAI
import os
from dotenv import load_dotenv

# Configuración de la página
st.set_page_config(page_title="NutriPeso IA", page_icon="🥗")
st.title("🥗 NutriPeso IA")
st.markdown("### Tu estratega personal de salud y ahorro")

# Cargar API Key
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Cargar bases de datos
@st.cache_data # Esto hace que los CSV no se recarguen a cada rato
def load_data():
    df_precios = pd.read_csv('CANASTA_BASICA_CON_ETIQUETAS.csv')
    df_nutri = pd.read_csv('ProductosMexicanos.csv')
    return df_precios, df_nutri

df_precios, df_nutri = load_data()

# Historial de chat
if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar mensajes previos
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Entrada del usuario
if prompt := st.chat_input("¿En qué te ayudo hoy?"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Lógica de búsqueda simple (puedes mejorarla luego)
    keyword = prompt.split()[-1]
    res_p = df_precios[df_precios['unique_id'].str.contains(keyword, case=False, na=False)].head(2).to_string()
    res_n = df_nutri[df_nutri['product_name'].str.contains(keyword, case=False, na=False)].head(2).to_string()

    # Respuesta de la IA
    with st.chat_message("assistant"):
        full_prompt = f"Datos Nutrición: {res_n}\nDatos Precios: {res_p}\nPregunta: {prompt}"
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres NutriPeso IA. Ayudas a mexicanos a comer sano y barato usando los datos provistos."},
                {"role": "user", "content": full_prompt}
            ]
        )
        answer = response.choices[0].message.content
        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
