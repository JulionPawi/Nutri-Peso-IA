import pandas as pd
import difflib
def calcular_mifflin_st_jeor(peso, altura, edad, genero, actividad):
    # s = 5 para hombres, -161 para mujeres
    s = 5 if genero.upper() == "H" else -161
    tmb = (10 * peso) + (6.25 * altura) - (5 * edad) + s
    return tmb * actividad

def distribuir_macros(calorias, objetivo):
    if objetivo == "ganar_musculo":
        # 30% Prot, 25% Grasas, 45% Carbs
        return {
            "proteina": (calorias * 0.30) / 4,
            "grasas": (calorias * 0.25) / 9,
            "carbs": (calorias * 0.45) / 4
        }
    else: # perder_peso (Déficit leve)
        calorias_ajustadas = calorias - 500
        return {
            "proteina": (calorias_ajustadas * 0.40) / 4,
            "grasas": (calorias_ajustadas * 0.20) / 9,
            "carbs": (calorias_ajustadas * 0.40) / 4,
            "calorias_final": calorias_ajustadas
        }

def limpiar_nombre_producto(texto_csv):
    try:
        # Separamos por la pipa |
        partes = texto_csv.split('|')
        categoria = partes[0].strip()
        detalles = partes[1].strip() if len(partes) > 1 else ""
        
        # Limpiamos comas y palabras repetidas del detalle
        detalles_limpios = detalles.replace(", ", " ").title()
        return f"{detalles_limpios} ({categoria.capitalize()})"
    except:
        return texto_csv

def buscador_nutripeso(query, dataframe):
    # 1. Preparar palabras clave (tokens)
    stop_words = {"DE", "CON", "LAS", "LOS", "PARA", "SIN", "BOTELLA", "FRASCO", "SOBRE"}
    tokens = [t.upper() for t in query.split() if t.upper() not in stop_words and len(t) > 2]
    
    if not tokens:
        return pd.DataFrame()

    # 2. Búsqueda por Intersección (Deben estar todas las palabras)
    # Esto evita que si buscas "Arroz con Leche" te traiga todo el "Leche"
    mask = dataframe['unique_id'].str.contains(tokens[0], case=False, na=False)
    for t in tokens[1:]:
        mask &= dataframe['unique_id'].str.contains(t, case=False, na=False)
    
    resultados = dataframe[mask].copy()

    # 3. Fuzzy Fallback (Si no hay coincidencia exacta, buscamos "parecidos")
    if resultados.empty:
        nombres_unicos = dataframe['unique_id'].unique()
        # Buscamos coincidencias cercanas para el token más importante (el primero)
        matches = difflib.get_close_matches(tokens[0], nombres_unicos, n=5, cutoff=0.5)
        resultados = dataframe[dataframe['unique_id'].isin(matches)].copy()

    # 4. Sistema de Scoring (Ranking)
    def calcular_score(row_text):
        score = 0
        partes = row_text.split('|')
        categoria = partes[0]
        detalle = partes[1] if len(partes) > 1 else ""
        
        for t in tokens:
            if t in detalle.upper(): score += 3 # Prioridad alta si está en la marca/producto
            if t in categoria.upper(): score += 1 # Prioridad baja si está en la categoría
        return score

    if not resultados.empty:
        resultados['score'] = resultados['unique_id'].apply(calcular_score)
        resultados = resultados.sort_values(by='score', ascending=False)

    return resultados.head(8) # Retornamos los 8 mejores
def buscador_inteligente_ia(query, dataframe, client):
    # 1. Extraemos los 30 candidatos más probables por texto (Rápido y barato)
    stop_words = {"DE", "CON", "UN", "EL", "PARA", "QUIERO", "BUSCO"}
    tokens = [t.upper() for t in query.split() if t.upper() not in stop_words]
    
    # Buscamos filas que contengan alguna de las palabras clave
    patron = "|".join(tokens)
    candidatos = dataframe[dataframe['unique_id'].str.contains(patron, case=False, na=False)].copy()
    
    if candidatos.empty:
        return pd.DataFrame()

    # Si hay demasiados, nos quedamos con los 30 mejores según coincidencia de texto
    candidatos = candidatos.head(30) 

    # 2. Le preguntamos a la IA cuál es el mejor (El "Cerebro")
    lista_para_ia = candidatos['unique_id'].tolist()
    
    prompt_filtro = f"""
    Usuario busca: "{query}"
    Lista de productos: {lista_para_ia}
    
    Instrucción: Selecciona los 5 productos de la lista que mejor coincidan con la intención del usuario. 
    Prioriza cortes de carne si pide carne, o marcas específicas si las menciona.
    Responde ÚNICAMENTE con los nombres exactos separados por comas.
    """
    
    respuesta = client.chat.completions.create(
        model="gpt-4o-mini", # Usamos el modelo barato para filtrar
        messages=[{"role": "system", "content": "Eres un experto en compras de supermercado en México."},
                  {"role": "user", "content": prompt_filtro}],
        temperature=0
    )
    
    seleccionados = [s.strip() for s in respuesta.choices[0].message.content.split(",")]
    
    # 3. Retornamos solo los que la IA eligió
    return dataframe[dataframe['unique_id'].isin(seleccionados)]

