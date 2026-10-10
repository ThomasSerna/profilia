from typing import TypedDict

from agents.profile.schemas import ProfileData

from .schemas import Preferences, Vacancy, VacancyMatch


class VacancyState(TypedDict):
    profile: ProfileData
    preferences: Preferences
    clarifications: dict
    skill_results: dict
    selected_roles: list[str]
    raw_vacancies: list[dict]
    vacancies: list[Vacancy]
    skipped: list[str]
    matches: list[VacancyMatch]
