import streamlit as st
import pandas as pd
from openai import OpenAI
import os
from dotenv import load_dotenv
from datetime import datetime

# --- IMPORTACIONES DE ARCHIVOS LOCALES ---
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
        df_p = pd.read_csv('CANASTA_BASICA_CON_ETIQUETAS.csv')
        df_p['ds'] = pd.to_datetime(df_p['ds'])
        
        try:
            df_n = pd.read_csv('ProductosMexicanos.csv')
        except:
            df_n = pd.DataFrame()
            
        lista_productos = sorted(df_p['unique_id'].dropna().unique().tolist())
            
        return df_p, df_n, lista_productos
    except Exception as e:
        st.error(f"Error cargando bases de datos: {e}")
        return pd.DataFrame(), pd.DataFrame(), []

df_p, df_n, lista_productos_db = load_data()

# --- FUNCIÓN DE PRECIOS EXACTOS Y PRONÓSTICO ---
def obtener_precios_seleccionados(df, productos_seleccionados):
    """Obtiene el precio actual, el pronóstico futuro y da recomendaciones de compra."""
    if not productos_seleccionados:
        return "El usuario no seleccionó productos de la base de datos."
        
    # 1. Definir "Hoy" (el mes actual) y "Futuro" (la fecha máxima en la base de datos)
    hoy = pd.to_datetime(datetime.today().replace(day=1).strftime('%Y-%m-01'))
    
    fechas_disponibles = df['ds'].unique()
    if hoy not in fechas_disponibles:
        fechas_pasadas = [f for f in fechas_disponibles if f <= hoy]
        fecha_actual = max(fechas_pasadas) if fechas_pasadas else df['ds'].min()
    else:
        fecha_actual = hoy
        
    fecha_futura = df['ds'].max()
    meses_diferencia = (pd.to_datetime(fecha_futura).year - pd.to_datetime(fecha_actual).year) * 12 + (pd.to_datetime(fecha_futura).month - pd.to_datetime(fecha_actual).month)
    
    if meses_diferencia <= 0:
        meses_diferencia = 1
        
    # 2. Extraer y comparar datos
    df_seleccion = df[df['unique_id'].isin(productos_seleccionados)]
    df_hoy = df_seleccion[df_seleccion['ds'] == fecha_actual]
    df_futuro = df_seleccion[df_seleccion['ds'] == fecha_futura]
    
    texto_precios = f"DATOS DE LA CANASTA Y PRONÓSTICO A {meses_diferencia} MESES (ÚSALO PARA TU ESTRATEGIA):\n"
    
    for p in productos_seleccionados:
        try:
            precio_hoy = df_hoy[df_hoy['unique_id'] == p]['y'].values[0]
            precio_fut = df_futuro[df_futuro['unique_id'] == p]['y'].values[0]
            unidad = df_hoy[df_hoy['unique_id'] == p]['Unidad'].values[0]
            
            # Calcular la variación porcentual
            cambio_pct = ((precio_fut - precio_hoy) / precio_hoy) * 100
            
            # Generar la recomendación matemática
            if cambio_pct > 2.5:
                recomendacion = "📈 TENDENCIA AL ALZA -> Sugerir compra al por mayor ahora y congelar/almacenar."
            elif cambio_pct < -2.5:
                recomendacion = "📉 TENDENCIA A LA BAJA -> Sugerir compra mes a mes (esperar a que baje el precio)."
            else:
                recomendacion = "⚖️ PRECIO ESTABLE -> Sugerir compra regular (solo lo que consumirá en la semana)."
                
            texto_precios += f"- {p}: Actual ${precio_hoy:.2f} | En {meses_diferencia} meses: ${precio_fut:.2f} | {recomendacion} (Unidad: {unidad})\n"
        except IndexError:
            pass
            
    return texto_precios

