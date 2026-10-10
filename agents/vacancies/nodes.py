from .dataset import load_vacancy_dataset
from .normalize import normalize_vacancy
from .scoring import candidate_skills, rank_matches, score_vacancy
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
    matches = [
        score_vacancy(candidate, vacancy, state["preferences"])
        for vacancy in state["vacancies"]
    ]
    return {"matches": rank_matches(matches)}
