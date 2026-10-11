from typing import TypedDict

from agents.profile.schemas import ProfileData
from agents.vacancies.schemas import Preferences, Vacancy, VacancyMatch

from .schemas import ApplicationPackage


class ApplicationState(TypedDict):
    profile: ProfileData
    preferences: Preferences
    clarifications: dict
    skill_results: dict
    selected_roles: list[str]
    selected_ids: list[str]
    user_name: str
    vacancies: list[Vacancy]
    matches: list[VacancyMatch]
    letters: dict
    screening: dict
    packages: list[ApplicationPackage]
    skipped: list[str]
    events: list[dict]
    inference_runs: list[dict]
