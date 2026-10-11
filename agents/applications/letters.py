"""Carta de presentación: plantilla determinista, composición y validación.

La carta nunca puede afirmar habilidades que el candidato no tiene registradas.
Si el LLM menciona una habilidad faltante, la carta se descarta y se usa la plantilla.
"""

import re

from agents.profile.schemas import ProfileData
from agents.vacancies.normalize import fold_text
from agents.vacancies.schemas import Vacancy, VacancyMatch

from .schemas import MAX_LETTER_SKILLS

MIN_LETTER_CHARS = 80


def signer_name(profile: ProfileData, fallback: str = "") -> str:
    return (profile.name or "").strip() or (fallback or "").strip()


def mentions_skill(text: str, skill: str) -> bool:
    needle = re.escape(fold_text(skill))
    return re.search(rf"(?<![\w+#.]){needle}(?![\w+#])", fold_text(text)) is not None


def is_letter_valid(body: str, match: VacancyMatch) -> bool:
    text = body.strip()
    if len(text) < MIN_LETTER_CHARS or "@" in text:
        return False
    missing = match.missing_required + match.missing_nice
    return not any(mentions_skill(text, skill) for skill in missing)


def _experience(profile: ProfileData) -> str | None:
    for item in profile.experience:
        role = (item.role or "").strip()
        company = (item.company or "").strip()
        if role and company:
            return f"Cuento con experiencia como {role} en {company}"
        if role:
            return f"Cuento con experiencia como {role}"
    return None


def _education(profile: ProfileData) -> str | None:
    for item in profile.education:
        degree = (item.degree or "").strip()
        institution = (item.institution or "").strip()
        if degree and institution:
            return f"Mi formación incluye {degree} en {institution}"
        if degree:
            return f"Mi formación incluye {degree}"
    return None


def template_body(profile: ProfileData, vacancy: Vacancy, match: VacancyMatch) -> str:
    intro = f"Me interesa postularme a la vacante {vacancy.title}."
    strengths = match.matched_skills[:MAX_LETTER_SKILLS]
    if strengths:
        intro += f" En mi perfil aparecen habilidades relacionadas con lo que buscan: {', '.join(strengths)}."

    paragraphs = [intro]
    background = [item for item in (_experience(profile), _education(profile)) if item]
    if background:
        paragraphs.append(" ".join(f"{item}." for item in background))
    paragraphs.append("Quedo disponible para conversar sobre cómo puedo aportar al equipo.")
    return "\n\n".join(paragraphs)


def compose_letter(body: str, vacancy: Vacancy, signer: str) -> str:
    closing = f"Cordialmente,\n{signer}" if signer else "Cordialmente,"
    return "\n\n".join([f"Equipo de selección de {vacancy.company},", body.strip(), closing])
