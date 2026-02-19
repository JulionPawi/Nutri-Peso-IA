# 🥗 Nutri-Peso-IA: Optimizador Nutricional y Financiero

Nutri-Peso-IA es una herramienta de Inteligencia Artificial (IA) diseñada para **democratizar el acceso a una alimentación saludable** en México. Combina el análisis de métricas de salud con la monitorización de precios reales de la canasta básica en ciudades clave, como la CDMX, para ofrecer información accionable.

Este proyecto representa el trabajo final de diplomado, enfocado en la aplicación de metodologías de Ciencia de Datos y priorizando la usabilidad para el usuario final.

---

## 🚀 Resumen del Proyecto (Abstract)

Desarrollado por la compañía ficticia **NutriTech Solutions**, el proyecto aborda la falta de herramientas accesibles para anticipar fluctuaciones de precios y monitorear indicadores de salud básicos. La solución integra dos módulos principales:

1.  **Predicción de Precios:** Pronóstico de la canasta básica mediante el modelo **XGBoost**.
2.  **Interfaz de Salud:** Clasificación automatizada del estado nutricional (IMC) utilizando **Random Forest Classifier**.

---

## 🛠️ Estrategia y Usabilidad

El enfoque del desarrollo ha sido centrado en el usuario, garantizando una alta usabilidad y accesibilidad.

*   **Descripción de Usuarios:** Consumidores finales interesados en su economía doméstica y salud preventiva, así como profesionales de primer contacto (nutricionistas, médicos generales).
*   **Valor Accionable:** La herramienta proporciona información concreta para tomar decisiones informadas sobre el presupuesto alimenticio y el monitoreo de la salud física.
*   **Interfaz Intuitiva:** Implementada en **Streamlit** para asegurar una experiencia de usuario fluida y comprensible para un público general, sin necesidad de conocimientos técnicos previos.

**Interacciones en la Interfaz (Ejemplos de Chatbot):**

| Funcionalidad | Descripción |
| :--- | :--- |
| **📸 Analizar etiqueta** | Clasifica la calidad de un producto al subir una foto. |
| **🛒 Optimizar despensa** | Consulta el mejor momento para comprar productos básicos (ej: "¿Es buen momento para surtir el arroz?"). |
| **🥦 Plan Económico** | Genera una dieta balanceada ajustada a un bajo presupuesto. |

---

## 📊 Metodología y Procesamiento de Datos

*   **Fuentes de Datos:** Se utilizaron **APIs y técnicas de *web scraping*** de datos corporativos y fuentes externas validadas. *(Nota: No se utilizó Kaggle como fuente, cumpliendo con la restricción académica).*
*   **Modelación Principal:**
    *   **Clasificación (IMC):** Random Forest Classifier.
    *   **Series de Tiempo (Precios):** XGBoost.
*   **Procesamiento de IA:** Se implementaron modelos avanzados para el tratamiento de datos:
    *   **GPT-4o-mini:** Para la estandarización de nombres de productos.
    *   **Sentence Transformers:** Para la homologación semántica entre distintos sets de datos.

---

## 📂 Contenido del Repositorio

El repositorio contiene los siguientes archivos clave para la reproducibilidad del proyecto:

*   `AguilarAyalaJulioProyectoFinalM5.ipynb`: El Notebook principal que documenta el ciclo completo de vida del dato: Análisis Exploratorio (EDA), limpieza, procesamiento y modelado.
*   `app.py`: El script principal de la aplicación con la interfaz de usuario funcional en Streamlit.
*   `Documentación`: Informe detallado con el sustento técnico y las conclusiones del proyecto.

---

## 💻 Instalación y Reproducibilidad

Para garantizar que el proyecto se pueda ejecutar sin errores (cumpliendo el criterio de reproducibilidad), siga estos pasos:

1.  **Clonar repositorio:**

    ```bash
    git clone [https://github.com/JulionPawi/Nutri-Peso-IA.git](https://github.com/JulionPawi/Nutri-Peso-IA.git)
    cd Nutri-Peso-IA
    ```

2.  **Instalar dependencias:**

    ```bash
    pip install streamlit pandas scikit-learn xgboost mlforecast sentence-transformers openai
    ```

3.  **Ejecutar la Interfaz (UI):**

    ```bash
    streamlit run app.py
    ```

*(Asegúrese de configurar su clave API en un archivo `.env` o similar para el correcto funcionamiento de los modelos de IA implementados para el procesamiento.)*
