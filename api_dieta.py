# api_dieta.py
import requests
import os
from dotenv import load_dotenv

load_dotenv()

class NutriAPI:
    def __init__(self):
        self.app_id = os.getenv("EDAMAM_APP_ID")
        self.app_key = os.getenv("EDAMAM_APP_KEY")
        self.url = "https://api.edamam.com/search"

    def buscar_recetas(self, query, calorias_rango, alergias=None):
        # Si no hay llaves, devolvemos None para que el bot use la local
        if not self.app_id or not self.app_key:
            return None
            
        params = {
            "q": query,
            "app_id": self.app_id,
            "app_key": self.app_key,
            "calories": calorias_rango,
        }
        if alergias: params["health"] = alergias
        
        try:
            response = requests.get(self.url, params=params)
            return response.json()
        except:
            return None
