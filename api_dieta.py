```

import requests

import os

from dotenv import load_dotenv

load_dotenv()

class NutriAPI:

    def __init__(self):

        self.app_id = os.getenv("EDAMAM_APP_ID")

        self.app_key = os.getenv("EDAMAM_APP_KEY")

        self.url = "[enlace sospechoso eliminado]"

    def buscar_recetas(self, query, calorias_rango, alergias=None, excluidos=None):

        params = {

            "q": query,

            "app_id": self.app_id,

            "app_key": self.app_key,

            "calories": calorias_rango,

        }

        if alergias: params["health"] = alergias

        if excluidos: params["excluded"] = excluidos

        

        response = requests.get(self.url, params=params)

        return response.json()

```
