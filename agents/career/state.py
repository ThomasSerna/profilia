from typing import TypedDict

from agents.profile.schemas import ProfileData
from .schemas import RoleAssessment, RoleProfile


class CareerState(TypedDict):
    profile: ProfileData
    raw_text: str
    roles: list[RoleProfile]
    assessments: list[RoleAssessment]
    skill_results: dict
    clarifications: dict
    cached_assessments: dict[str, RoleAssessment]
    generate_recommendations: bool
    retry_recommendation: bool
    inference_runs: list[dict]
