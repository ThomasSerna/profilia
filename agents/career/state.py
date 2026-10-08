from typing import TypedDict

from agents.profile.schemas import ProfileData
from .schemas import RoleAssessment, RoleProfile


class CareerState(TypedDict):
    profile: ProfileData
    raw_text: str
    roles: list[RoleProfile]
    assessments: list[RoleAssessment]
    reused: bool