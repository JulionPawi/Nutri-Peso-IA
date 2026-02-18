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
