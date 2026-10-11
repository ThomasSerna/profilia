"""Preguntas de filtro. Las respuestas salen solo del perfil, las aclaraciones y las preferencias."""

from agents.profile.schemas import ProfileData  # noqa: F401  (tipo documentado en la firma del agente)
from agents.vacancies.normalize import fold_text, skill_key
from agents.vacancies.schemas import Preferences, Vacancy

from .schemas import MAX_SCREENING_SKILLS, ScreeningAnswer


def _cop(value: int) -> str:
    return f"${value:,.0f} COP".replace(",", ".")


def _skill_answer(skill: str, candidate: dict, confirmed: dict, inferred: dict) -> ScreeningAnswer:
    key = skill_key(skill)
    question = f"¿Tienes experiencia con {skill}?"

    if key in candidate:
        return ScreeningAnswer(question=question, status="cumple", source="perfil",
                               answer=f"Sí, {skill} aparece en mi perfil profesional.")
    if key in confirmed:
        return ScreeningAnswer(question=question, status="cumple", source="aclaracion",
                               answer=f"Sí, lo confirmé al responder las preguntas de Profilia sobre {skill}.")
    if key in inferred:
        return ScreeningAnswer(question=question, status="cumple", source="inferida",
                               answer=f"Sí, mi perfil incluye información relacionada con {skill}.")
    return ScreeningAnswer(question=question, status="sin_evidencia", source="ninguna",
                           answer=f"No tengo información registrada sobre {skill} en mi perfil.")


def build_screening(vacancy: Vacancy, preferences: Preferences, candidate: dict[str, str],
                    confirmed: dict[str, str], inferred: dict[str, str]) -> list[ScreeningAnswer]:
    answers = [
        _skill_answer(skill, candidate, confirmed, inferred)
        for skill in vacancy.required_skills[:MAX_SCREENING_SKILLS]
    ]

    modality_question = f"¿Puedes trabajar en modalidad {vacancy.modality}?"
    if preferences.modality == "any":
        answers.append(ScreeningAnswer(question=modality_question, status="informativa", source="preferencias",
                                       answer="Sí, no tengo una modalidad preferida."))
    elif preferences.modality == vacancy.modality:
        answers.append(ScreeningAnswer(question=modality_question, status="informativa", source="preferencias",
                                       answer="Sí, coincide con mi preferencia."))
    else:
        answers.append(ScreeningAnswer(question=modality_question, status="informativa", source="preferencias",
                                       answer=f"Mi modalidad preferida es {preferences.modality}."))

    if vacancy.modality != "remoto" and vacancy.city:
        city_question = f"¿Puedes trabajar en {vacancy.city}?"
        if not preferences.city:
            answers.append(ScreeningAnswer(question=city_question, status="informativa", source="preferencias",
                                           answer="No indiqué una ciudad preferida."))
        elif fold_text(preferences.city) == fold_text(vacancy.city):
            answers.append(ScreeningAnswer(question=city_question, status="informativa", source="preferencias",
                                           answer=f"Sí, {vacancy.city} es mi ciudad preferida."))
        else:
            answers.append(ScreeningAnswer(question=city_question, status="informativa", source="preferencias",
                                           answer=f"Mi ciudad preferida es {preferences.city}."))

    answers.append(ScreeningAnswer(
        question="¿Cuál es tu aspiración salarial?",
        status="informativa",
        source="preferencias",
        answer=(f"Mi aspiración salarial mínima es {_cop(preferences.salary_min)}."
                if preferences.salary_min else "No he indicado una aspiración salarial."),
    ))
    return answers
