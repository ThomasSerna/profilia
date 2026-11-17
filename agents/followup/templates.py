"""Plantilla determinista de próximos pasos y recordatorios (respaldo cuando el LLM falla)."""

import re
from datetime import datetime, timedelta

from .schemas import MAX_FOCUS_SKILLS, FollowupPlanDraft, PlannedReminder, TrackedApplication

# Días sugeridos para volver a consultar una postulación sin respuesta (solo fija la fecha del
# recordatorio; el estado lo cambia únicamente el usuario).
FOLLOW_UP_AFTER_DAYS = 7

_UNSAFE = re.compile(r"@|https?://|www\.", re.IGNORECASE)


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def days_since(submitted_at: datetime, now: datetime) -> int:
    return max((now - submitted_at).days, 0)


def focus_skills(application: TrackedApplication) -> list[str]:
    return list(dict.fromkeys(application.missing_required))[:MAX_FOCUS_SKILLS]


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " y " + items[-1]


def _due(base: datetime, days: int, now: datetime):
    return max((base + timedelta(days=days)).date(), now.date())


def template_plan(application: TrackedApplication, now: datetime) -> tuple[str, list[PlannedReminder]]:
    status = application.status
    focus = focus_skills(application)
    matched = application.matched_skills[:3]
    warning = application.warnings[0] if application.warnings else ""
    title, company = application.title, application.company

    if status == "postulada":
        return (
            f"Espera la respuesta de {company}; cuando tengas novedades, mueve la tarjeta a su nueva etapa.",
            [PlannedReminder(
                key="postulada:revisar-estado",
                title=f"Revisar el estado de {title}",
                detail=f"Si aún no tienes respuesta de {company}, revisa tu correo o el portal de la vacante.",
                due_date=_due(application.submitted_at, FOLLOW_UP_AFTER_DAYS, now),
            )],
        )

    if status == "en_revision":
        reminders = []
        if focus:
            reminders.append(PlannedReminder(
                key="en_revision:reforzar",
                title=f"Reforzar {_join(focus)}",
                detail=warning or "Son requisitos de la vacante que aún no aparecen en tu perfil.",
                due_date=_due(now, 1, now),
            ))
        reminders.append(PlannedReminder(
            key="en_revision:novedades",
            title=f"Consultar novedades de {company}",
            detail="Si te citan a entrevista o te descartan, mueve la tarjeta para actualizar tu plan.",
            due_date=_due(now, FOLLOW_UP_AFTER_DAYS, now),
        ))
        step = (f"Mientras {company} revisa tu postulación, repasa {_join(focus)}."
                if focus else f"Mientras {company} revisa tu postulación, prepara ejemplos de tus proyectos.")
        return step, reminders

    if status == "entrevista":
        topics = focus or matched
        reminders = [PlannedReminder(
            key="entrevista:repasar",
            title=f"Repasar temas técnicos: {_join(topics)}" if topics else "Repasar los requisitos técnicos de la vacante",
            detail=warning or "Prepárate para preguntas técnicas sobre la vacante.",
            due_date=_due(now, 1, now),
        )]
        if matched:
            reminders.append(PlannedReminder(
                key="entrevista:ejemplos",
                title=f"Preparar ejemplos concretos con {_join(matched)}",
                detail="Cuenta qué hiciste, cómo lo hiciste y qué resultado obtuviste.",
                due_date=_due(now, 2, now),
            ))
        reminders.append(PlannedReminder(
            key="entrevista:preguntas",
            title=f"Preparar preguntas para {company}",
            detail="Pregunta por el equipo, las responsabilidades y los siguientes pasos del proceso.",
            due_date=_due(now, 2, now),
        ))
        step = (f"Prepara tu entrevista con {company}: repasa {_join(topics)}."
                if topics else f"Prepara tu entrevista con {company} repasando la descripción de la vacante.")
        return step, reminders

    return "Este proceso terminó. Revisa nuevas vacantes en el Agente de Vacantes.", []


def is_plan_valid(draft: FollowupPlanDraft) -> bool:
    texts = [draft.next_step] + [item.title for item in draft.reminders] + [item.detail for item in draft.reminders]
    if any(_UNSAFE.search(text) for text in texts):
        return False
    return len({item.title.lower() for item in draft.reminders}) == len(draft.reminders)


def draft_to_reminders(application: TrackedApplication, draft: FollowupPlanDraft,
                       now: datetime) -> list[PlannedReminder]:
    return [
        PlannedReminder(
            key=f"{application.status}:llm-{index}",
            title=item.title,
            detail=item.detail,
            due_date=_due(now, item.days_from_now, now),
        )
        for index, item in enumerate(draft.reminders, start=1)
    ]
