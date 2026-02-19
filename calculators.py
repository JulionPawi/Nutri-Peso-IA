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
