from typing import Literal

from pydantic import BaseModel, Field, model_validator

APPLICATION_MODEL = "openai/gpt-oss-120b"
LETTER_VERSION = "application_letter_v1"
SCREENING_VERSION = "application_screening_v1"
CHANNEL = "Magneto 365 (simulado)"
MAX_SCREENING_SKILLS = 6
MAX_LETTER_SKILLS = 6


class CoverLetterDraft(BaseModel):
    """Cuerpo de la carta que devuelve el LLM (sin saludo ni firma)."""

    text: str = Field(min_length=1, max_length=1800)

    @model_validator(mode="after")
    def validate_nonempty_text(self):
        self.text = self.text.strip()
        if not self.text:
            raise ValueError("La carta no puede estar vacía.")
        return self


class ScreeningAnswer(BaseModel):
    """Respuesta a una pregunta de filtro, siempre respaldada por el perfil o las preferencias."""

    question: str
    answer: str
    status: Literal["cumple", "sin_evidencia", "informativa"]
    source: Literal["perfil", "aclaracion", "inferida", "preferencias", "ninguna"]


class ApplicationPackage(BaseModel):
    vacancy_id: str
    title: str
    company: str
    score: int = Field(ge=0, le=100)
    cover_letter: str
    letter_source: Literal["groq", "template"]
    screening: list[ScreeningAnswer] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    status: Literal["postulada"] = "postulada"
    channel: str = CHANNEL
    submitted_at: str
    audit: dict = Field(default_factory=dict)
