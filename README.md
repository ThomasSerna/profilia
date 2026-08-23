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
- Groq / GPT-OSS 20B
- PyPDF

## Funcionalidades actuales

- Carga y procesamiento de hojas de vida en formato PDF desde la interfaz principal y el panel de depuración.
- Extracción del texto contenido en el PDF.
- Flujo del Agente de Perfil implementado con LangGraph.
- Extracción estructurada de datos del candidato mediante un LLM.
- Interfaz base de Profilia para el flujo agéntico y panel global de depuración.
- Sistema básico de autenticación con registro, inicio y cierre de sesión.
- Visualización de los datos del usuario autenticado dentro de la interfaz.

## Configuración local

```bash
git clone https://github.com/ThomasSerna/profilia.git
cd profilia
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Antes de iniciar el proyecto, crea el archivo `.env` a partir de `.env.example` y configura las claves necesarias.

La aplicación principal se encuentra en:

```text
http://127.0.0.1:8000/
```

El panel de depuración se encuentra en:

```text
http://127.0.0.1:8000/debug/
```
