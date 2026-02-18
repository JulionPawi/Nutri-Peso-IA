import os
import pandas as pd
from openai import OpenAI
from dotenv import load_dotenv
from src.prompts import SYSTEM_PROMPT, generar_prompt_consulta, BIENVENIDA_APP

# 1. Configuración inicial
load_dotenv()

# os.getenv buscará "OPENAI_API_KEY" en el sistema 
# (donde GitHub Actions la inyectará automáticamente)
api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise ValueError("No se encontró la OPENAI_API_KEY. Verifica tu archivo .env o los Secrets de GitHub.")

client = OpenAI(api_key=api_key)

# 2. Cargar bases de datos (viven en la raíz según tu repo)
df_precios = pd.read_csv('CANASTA_BASICA_CON_ETIQUETAS.csv')
df_nutri = pd.read_csv('ProductosMexicanos.csv')

def buscar_en_datos(query):
    """Busca coincidencias en los CSV de forma simple"""
    keyword = query.split()[-1] # Toma la última palabra como palabra clave (ej. 'arroz')
    
    # Buscar en Precios (unique_id)
    res_precios = df_precios[df_precios['unique_id'].str.contains(keyword, case=False, na=False)].head(2)
    # Buscar en Nutrición (product_name)
    res_nutri = df_nutri[df_nutri['product_name'].str.contains(keyword, case=False, na=False)].head(2)
    
    return res_nutri.to_string(), res_precios.to_string()

def chat_nutripeso():
    print("-" * 50)
    print(BIENVENIDA_APP)
    print("-" * 50)

    while True:
        user_input = input("\n👤 Tú: ")
        if user_input.lower() in ['salir', 'exit', 'bye']:
            print("¡Hasta luego! Recuerda cuidar tu salud y tu bolsillo.")
            break

        # Buscar contexto en los CSV
        info_n, info_p = buscar_en_datos(user_input)
        
        # Construir el prompt para la IA
        prompt_final = generar_prompt_consulta(user_input, info_n, info_p)

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo", # Puedes usar "gpt-4o" si tienes acceso
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_final}
                ],
                temperature=0.7
            )
            
            print(f"\n🥗 NutriPeso IA: {response.choices[0].message.content}")
        
        except Exception as e:
            print(f"Error al conectar con OpenAI: {e}")

if __name__ == "__main__":
    chat_nutripeso()
