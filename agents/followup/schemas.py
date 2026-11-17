from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

FOLLOWUP_MODEL = "openai/gpt-oss-120b"
PLAN_VERSION = "followup_plan_v1"
MAX_REMINDERS = 3
MAX_REMINDER_DAYS = 30
MAX_FOCUS_SKILLS = 4

Status = Literal["postulada", "en_revision", "entrevista", "descartada"]

STATUS_LABELS = {
    "postulada": "Postulada",
    "en_revision": "En revisión",
    "entrevista": "Entrevista",
    "descartada": "Descartada",
}
ACTIVE_STATUSES = ("postulada", "en_revision", "entrevista")


class TrackedApplication(BaseModel):
    """Instantánea de una postulación enviada. El agente no accede a la base de datos."""

    application_id: int
    vacancy_id: str
    title: str
    company: str
    score: int = Field(ge=0, le=100)
    status: Status
    submitted_at: datetime
    matched_skills: list[str] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    plan_status: str = ""


class StatusChange(BaseModel):
    """Evento ESTADO CAMBIADO: un cambio que registró el usuario y que el agente debe notificar."""

    change_id: int
    application_id: int
    from_status: Status
    to_status: Status
    reason: str


class ReminderDraft(BaseModel):
    """Recordatorio que devuelve el LLM; la fecha se calcula a partir de days_from_now."""

    title: str = Field(min_length=3, max_length=120)
    detail: str = Field(default="", max_length=300)
    days_from_now: int = Field(ge=0, le=MAX_REMINDER_DAYS)

    @model_validator(mode="after")
    def strip_text(self):
        self.title = self.title.strip()
        self.detail = self.detail.strip()
        if len(self.title) < 3:
            raise ValueError("El recordatorio necesita un título.")
        return self


class FollowupPlanDraft(BaseModel):
    """Salida estructurada del LLM: próximo paso concreto y recordatorios."""

    next_step: str = Field(min_length=10, max_length=300)
    reminders: list[ReminderDraft] = Field(min_length=1, max_length=MAX_REMINDERS)

    @model_validator(mode="after")
    def strip_text(self):
        self.next_step = self.next_step.strip()
        if len(self.next_step) < 10:
            raise ValueError("El próximo paso no puede estar vacío.")
        return self


class PlannedReminder(BaseModel):
    key: str
    title: str
    detail: str = ""
    due_date: date


class FollowupPlan(BaseModel):
    application_id: int
    vacancy_id: str
    status: Status
    next_step: str
    source: Literal["groq", "template"]
    reminders: list[PlannedReminder] = Field(default_factory=list)


class NotificationDraft(BaseModel):
    change_id: int | None = None
    application_id: int
    vacancy_id: str
    from_status: Status
    to_status: Status
    title: str
    message: str
