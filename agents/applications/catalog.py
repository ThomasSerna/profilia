from agents.vacancies.dataset import load_vacancy_dataset
from agents.vacancies.normalize import normalize_vacancy
from agents.vacancies.schemas import Vacancy


def load_vacancies_by_id() -> dict[str, Vacancy]:
    """Vacantes válidas del dataset, indexadas por id. Las inválidas se omiten, igual que en el agente de vacantes."""
    vacancies: dict[str, Vacancy] = {}
    for raw in load_vacancy_dataset():
        try:
            vacancy = normalize_vacancy(raw)
        except ValueError:
            continue
        vacancies[vacancy.id] = vacancy
    return vacancies
