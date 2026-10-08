from typing import Literal

from pydantic import BaseModel, Field

EVALUATOR_VERSION = "skill_matching_v1"
KEV_EVALUATOR_VERSION = "kev_requirements_v1"

class RoleProfile(BaseModel):
    name: str
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_areas: list[str] = Field(default_factory=list)


class SkillEvidence(BaseModel):
    value: str
    source: str

class KevProbabilities(BaseModel):
    cumple: float = Field(ge=0, le=1)
    incumple: float = Field(ge=0, le=1)
    sin_evidencia: float = Field(ge=0, le=1)


class KevChoiceAnswer(BaseModel):
    type: Literal["choice"]
    choice: Literal["cumple", "incumple", "sin_evidencia"]
    confidence: float = Field(ge=0, le=1)
    probabilities: KevProbabilities


class RequirementMatch(BaseModel):
    skill: str
    category: Literal["required", "preferred"]

    status: Literal[
        "evidencia_en_perfil",
        "cumple",
        "incumple",
        "sin_evidencia",
    ]

    evidence: list[SkillEvidence] = Field(default_factory=list)
    probabilities: KevProbabilities | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class RoleAssessment(BaseModel):
    role_name: str
    evaluator: str = EVALUATOR_VERSION
    requirements: list[RequirementMatch] = Field(default_factory=list)
    summary: str = ""

    usage: dict[str, int] = Field(default_factory=dict)
    latency_ms: float | None = Field(default=None, ge=0)