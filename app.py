import streamlit as st
import pandas as pd
from openai import OpenAI
import os
from dotenv import load_dotenv

# --- IMPORTACIONES DE ARCHIVOS LOCALES ---
from calculators import calcular_mifflin_st_jeor, distribuir_macros, limpiar_nombre_producto
from prompts import SYSTEM_CLASSIFIER, SYSTEM_ESTRATEGA
from biblioteca_dietas import DIETAS_BASE
from api_dieta import NutriAPI

# NOTA: Quité 'buscador_inteligente_ia' porque ahora usamos la función optimizada local
# para no gastar tokens ni tiempo en búsquedas complejas ineficientes.

# -------------------------------------------------------------
# 1. CONFIGURACIÓN GENERAL
# -------------------------------------------------------------
st.set_page_config(page_title="NutriPeso IA", page_icon="🥗", layout="wide")
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@st.cache_data
def load_data():
    # Cargar la base de datos limpia (Asegúrate de que este CSV sea el que ya procesamos con nombres limpios)
    try:
        df_p = pd.read_csv('CANASTA_BASICA_CON_ETIQUETAS.csv')
        df_p['ds'] = pd.to_datetime(df_p['ds'])
        
        # ProductosMexicanos (Si lo usas para algo más, se carga, si no, lo ignoramos)
        try:
            df_n = pd.read_csv('ProductosMexicanos.csv')
        except:
            df_n = pd.DataFrame()
            
        return df_p, df_n
    except Exception as e:
        st.error(f"Error cargando bases de datos: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_p, df_n = load_data()

# --- NUEVO MOTOR DE BÚSQUEDA DE PRECIOS OPTIMIZADO ---
def buscar_precios_reales(df, prompt_usuario, ingredientes_receta=None):
    """Busca precios en la base de datos basándose en el prompt o los ingredientes."""
    if df.empty:
        return "Base de datos de precios no disponible."
        
    # Usar la fecha más reciente para dar precios actuales (del mes)
    fecha_reciente = df['ds'].max()
    df_actual = df[df['ds'] == fecha_reciente]
    
    # 1. Definir qué vamos a buscar
    texto_busqueda = prompt_usuario.lower()
    if ingredientes_receta:
        # Añadir los ingredientes que encontró la API de recetas a la búsqueda
        texto_busqueda += " " + " ".join(ingredientes_receta).lower()

    # 2. Diccionario de mapeo inteligente a tu CSV
    busquedas = {
        "Pollo": ["pollo", "pechuga"],
        "Carne de Res": ["res", "bistec", "filete de res", "molida", "retazo"],
        "Pescado": ["tilapia", "mojarra", "pescado", "atún", "atun", "salmón", "salmon"],
        "Cerdo": ["cerdo", "chuleta", "lomo", "carnitas"],
        "Arroz": ["arroz"],
        "Avena": ["avena"],
        "Frijoles": ["frijol", "frijoles"],
        "Lentejas": ["lenteja", "lentejas"],
        "Huevos": ["huevo", "huevos"],
        "Leche": ["leche"],
        "Yogur": ["yogur", "yogurt", "griego"],
        "Queso": ["queso", "panela", "oaxaca", "manchego"],
        "Manzana": ["manzana"],
        "Plátano": ["platano", "plátano"],
        "Tomate/Jitomate": ["tomate", "jitomate"],
        "Cebolla": ["cebolla"],
        "Brócoli": ["brocoli", "brócoli"],
        "Zanahoria": ["zanahoria"],
        "Aguacate": ["aguacate"],
        "Aceite": ["aceite"]
    }

    texto_precios = "DATOS EXTRAÍDOS DE LA CANASTA BÁSICA (PRECIOS REALES MXN):\n"
    encontrados = 0

    # 3. Buscar en la base de datos
    for categoria, keywords in busquedas.items():
        # Si la categoría fue mencionada por el usuario o está en la receta
        if any(kw in texto_busqueda for kw in keywords):
            
            # Buscar en el DataFrame
            patron = '|'.join(keywords)
            mask = df_actual['unique_id'].str.contains(patron, case=False, na=False)
            
            # Filtro especial para pollo: Evitar traer precios de nuggets o pollo cordon blue procesado
            if categoria == "Pollo":
                mask &= ~df_actual['unique_id'].str.contains("Cordon|Nugget", case=False, na=False)
                
            resultados = df_actual[mask]
            
            if not resultados.empty:
                precio_promedio = resultados['y'].mean()
                # Tomar el nombre de un producto real (para que la IA no invente marcas)
                ejemplo_real = resultados['unique_id'].iloc[0] 
                
                texto_precios += f"- {categoria}: Aprox ${precio_promedio:.2f} MXN (Te sugerimos: {ejemplo_real})\n"
                encontrados += 1

    if encontrados == 0:
        return "No se encontraron precios exactos en la base de datos para los ingredientes mencionados. Sugiere alternativas económicas o estima costos de mercado general de México."
        
    return texto_precios

# -------------------------------------------------------------
# 2. SIDEBAR – Perfil nutricional
# -------------------------------------------------------------
with st.sidebar:
    st.header("🏃 Mi Perfil Físico")
    nombre = st.text_input("¿Cómo te llamas?", "")

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
# 3. INTERFAZ DEL CHAT (Historial)
# -------------------------------------------------------------
st.title("🥗 NutriPeso IA: Tu Estratega de Ahorro y Salud")

if "messages" not in st.session_state:
    saludo = f"""¡Hola {nombre}! 👋 Soy **NutriPeso IA**.

Basado en tu perfil, tu meta ideal es de **{int(cal_meta)} kcal/día**. Mi misión es que comas bien sin que tu cartera sufra. 🥗💰

📉 **¿Por dónde empezamos hoy?**

1. Puedo diseñarte una **receta optimizada** con los precios de hoy en CDMX.
2. O puedo darte el **pronóstico de precios 2026** para que te anticipes a las alzas en el súper.

¿Qué prefieres? 🛒"""
    st.session_state.messages = [{"role": "assistant", "content": saludo}]

# Mostrar mensajes previos
for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# -------------------------------------------------------------
# 4. LÓGICA UNIFICADA DEL CHAT
# -------------------------------------------------------------
if prompt := st.chat_input("Escribe aquí…", key="chat_nutripeso"):
    
    # Mostrar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analizando mercado y armando tu plan..."):
            
            # --- A. CLASIFICACIÓN ---
            try:
                intent_res = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": SYSTEM_CLASSIFIER}, {"role": "user", "content": prompt}]
                )
                intent = intent_res.choices[0].message.content.upper()
            except Exception as e:
                intent = "DIETA" # Fallback si falla
            
            # --- B. INICIALIZACIÓN DE VARIABLES ---
            dieta_info = "No se generó un plan específico en este turno."
            ingredientes_receta = []
            
            # --- C. LÓGICA DE DIETAS / RECETAS ---
            if any(word in intent for word in ["DIETA", "COMER", "RECETA", "CENA", "CONCEPTUAL", "PRECIO"]):
                try:
                    # Usar tu API externa
                    api_nutri = NutriAPI()
                    rango_cal = f"{int(cal_meta/4)}-{int(cal_meta/3)}"
                    recetas_encontradas = api_nutri.buscar_recetas(prompt, rango_cal)

                    if recetas_encontradas:
                        receta = recetas_encontradas[0]
                        dieta_info = (
                            f"🍳 **RECETA SUGERIDA:** {receta['nombre']}\n"
                            f"🔥 **Calorías:** {receta['calorias']} kcal\n"
                            f"🛒 **Ingredientes Principales:** {', '.join(receta['ingredientes'][:5])}"
                        )
                        ingredientes_receta = receta['ingredientes']
                    else:
                        # Fallback a dietas locales
                        tipo = "vegana" if "VEGAN" in prompt.upper() else objetivo
                        plan_local = DIETAS_BASE.get(tipo, DIETAS_BASE.get("perder_peso"))
                        dieta_info = f"🏠 **PLAN LOCAL:** {plan_local.get('nombre')}\n💡 {plan_local.get('sugerencia')}"
                except Exception as e:
                    dieta_info = "Utiliza tu conocimiento nutricional general para proponer una dieta balanceada."

            # --- D. MOTOR DE BÚSQUEDA DE PRECIOS OPTIMIZADO ---
            # Pasamos tanto lo que dijo el usuario, como los ingredientes de la receta (si se encontró una)
            contexto_precios = buscar_precios_reales(df_p, prompt, ingredientes_receta)

            # --- E. RESPUESTA FINAL CON GPT-4o ---
            # Construimos el sistema
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
            
            # --- LA CLAVE PARA QUE NO INVENTE PRECIOS ---
            final_system += f"\n\nCONTEXTO DE PRECIOS ACTUALES EXTRAÍDOS DE LA BASE DE DATOS:\n{contexto_precios}"
            final_system += """\n\nREGLAS OBLIGATORIAS: 
            1. Para la estrategia de compras, USA ÚNICAMENTE los precios proporcionados arriba.
            2. NUNCA uses marcadores vacíos como '[Precio por porción]'. Usa los precios exactos (Ej. $45 MXN).
            3. Si un ingrediente está en la lista de precios, incluye la marca/tipo exacto entre paréntesis (Ej: 'Yogur: $196 MXN (Fage Griego Natural)')."""

            try:
                # OJO: Cambié a gpt-4o, puedes usar gpt-4o-mini si quieres que sea más barato
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
                
                # Guardar en el historial
                st.session_state.messages.append({"role": "assistant", "content": answer})
                
            except Exception as e:
                error_msg = f"Hubo un error al generar la respuesta: {e}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
