```

def calcular_mifflin_st_jeor(peso, altura, edad, genero, actividad):

    """

    Calcula las calorías diarias basadas en la tasa metabólica basal.

    actividad: 1.2 (sedentario), 1.375 (ligero), 1.55 (moderado), 1.725 (fuerte), 1.9 (atleta)

    """

    s = 5 if genero.upper() == "H" else -161

    tmb = (10 * peso) + (6.25 * altura) - (5 * edad) + s

    return tmb * actividad

def distribuir_macros(calorias, objetivo):

    """

    Distribuye Proteínas, Grasas y Carbohidratos según el objetivo.

    """

    if objetivo == "ganar_musculo":

        # 30% Prot, 25% Grasas, 45% Carbs

        return {"proteina": (calorias * 0.30) / 4, "grasas": (calorias * 0.25) / 9, "carbs": (calorias * 0.45) / 4}

    else:

        # 40% Prot, 20% Grasas, 40% Carbs (Déficit)

        return {"proteina": (calorias * 0.40) / 4, "grasas": (calorias * 0.20) / 9, "carbs": (calorias * 0.40) / 4}

```
