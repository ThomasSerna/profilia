from typing import Literal

from pydantic import BaseModel, Field


class RoleProfile(BaseModel):
    name: str
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_areas: list[str] = Field(default_factory=list)


class SkillEvidence(BaseModel):
    value: str
    source: str


class RequirementMatch(BaseModel):
    skill: str
    category: Literal["required", "preferred"]
    status: Literal["evidencia_en_perfil", "sin_evidencia"]
    evidence: list[SkillEvidence] = Field(default_factory=list)


class RoleAssessment(BaseModel):
    role_name: str
    evaluator: str = "skill_matching_v1"
    requirements: list[RequirementMatch] = Field(default_factory=list)