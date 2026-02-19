# api_dieta.py
import requests
import os
import logging

# Configuramos un logger para saber qué pasa si la API falla
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NutriAPI:
    def __init__(self):
        self.app_id = os.getenv("EDAMAM_APP_ID")
        self.app_key = os.getenv("EDAMAM_APP_KEY")
        self.url = "https://api.edamam.com/search"
        
        # Validación temprana
        self.is_active = bool(self.app_id and self.app_key)
        if not self.is_active:
            logger.warning("⚠️ Edamam Credentials no encontradas. Usando modo local.")

    def buscar_recetas(self, query: str, calorias_rango: str, alergias: list = None):
        if not self.is_active:
            return None
            
        params = {
            "q": query,
            "app_id": self.app_id,
            "app_key": self.app_key,
            "calories": calorias_rango,
            "from": 0,
            "to": 5,  # Limitamos a 5 para no saturar la UI de Streamlit
        }
        
        # Edamam espera 'health' como una lista de strings
        if alergias: 
            params["health"] = alergias
        
        try:
            response = requests.get(self.url, params=params, timeout=10) # Timeout para que el bot no se quede colgado
            response.raise_for_status() # Lanza error si el status no es 200
            
            data = response.json()
            
            # Limpiamos los datos para que el bot solo reciba lo que necesita
            return self._procesar_resultados(data)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error en la petición a Edamam: {e}")
            return None

    def _procesar_resultados(self, data):
        """Extrae solo la info relevante para ahorrar memoria y tokens"""
        if not data.get("hits"):
            return []
            
        return [
            {
                "nombre": hit["recipe"]["label"],
                "imagen": hit["recipe"]["image"],
                "url": hit["recipe"]["url"],
                "calorias": round(hit["recipe"]["calories"]),
                "ingredientes": hit["recipe"]["ingredientLines"]
            }
            for hit in data["hits"]
        ]
