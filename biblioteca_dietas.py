# biblioteca_dietas.py

DIETAS_BASE = {
    "vegana": {
        "nombre": "Plan Plant-Based",
        "tips": "Combina cereales con leguminosas.",
        "sugerencia": "Ensalada de lentejas con nopales y arroz.", # <--- Debe decir 'sugerencia'
        "items": ["LENTEJA", "NOPAL", "ARROZ"]
    },
    "ganar_musculo": {
        "nombre": "Plan Hipertrofia",
        "tips": "Aumenta la proteína y carbohidratos.",
        "sugerencia": "Bistec de res con papas y frijoles.",
        "items": ["BISTEC", "PAPA", "FRIJOL"]
    },
    "perder_peso": {
        "nombre": "Plan Déficit Calórico",
        "tips": "Prioriza verduras de hoja verde.",
        "sugerencia": "Pechuga de pollo con calabacitas.",
        "items": ["POLLO", "CALABACITA", "HUEVO", "ESPINACA"] # <--- Estos deben ser términos del CSV
    }
}
