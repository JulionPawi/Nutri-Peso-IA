```

from calculators import calcular_mifflin_st_jeor, distribuir_macros

from api_handler import NutriAPI

def chatbot():

    print("--- Nutri-Peso-IA ---")

    # Simulación de inputs del usuario

    peso = float(input("Peso (kg): "))

    altura = float(input("Altura (cm): "))

    edad = int(input("Edad: "))

    genero = input("Género (H/M): ")

    objetivo = input("Objetivo (ganar_musculo/perder_peso): ")

    

    calorias = calcular_mifflin_st_jeor(peso, altura, edad, genero, 1.55)

    macros = distribuir_macros(calorias, objetivo)

    

    print(f"\nTu objetivo calórico es: {calorias:.0f} kcal")

    print(f"Macros sugeridos: {macros}")

    

    # Consultar API

    api = NutriAPI()

    resultados = api.buscar_recetas("chicken", f"{int(calorias/3)}-{int(calorias/2)}")

    

    if "hits" in resultados:

        print("\nSugerencia de comida:")

        print(f"- {resultados['hits'][0]['recipe']['label']}")

        print(f"- Link: {resultados['hits'][0]['recipe']['url']}")

if __name__ == "__main__":

    chatbot()

```
