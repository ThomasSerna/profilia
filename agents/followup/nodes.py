from .llm import generate_followup_plan
from .schemas import ACTIVE_STATUSES, STATUS_LABELS, FollowupPlan, NotificationDraft
from .state import FollowupState
from .templates import _plural, days_since, draft_to_reminders, is_plan_valid, template_plan


def _event(level: str, message: str, vacancy_id: str | None = None) -> dict:
    return {"level": level, "message": message, "vacancy_id": vacancy_id}


def build_notification(application_id: int, vacancy_id: str, title: str, company: str,
                       from_status: str, to_status: str, reason: str,
                       change_id: int | None = None) -> NotificationDraft:
    """Notificación del evento ESTADO CAMBIADO: siempre indica la vacante y el nuevo estado."""
    message = (f"Tu postulación a {title} en {company} pasó de {STATUS_LABELS[from_status]} "
               f"a {STATUS_LABELS[to_status]}. {reason}")
    return NotificationDraft(
        change_id=change_id,
        application_id=application_id,
        vacancy_id=vacancy_id,
        from_status=from_status,
        to_status=to_status,
        title=f"{title}: {STATUS_LABELS[to_status]}"[:160],
        message=message[:400],
    )


def monitor_node(state: FollowupState):
    applications = state["applications"]
    events = [_event("agent", "[AGENTE] Iniciando Agente de Seguimiento con LangGraph Agent...")]
    if applications:
        events.append(_event(
            "system", f"[SISTEMA] Monitoreando {_plural(len(applications), 'postulación enviada', 'postulaciones enviadas')}."))
    else:
        events.append(_event("warning", "[AVISO] No hay postulaciones enviadas para seguir."))
    return {"events": events}


def review_status_node(state: FollowupState):
    """Consolida el estado actual. El agente no decide estados: solo el usuario los cambia."""
    events = list(state["events"])
    changes = {}
    for change in state["changes"]:
        changes.setdefault(change.application_id, []).append(change)

    for application in state["applications"]:
        days = days_since(application.submitted_at, state["now"])
        events.append(_event(
            "step", f"[1/3] Revisando estado de: {application.title} · {STATUS_LABELS[application.status]} "
                    f"(enviada hace {_plural(days, 'día')})...", application.vacancy_id))
        for change in changes.get(application.application_id, []):
            events.append(_event(
                "success", f"[1/3] Cambio registrado: {STATUS_LABELS[change.from_status]} → "
                           f"{STATUS_LABELS[change.to_status]} · {application.title}", application.vacancy_id))
    return {"events": events}


def plan_reminders_node(state: FollowupState):
    events = list(state["events"])
    runs = list(state["inference_runs"])
    plans = []
    now = state["now"]

    for application in state["applications"]:
        if application.plan_status == application.status:
            events.append(_event(
                "system", f"[SISTEMA] Recordatorios al día, sin duplicados · {application.title}",
                application.vacancy_id))
            continue

        events.append(_event(
            "step", f"[2/3] Generando recordatorios y próximo paso para: {application.title}...",
            application.vacancy_id))
        next_step, reminders = template_plan(application, now)
        source = "template"
        if application.status in ACTIVE_STATUSES:
            draft, run = generate_followup_plan(application, now, state["profile"])
            if draft is not None and is_plan_valid(draft):
                next_step, reminders, source = draft.next_step, draft_to_reminders(application, draft, now), "groq"
            elif draft is not None:
                run = {**run, "status": "fallback", "error": "El plan generado no pasó la validación."}
            runs.append(run)

        plans.append(FollowupPlan(
            application_id=application.application_id,
            vacancy_id=application.vacancy_id,
            status=application.status,
            next_step=next_step,
            source=source,
            reminders=reminders,
        ))

    return {"plans": plans, "events": events, "inference_runs": runs}


def notify_node(state: FollowupState):
    events = list(state["events"])
    by_id = {application.application_id: application for application in state["applications"]}
    notifications = []

    for change in state["changes"]:
        application = by_id.get(change.application_id)
        if application is None:
            continue
        notifications.append(build_notification(
            application.application_id, application.vacancy_id, application.title, application.company,
            change.from_status, change.to_status, change.reason, change.change_id,
        ))
        events.append(_event(
            "success", f"[3/3] Notificación creada: {application.title} ahora está en "
                       f"{STATUS_LABELS[change.to_status]}.", application.vacancy_id))

    if not state["applications"]:
        return {"notifications": notifications, "events": events}
    if notifications:
        events.append(_event(
            "final", f"[ÉXITO] Seguimiento actualizado: "
                     f"{_plural(len(notifications), 'notificación creada', 'notificaciones creadas')}."))
    else:
        events.append(_event("final", "[ÉXITO] Seguimiento al día: tus recordatorios y próximos pasos están listos."))
    return {"notifications": notifications, "events": events}