# -------------------------------------------------------------
# 2. SIDEBAR – Perfil Nutricional y Canasta Inteligente
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

    # --- NUEVA SECCIÓN: CANASTA INTELIGENTE (MULTISELECT + BULK ADD) ---
    st.markdown("---")
    st.header("🛒 Mi Canasta Inteligente")
    st.write("Agrega por palabra clave o selecciona uno por uno. (Máx 30)")
    
    if "canasta_usuario" not in st.session_state:
        st.session_state.canasta_usuario = []

    def agregar_masivo():
        termino = st.session_state.busqueda_rapida.strip().lower()
        if termino:
            coincidencias = [p for p in lista_productos_db if termino in p.lower()]
            if coincidencias:
                nuevos_productos = list(set(st.session_state.canasta_usuario + coincidencias))
                if len(nuevos_productos) > 30:
                    nuevos_productos = nuevos_productos[:30]
                    st.toast("⚠️ Se alcanzó el límite máximo de 30 productos.", icon="🛑")
                else:
                    st.toast(f"✅ Se agregaron {len(coincidencias)} productos.", icon="🛒")
                st.session_state.canasta_usuario = nuevos_productos
            else:
                st.toast("No se encontraron productos con esa palabra.", icon="❌")
            st.session_state.busqueda_rapida = ""

    st.text_input("🔍 Búsqueda rápida (Ej. Pollo, Aceite):", 
                  key="busqueda_rapida", 
                  on_change=agregar_masivo,
                  help="Escribe un producto y presiona Enter para agregar todas sus variantes.")

    productos_elegidos = st.multiselect(
        "Edita o selecciona manualmente:", 
        options=lista_productos_db,
        key="canasta_usuario", 
        max_selections=30,
        placeholder="O busca uno por uno aquí..."
    )

# -------------------------------------------------------------
# 3. INTERFAZ DEL CHAT (Historial)
# -------------------------------------------------------------
st.title("🥗 NutriPeso IA: Tu Estratega de Ahorro y Salud")

if "messages" not in st.session_state:
    saludo = f"""¡Hola {nombre}! 👋 Soy **NutriPeso IA**.

Tu meta ideal es de **{int(cal_meta)} kcal/día**. 
Puedes pedirme una dieta general o **armar tu canasta en la barra lateral 👈** (puedes buscar palabras como 'Pollo' para agregar todos de golpe) y pedirme que te arme un plan.

Además de los precios, te diré si **conviene comprar hoy y congelar, o esperar a que baje el precio** según el pronóstico del mercado. 📉📈

¿Qué cocinamos hoy? 🛒"""
    st.session_state.messages = [{"role": "assistant", "content": saludo}]

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

# -------------------------------------------------------------
# 4. LÓGICA UNIFICADA DEL CHAT
# -------------------------------------------------------------
if prompt := st.chat_input("Ej: Ármame una cena con lo que seleccioné y dime qué me conviene comprar al por mayor...", key="chat_nutripeso"):
    
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analizando precios, pronósticos y armando tu plan..."):
            
            # --- A. CLASIFICACIÓN ---
            try:
                intent_res = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": SYSTEM_CLASSIFIER}, {"role": "user", "content": prompt}]
                )
                intent = intent_res.choices[0].message.content.upper()
            except Exception:
                intent = "DIETA" 

            # --- B. OBTENER PRECIOS EXACTOS Y PRONÓSTICO DEL DROPDOWN ---
            contexto_precios = obtener_precios_seleccionados(df_p, productos_elegidos)
            
            # --- C. LÓGICA DE RECETAS ---
            dieta_info = "Genera un plan basado en los ingredientes seleccionados y analiza los pronósticos."
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
                final_system = f"Eres NutriPeso IA. Perfil: {nombre}, {int(cal_meta)} kcal, {objetivo}."
            
            if productos_elegidos:
                final_system += f"\n\nCONTEXTO DE PRECIOS Y PRONÓSTICOS (CANASTA DEL USUARIO):\n{contexto_precios}"
            
            final_system += """\n\nREGLAS OBLIGATORIAS DE COSTOS Y COMPRAS: 
            1. Usa OBLIGATORIAMENTE los precios exactos que te proporcioné para calcular costos. NUNCA uses '[Precio por porción]'.
            2. Muestra los precios usando este formato exacto: '$45.00 MXN'.
            3. INCLUYE UNA SECCIÓN DE ESTRATEGIA DE COMPRAS: Revisa las alertas de "TENDENCIA AL ALZA" (📈) o "TENDENCIA A LA BAJA" (📉) en el contexto de precios. Aconseja al usuario qué productos debe comprar por mayoreo/congelar ahora mismo, y cuáles le conviene ir comprando mes a mes porque van a bajar de precio."""

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
