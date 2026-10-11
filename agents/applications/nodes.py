import hashlib
import json
from datetime import datetime, timezone

from agents.vacancies.graph import run_vacancy_agent
from agents.vacancies.scoring import candidate_skills, confirmed_skills, inferred_skills

from .catalog import load_vacancies_by_id
from .letters import compose_letter, is_letter_valid, signer_name, template_body
from .llm import generate_cover_letter
from .schemas import (
    APPLICATION_MODEL,
    CHANNEL,
    LETTER_VERSION,
    SCREENING_VERSION,
    ApplicationPackage,
)
from .screening import build_screening
from .state import ApplicationState


def _event(level: str, message: str, vacancy_id: str | None = None) -> dict:
    return {"level": level, "message": message, "vacancy_id": vacancy_id}


def resolve_vacancies_node(state: ApplicationState):
    """Reutiliza el agente de vacantes: mismo perfil, aclaraciones, inferencias, cargos y preferencias."""
    result = run_vacancy_agent(
        state["profile"], state["preferences"], state["clarifications"],
        state["selected_roles"], state["skill_results"],
    )
    matches_by_id = {match.vacancy_id: match for match in result["matches"]}
    catalog = load_vacancies_by_id()

    vacancies, matches, skipped = [], [], []
    events = [_event("agent", "[AGENTE] Iniciando automatización de postulación con LangGraph Agent...")]
    for vacancy_id in dict.fromkeys(state["selected_ids"]):
        if vacancy_id in catalog and vacancy_id in matches_by_id:
            vacancies.append(catalog[vacancy_id])
            matches.append(matches_by_id[vacancy_id])
        else:
            skipped.append(vacancy_id)
            events.append(_event("warning", f"[AVISO] La vacante {vacancy_id} ya no está disponible y se omitió.",
                                 vacancy_id))
    return {"vacancies": vacancies, "matches": matches, "skipped": skipped, "events": events}


def draft_letters_node(state: ApplicationState):
    profile = state["profile"]
    signer = signer_name(profile, state["user_name"])
    runs = list(state["inference_runs"])
    events = list(state["events"])
    letters = {}

    for vacancy, match in zip(state["vacancies"], state["matches"], strict=True):
        events.append(_event("step", f"[1/3] Redactando carta personalizada para: {vacancy.title}...", vacancy.id))
        body, run = generate_cover_letter(profile, vacancy, match)
        source = "groq"
        if body is None or not is_letter_valid(body, match):
            if body is not None:
                run = {**run, "status": "fallback", "error": "La carta generada no pasó la validación."}
            body = template_body(profile, vacancy, match)
            source = "template"
        letters[vacancy.id] = {"text": compose_letter(body, vacancy, signer), "source": source}
        runs.append(run)

    return {"letters": letters, "events": events, "inference_runs": runs}


def answer_screening_node(state: ApplicationState):
    profile = state["profile"]
    candidate = candidate_skills(profile)
    confirmed = confirmed_skills(state["clarifications"])
    inferred = inferred_skills(state["skill_results"], state["clarifications"])
    events = list(state["events"])
    screening = {}

    for vacancy in state["vacancies"]:
        events.append(_event(
            "step", f"[2/3] Respondiendo preguntas de filtro técnico para: {vacancy.title}...", vacancy.id))
        screening[vacancy.id] = build_screening(vacancy, state["preferences"], candidate, confirmed, inferred)

    return {"screening": screening, "events": events}


def _warnings(vacancy, match) -> list[str]:
    warnings = []
    if match.missing_required:
        warnings.append("Te faltan requisitos obligatorios: " + ", ".join(match.missing_required) + ".")
        if len(match.missing_required) / len(vacancy.required_skills) > 0.5:
            warnings.append("Cubres menos de la mitad de los requisitos obligatorios.")
    if not match.meets_preferences:
        warnings.append("Esta vacante está fuera de tus preferencias.")
    return warnings


def submit_applications_node(state: ApplicationState):
    """Envío simulado: no hay API externa. Deja el paquete y la evidencia de auditoría."""
    events = list(state["events"])
    packages = []
    submitted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for vacancy, match in zip(state["vacancies"], state["matches"], strict=True):
        letter = state["letters"][vacancy.id]
        screening = state["screening"][vacancy.id]
        digest = hashlib.sha256(json.dumps(
            {"cover_letter": letter["text"], "screening": [answer.model_dump() for answer in screening]},
            sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()

        packages.append(ApplicationPackage(
            vacancy_id=vacancy.id,
            title=vacancy.title,
            company=vacancy.company,
            score=match.score,
            cover_letter=letter["text"],
            letter_source=letter["source"],
            screening=screening,
            warnings=_warnings(vacancy, match),
            submitted_at=submitted_at,
            audit={
                "simulated": True,
                "channel": CHANNEL,
                "letter_version": LETTER_VERSION,
                "screening_version": SCREENING_VERSION,
                "letter_source": letter["source"],
                "model": APPLICATION_MODEL if letter["source"] == "groq" else None,
                "match_score": match.score,
                "matched_skills": match.matched_skills,
                "missing_required": match.missing_required,
                "package_sha256": digest,
            },
        ))
        events.append(_event(
            "success", f"[3/3] ¡Postulación enviada exitosamente a Magneto 365 Network! (simulada) · {vacancy.title}",
            vacancy.id))

    if packages:
        events.append(_event(
            "final", "[ÉXITO] Todas las postulaciones se han completado. Guardando evidencia de auditoría."))
    else:
        events.append(_event("warning", "[AVISO] No hay vacantes válidas para postular."))
    return {"packages": packages, "events": events}
