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
- Groq / GPT-OSS 20B y GPT-OSS 120B
- Kev / Qwen3.5-0.8B y Qwen3.5-4B
- PyPDF

## Funcionalidades actuales

- Sistema de autenticación con registro, inicio y cierre de sesión.
- Carga y procesamiento de hojas de vida en PDF, con validación de formato y tamaño máximo de 10 MB.
- Extracción de texto y datos estructurados del candidato mediante el Agente de Perfil, implementado con LangGraph y un LLM.
- Almacenamiento del perfil y recuperación de los resultados al volver a ingresar.
- Reutilización de hojas de vida ya procesadas para evitar análisis repetidos.
- Selección y evaluación de entre uno y tres cargos del catálogo profesional.
- Evaluación de habilidades y coincidencia con los requisitos de cada cargo mediante Kev.
- Visualización de fortalezas, brechas e información pendiente para orientar la búsqueda de empleo.
- Exploración del catálogo para sugerir hasta tres cargos afines al perfil.
- Preguntas de aclaración sobre habilidades y actualización de la evaluación con las respuestas del usuario.
- Generación de recomendaciones profesionales para evaluaciones de coincidencia intermedia y reintento de recomendaciones pendientes.
- Guardado de preferencias de empleo por modalidad, ciudad y salario mínimo.
- Consulta y clasificación de vacantes de un conjunto de datos local según el perfil, las habilidades y las preferencias del usuario.
- Interfaz integrada para cargar la hoja de vida, consultar la orientación profesional y explorar vacantes.

## Configuración local

### Servidor django

Clonar el repositorio y descargar requerimientos del servicio en django:

```bash
git clone https://github.com/ThomasSerna/profilia.git
cd profilia
pip install -r requirements.txt
python manage.py migrate
```

### Modelo de decisión Kev

Clonar el repositorio y descargar requerimientos del modelo de decisión:

```bash
git clone --depth 1 --branch kev-1.0 https://github.com/jaredpalmer/kev.git vendor/kev
cd vendor/kev
uv sync --extra serve
```

Para levantarlo, ejecuta desde `vendor/kev`:

Modelo `kev-0.8b` (recomendado para prototipado):
```bash
uv run --extra serve python -m kev.serve --run jaredpalmer/kev-0.8b@v1.0 --port 8009
```

Modelo `kev-4b` (recomendado para producción):
```bash
uv run --extra serve python -m kev.serve --run jaredpalmer/kev-4b@v1.0 --port 8009
```

Antes de iniciar el proyecto, crea el archivo `.env` a partir de `.env.example` y configura las claves necesarias.

### Iniciar el servidor

```bash
python manage.py runserver
```

La aplicación principal se encuentra en:

```text
http://127.0.0.1:8000/
```