def cargar_precios_optimizados():
    try:
        # 1. Cargar tu archivo limpio
        df = pd.read_csv('CANASTA_BASICA_CON_ETIQUETAS.csv')
        
        # 2. Filtrar por la fecha más reciente para dar precios actuales
        fecha_reciente = df['ds'].max()
        df_actual = df[df['ds'] == fecha_reciente]

        # 3. Diccionario de búsqueda inteligente (Usamos palabras clave directas)
        # La IA buscará CUALQUIERA de estas palabras en el nombre limpio
        busquedas = {
            "Pechuga de Pollo": ["Pechuga"],
            "Arroz": ["Arroz"],
            "Brócoli": ["Brocoli", "Brócoli"],
            "Filete de Pescado (Mojarra/Tilapia/Atún)": ["Tilapia", "Mojarra", "Atún", "Atun"],
            "Yogur Griego": ["Griego", "Fage", "Oikos"] # Ya no exigimos la palabra "Yogurt"
        }

        texto_precios = "BASE DE DATOS DE PRECIOS REALES (MXN):\n"

        for producto, keywords in busquedas.items():
            # Crear un patrón de búsqueda tipo "Palabra1|Palabra2" (OR)
            patron = '|'.join(keywords)
            mask = df_actual['unique_id'].str.contains(patron, case=False, na=False)
            
            # Filtro extra: si es Pechuga, evitar que traiga "Pechuga Cordon Blue" (congelados caros)
            if producto == "Pechuga de Pollo":
                mask &= ~df_actual['unique_id'].str.contains("Cordon", case=False, na=False)
                
            resultados = df_actual[mask]
            
            if not resultados.empty:
                # Calcular el precio promedio de las variantes encontradas
                precio_promedio = resultados['y'].mean()
                
                # Tomar el nombre del primer producto real encontrado como ejemplo
                ejemplo_real = resultados['unique_id'].iloc[0]
                
                texto_precios += f"- {producto}: ${precio_promedio:.2f} por KG/Unidad (Recomienda: {ejemplo_real})\n"
            else:
                texto_precios += f"- {producto}: Precio no disponible (Estimar costo del mercado local)\n"
        
        return texto_precios

    except Exception as e:
        return f"Error leyendo base de datos: {e}"

# --- PRUEBA RÁPIDA (Opcional, para que veas qué le manda a la IA) ---
# print(cargar_precios_optimizados())

def buscar_precios_reales(df, prompt_usuario, texto_dieta=""):
    """Busca precios en la base de datos basándose en el prompt o los ingredientes."""
    if df.empty:
        return "Base de datos de precios no disponible."
        
    fecha_reciente = df['ds'].max()
    df_actual = df[df['ds'] == fecha_reciente]
    
    # Unimos lo que pidió el usuario + la dieta sugerida para buscar todo de una vez
    texto_busqueda = f"{prompt_usuario} {texto_dieta}".lower()

    # Diccionario 100% adaptado a tu archivo CSV
    busquedas = {
        "Pollo": ["pollo", "pechuga"],
        "Carne de Res": ["res", "bistec", "molida", "retazo", "arrachera", "chamabrete", "diezmillo"],
        "Pescado": ["tilapia", "mojarra", "pescado", "atún", "atun", "salmón", "salmon", "basa"],
        "Cerdo": ["cerdo", "chuleta", "lomo", "tocino", "pierna"],
        "Arroz": ["arroz"],
        "Avena": ["avena"],
        "Frijoles": ["frijol", "frijoles", "lentejas"],
        "Huevos": ["huevo", "huevos"],
        "Leche": ["leche"],
        "Yogur": ["yogurt", "batido", "griego", "activia"],
        "Queso": ["queso", "panela", "oaxaca", "manchego", "cottage"],
        "Jugo": ["jugo ", "jugo de", "nectar", "néctar", "boing", "jumex"], 
        "Verduras (Verdes)": ["espinaca", "brócoli", "brocoli", "calabacita", "lechuga"], 
        "Tomate y Cebolla": ["tomate", "jitomate", "cebolla"],
        "Zanahoria": ["zanahoria"],
        "Fruta": ["manzana", "platano", "plátano", "durazno"],
        "Aguacate": ["aguacate"],
        "Aceite": ["aceite"]
    }

    texto_precios = "DATOS EXTRAÍDOS DE LA CANASTA BÁSICA (PRECIOS REALES MXN):\n"
    encontrados = 0

    # Buscar en la base de datos
    for categoria, keywords in busquedas.items():
        if any(kw in texto_busqueda for kw in keywords):
            
            # Buscar coincidencias exactas con el diccionario
            patron = '|'.join(keywords)
            mask = df_actual['unique_id'].str.contains(patron, case=False, na=False)
            
            # --- FILTROS DE LIMPIEZA BASADOS EN TU CSV ---
            if categoria == "Pollo":
                mask &= ~df_actual['unique_id'].str.contains("Cordon|Suiza|Papilla", case=False, na=False)
            elif categoria == "Jugo":
                # Evitar que te recomiende Mayonesa o Jugo Maggi
                mask &= ~df_actual['unique_id'].str.contains("Mayonesa|Maggi|Clamato", case=False, na=False)
            elif categoria == "Yogur":
                # Evitar confusiones con leches saborizadas o yakult
                mask &= ~df_actual['unique_id'].str.contains("Yakult", case=False, na=False)
                
            resultados = df_actual[mask]
            
            if not resultados.empty:
                precio_promedio = resultados['y'].mean()
                
                # TOMAR HASTA 3 EJEMPLOS REALES PARA DAR VARIEDAD
                ejemplos_reales = resultados['unique_id'].drop_duplicates().head(3).tolist()
                ejemplos_texto = " | ".join(ejemplos_reales) 
                
                texto_precios += f"- {categoria}: Aprox ${precio_promedio:.2f} MXN (Opciones: {ejemplos_texto})\n"
                encontrados += 1

    if encontrados == 0:
        return "No se encontraron precios exactos para los ingredientes de la receta. Considera los precios estándar de tu localidad."
        
    return texto_precios
