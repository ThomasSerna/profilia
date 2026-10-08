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

- Carga y procesamiento de hojas de vida en formato PDF desde la interfaz principal.
- Extracción del texto contenido en el PDF.
- Flujo del Agente de Perfil implementado con LangGraph.
- Extracción estructurada de datos del candidato mediante un LLM.
- Interfaz base de Profilia para el flujo agéntico.
- Sistema básico de autenticación con registro, inicio y cierre de sesión.
- Visualización de los datos del usuario autenticado dentro de la interfaz.

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
