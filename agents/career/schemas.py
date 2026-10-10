from typing import Literal

from pydantic import BaseModel, Field, model_validator

EVALUATOR_VERSION = "skill_matching_v1"
KEV_EVALUATOR_VERSION = "kev_profile_skills_v3"
RUBRIC_VERSION = "career_rubric_v1"
RECOMMENDATION_VERSION = "career_recommendation_v3"
RECOMMENDATION_MODEL = "openai/gpt-oss-120b"
MIN_KEV_CONFIDENCE = 0.60

class RoleProfile(BaseModel):
    name: str
    required_skills: list[str] = Field(default_factory=list)
    required_skill_alternatives: list[list[str]] = Field(default_factory=list)
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

    @model_validator(mode="after")
    def validate_probabilities(self):
        probabilities = self.probabilities.model_dump()
        if (
            abs(sum(probabilities.values()) - 1) > 0.01
            or probabilities[self.choice] < max(probabilities.values())
        ):
            raise ValueError("Kev devolvió probabilidades inconsistentes.")
        return self


class KevMetrics(BaseModel):
    usage: dict[str, int] = Field(default_factory=dict)
    latency_ms: float | None = Field(default=None, ge=0)


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
    source: Literal["kev", "user_clarification", "rule"] = "kev"
    kev_answer: KevChoiceAnswer | None = None
    alternatives: list["RequirementMatch"] = Field(default_factory=list)


class RecommendationAction(BaseModel):
    skill: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=800)
    evidence_of_progress: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_nonempty_text(self):
        for field in ("skill", "action", "evidence_of_progress"):
            value = getattr(self, field).strip()
            if not value:
                raise ValueError("La acción no puede tener campos vacíos.")
            setattr(self, field, value)
        return self


class CareerRecommendation(BaseModel):
    text: str = Field(min_length=1, max_length=1600)
    actions: list[RecommendationAction] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def validate_nonempty_text(self):
        self.text = self.text.strip()
        if not self.text:
            raise ValueError("La recomendación no puede estar vacía.")
        return self


class RoleAssessment(BaseModel):
    role_name: str
    evaluator: str = EVALUATOR_VERSION
    requirements: list[RequirementMatch] = Field(default_factory=list)
    summary: str = ""
    score_min: float = Field(default=0, ge=0, le=100)
    score_max: float = Field(default=100, ge=0, le=100)
    required_coverage: float = Field(default=0, ge=0, le=1)
    group: Literal["high", "medium", "low", "pending"] = "pending"
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    unknown_skills: list[str] = Field(default_factory=list)
    recommendation: CareerRecommendation | None = None
    recommendation_status: Literal["not_requested", "ready", "pending"] = "not_requested"
    recommendation_source: Literal["template", "groq", "none"] = "none"
    recommendation_key: str = ""

    usage: dict[str, int] = Field(default_factory=dict)
    latency_ms: float | None = Field(default=None, ge=0)
