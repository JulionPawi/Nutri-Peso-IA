import streamlit as st
import pandas as pd
from openai import OpenAI
import os
from dotenv import load_dotenv

# --- IMPORTACIONES DE ARCHIVOS LOCALES ---
# NOTA: Quitamos las funciones de búsqueda viejas porque ahora usamos selección directa
from calculators import calcular_mifflin_st_jeor, distribuir_macros
from prompts import SYSTEM_CLASSIFIER, SYSTEM_ESTRATEGA
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
    """Carga las bases de datos y extrae la lista de productos únicos."""
    try:
        # 1. Cargar la base limpia
        df_p = pd.read_csv('CANASTA_BASICA_CON_ETIQUETAS.csv')
        df_p['ds'] = pd.to_datetime(df_p['ds'])
        
        # 2. Cargar la otra base (si existe)
        try:
            df_n = pd.read_csv('ProductosMexicanos.csv')
        except:
            df_n = pd.DataFrame()
            
        # 3. Obtener lista de productos únicos limpios y ordenados para el Dropdown
        # Usamos la columna 'unique_id' que es la que tiene los nombres limpios
        lista_productos = sorted(df_p['unique_id'].dropna().unique().tolist())
            
        return df_p, df_n, lista_productos
    except Exception as e:
        st.error(f"Error cargando bases de datos: {e}")
        return pd.DataFrame(), pd.DataFrame(), []

df_p, df_n, lista_productos_db = load_data()

# --- FUNCIÓN DE PRECIOS EXACTOS ---
def obtener_precios_seleccionados(df, productos_seleccionados):
    """Filtra la base de datos para obtener el precio actual solo de lo que eligió el usuario."""
    if not productos_seleccionados:
        return "El usuario no seleccionó productos de la base de datos."
        
    # Usar la fecha más reciente para dar el precio actual
    fecha_reciente = df['ds'].max()
    df_actual = df[df['ds'] == fecha_reciente]
    
    # Filtrar exactamente los productos que seleccionó en la interfaz
    resultados = df_actual[df_actual['unique_id'].isin(productos_seleccionados)]
    
    texto_precios = "DATOS EXACTOS DE LA CANASTA SELECCIONADA POR EL USUARIO:\n"
    for _, row in resultados.iterrows():
        texto_precios += f"- {row['unique_id']}: ${row['y']:.2f} MXN (Unidad: {row['Unidad']})\n"
        
    return texto_precios

# -------------------------------------------------------------
# 2. SIDEBAR – Perfil Nutricional y Canasta
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

    # --- NUEVA SECCIÓN: MULTISELECT DE PRODUCTOS ---
    st.markdown("---")
    st.header("🛒 Mi Canasta")
    st.write("¿Qué ingredientes tienes en casa o quieres cotizar?")
    
    productos_elegidos = st.multiselect(
        "Busca y selecciona:", 
        options=lista_productos_db,
        placeholder="Ej. Pechuga, Arroz, Huevo..."
    )

# -------------------------------------------------------------
# 3. INTERFAZ DEL CHAT (Historial)
# -------------------------------------------------------------
st.title("🥗 NutriPeso IA: Tu Estratega de Ahorro y Salud")

if "messages" not in st.session_state:
    saludo = f"""¡Hola {nombre}! 👋 Soy **NutriPeso IA**.

Tu meta ideal es de **{int(cal_meta)} kcal/día**. 
Puedes pedirme una dieta general o **seleccionar productos en la barra lateral 👈** y pedirme que te arme una receta con el presupuesto exacto.

¿Qué cocinamos hoy? 🛒"""
    st.session_state.messages = [{"role": "assistant", "content": saludo}]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# -------------------------------------------------------------
# 4. LÓGICA UNIFICADA DEL CHAT
# -------------------------------------------------------------
if prompt := st.chat_input("Ej: Ármame una cena con lo que seleccioné...", key="chat_nutripeso"):
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analizando tus ingredientes y presupuesto..."):
            
            # --- A. CLASIFICACIÓN ---
            try:
                intent_res = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": SYSTEM_CLASSIFIER}, {"role": "user", "content": prompt}]
                )
                intent = intent_res.choices[0].message.content.upper()
            except Exception:
                intent = "DIETA" 

            # --- B. OBTENER PRECIOS EXACTOS DEL DROPDOWN ---
            contexto_precios = obtener_precios_seleccionados(df_p, productos_elegidos)
            
            # --- C. LÓGICA DE RECETAS ---
            dieta_info = "Genera un plan basado en los ingredientes seleccionados o en la petición del usuario."
            if not productos_elegidos and any(w in intent for w in ["DIETA", "COMER", "RECETA", "CENA"]):
                 try:
                    api_nutri = NutriAPI()
                    rango_cal = f"{int(cal_meta/4)}-{int(cal_meta/3)}"
                    recetas = api_nutri.buscar_recetas(prompt, rango_cal)
                    if recetas:
                        dieta_info = (
                            f"🍳 **RECETA SUGERIDA:** {recetas[0]['nombre']}\n"
                            f"🔥 **Calorías:** {recetas[0]['calorias']} kcal\n"
                            f"🛒 **Ingredientes:** {', '.join(recetas[0]['ingredientes'][:5])}"
                        )
                 except:
                     pass

            # --- D. CONSTRUIR EL PROMPT FINAL ---
            try:
                final_system = SYSTEM_ESTRATEGA.format(
                    nombre=nombre, 
                    objetivo=objetivo, 
                    calorias=int(cal_meta), 
                    macros=macros, 
                    dieta_info=dieta_info
                )
            except:
                final_system = f"Eres NutriPeso IA. Perfil: {nombre}, {int(cal_meta)} kcal, {objetivo}. Info Dieta: {dieta_info}"
            
            # Inyectamos los precios exactos si eligió algo
            if productos_elegidos:
                final_system += f"\n\nCONTEXTO DE PRECIOS EXACTOS (PRODUCTOS SELECCIONADOS POR EL USUARIO):\n{contexto_precios}"
            
            # Reglas estrictas para que no invente precios
            final_system += """\n\nREGLAS OBLIGATORIAS DE COSTOS: 
            1. Si te proporcioné una lista de "DATOS EXACTOS DE LA CANASTA", úsala OBLIGATORIAMENTE para calcular los costos del platillo.
            2. NUNCA uses marcadores vacíos como '[Precio por porción]'. Usa los precios exactos (Ej. $45 MXN) que te di.
            3. Si sugieres un ingrediente adicional que NO está en la lista de precios que te pasé, indica explícitamente '(Precio no disponible, estimar en mercado local)'."""

            try:
                full_response = client.chat.completions.create(
                    model="gpt-4o", 
                    messages=[
                        {"role": "system", "content": final_system},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.4
                )

                answer = full_response.choices[0].message.content
                st.write(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
            except Exception as e:
                error_msg = f"Hubo un error de conexión con la IA: {e}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
