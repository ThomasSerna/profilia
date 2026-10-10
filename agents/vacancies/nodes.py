from .dataset import load_vacancy_dataset
from .normalize import normalize_vacancy
from agents.vacancies.normalize import fold_text
from .scoring import candidate_skills, confirmed_skills, inferred_skills, rank_matches, score_vacancy
from .state import VacancyState


def ingest_vacancies_node(state: VacancyState):
    return {"raw_vacancies": load_vacancy_dataset()}


def normalize_vacancies_node(state: VacancyState):
    vacancies = []
    skipped = []
    for raw in state["raw_vacancies"]:
        try:
            vacancies.append(normalize_vacancy(raw))
        except ValueError:
            identifier = raw.get("id", "desconocido") if isinstance(raw, dict) else "desconocido"
            skipped.append(str(identifier))
    return {"vacancies": vacancies, "skipped": skipped}


def match_vacancies_node(state: VacancyState):
    candidate = candidate_skills(state["profile"])
    confirmed = confirmed_skills(state.get("clarifications"))
    inferred = inferred_skills(state.get("skill_results"), state.get("clarifications"))
    selected_roles = {fold_text(name) for name in state.get("selected_roles") or []}
    matches = [
        score_vacancy(candidate, vacancy, state["preferences"], confirmed, selected_roles, inferred)
        for vacancy in state["vacancies"]
    ]
    return {"matches": rank_matches(matches)}
