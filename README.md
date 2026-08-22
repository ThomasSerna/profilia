# Profilia

Proyecto de Ingeniería de Software orientado a una arquitectura agéntica para apoyar el proceso de búsqueda de empleo.

## Integrantes

- Samuel Molina Garcés
- Thomas Serna Saldarriaga
- Juan Diego Parra Castañeda
- Juan Esteban Palacio Betancur

## Stack

- Python 3.13
- Django
- LangGraph
- Groq / Llama 3.3
- PyPDF

## Funcionalidades actuales

- Carga de hojas de vida en formato PDF desde una interfaz web de depuración.
- Extracción del texto contenido en el PDF.
- Flujo del Agente de Perfil implementado con LangGraph.
- Extracción estructurada de datos del candidato mediante un LLM.
- Visualización del texto leído y del perfil generado para pruebas del MVP.

## Configuración local

```bash
git clone https://github.com/ThomasSerna/profilia.git
cd profilia
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

La interfaz de depuración del Agente de Perfil se encuentra en:

```text
http://127.0.0.1:8000/debug/profile/
```
