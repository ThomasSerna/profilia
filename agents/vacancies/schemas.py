from typing import Literal

from pydantic import BaseModel, Field, model_validator

Modality = Literal["remoto", "hibrido", "presencial"]
PreferredModality = Literal["any", "remoto", "hibrido", "presencial"]


class Preferences(BaseModel):
    """Preferencias del candidato que el agente usa para puntuar vacantes."""

    modality: PreferredModality = "any"
    city: str | None = Field(default=None, max_length=80)
    salary_min: int | None = Field(default=None, ge=0, le=100_000_000)


class Vacancy(BaseModel):
    """Vacante ya normalizada, lista para hacer matching."""

    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=160)
    company: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=80)
    modality: Modality
    city: str | None = None
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    required_skills: list[str] = Field(min_length=1)
    nice_skills: list[str] = Field(default_factory=list)
    source: str = "dataset"
    description: str = ""

    @model_validator(mode="after")
    def check_salary_range(self):
        if self.salary_min is not None and self.salary_max is not None:
            if self.salary_max < self.salary_min:
                raise ValueError("salary_max no puede ser menor que salary_min")
        return self


class VacancyMatch(BaseModel):
    """Resultado del scoring de una vacante para un candidato."""

    vacancy_id: str
    title: str
    company: str
    role: str
    modality: Modality
    city: str | None
    salary_min: int | None
    salary_max: int | None
    source: str
    description: str
    score: int = Field(ge=0, le=100)
    matched_skills: list[str]
    missing_required: list[str]
    missing_nice: list[str]
    reasons: list[str]
    meets_preferences: bool
