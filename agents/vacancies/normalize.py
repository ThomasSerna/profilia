import re
import unicodedata

from agents.career.roles import get_role_by_name

from .schemas import Vacancy

MODALITY_ALIASES = {
    "remoto": "remoto",
    "remote": "remoto",
    "100% remoto": "remoto",
    "teletrabajo": "remoto",
    "hibrido": "hibrido",
    "hybrid": "hibrido",
    "presencial": "presencial",
    "onsite": "presencial",
    "on-site": "presencial",
}

# Claves ya normalizadas con fold_text(). Los valores son el nombre canónico.
SKILL_ALIASES = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "py": "Python",
    "python": "Python",
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "sql": "SQL",
    "rest": "REST APIs",
    "rest api": "REST APIs",
    "rest apis": "REST APIs",
    "api rest": "REST APIs",
    "apis rest": "REST APIs",
    "fastapi": "FastAPI",
    "django": "Django",
    "docker": "Docker",
    "git": "Git",
    "langchain": "LangChain",
    "langgraph": "LangGraph",
    "llm": "LLMs",
    "llms": "LLMs",
    "power bi": "Power BI",
    "powerbi": "Power BI",
    "excel": "Excel",
    "aws": "AWS",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "ci cd": "CI/CD",
    "machine learning": "Machine Learning",
    "ml": "Machine Learning",
    "pandas": "Pandas",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "html": "HTML",
    "css": "CSS",
}


def fold_text(text: str) -> str:
    """Minúsculas, sin tildes y con espacios colapsados, para comparar textos."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(without_accents.lower().split())


def normalize_modality(value: str) -> str | None:
    return MODALITY_ALIASES.get(fold_text(value))


def normalize_skill(raw: str) -> str:
    cleaned = " ".join(raw.split())
    return SKILL_ALIASES.get(fold_text(cleaned), cleaned)


def skill_key(name: str) -> str:
    """Clave para comparar habilidades: ignora mayúsculas, tildes y alias."""
    return fold_text(normalize_skill(name))


def unique_skills(items: list[str]) -> list[str]:
    seen, result = set(), []
    for item in items:
        name = normalize_skill(item)
        key = skill_key(item)
        if key and key not in seen:
            seen.add(key)
            result.append(name)
    return result


def normalize_city(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    return " ".join(value.split())


def _to_int(value) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    digits = re.sub(r"\D", "", str(value))
    return int(digits) if digits else None


def normalize_vacancy(raw: dict) -> Vacancy:
    """Convierte una vacante cruda del dataset en una Vacancy válida.

    Lanza ValueError si la modalidad es desconocida o los datos no son válidos.
    """
    modality = normalize_modality(str(raw.get("modality", "")))
    if modality is None:
        raise ValueError(f"Modalidad desconocida: {raw.get('modality')!r}")

    role = get_role_by_name(str(raw.get("role", "")).strip())
    if role is None:
        raise ValueError(f"Cargo fuera del catálogo: {raw.get('role')!r}")

    return Vacancy(
        id=str(raw.get("id", "")).strip(),
        title=" ".join(str(raw.get("title", "")).split()),
        company=" ".join(str(raw.get("company", "")).split()),
        role=role.name,
        modality=modality,
        city=normalize_city(raw.get("city")),
        salary_min=_to_int(raw.get("salary_min")),
        salary_max=_to_int(raw.get("salary_max")),
        required_skills=unique_skills(raw.get("required_skills", [])),
        nice_skills=unique_skills(raw.get("nice_skills", [])),
        source=str(raw.get("source", "dataset")),
        description=" ".join(str(raw.get("description", "")).split()),
    )
