import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from pydantic import ValidationError

from agents.followup.graph import run_followup_agent
from agents.followup.nodes import build_notification
from agents.followup.schemas import STATUS_LABELS, StatusChange, TrackedApplication
from agents.profile.schemas import ProfileData, has_professional_information
from core.models import Application, ApplicationStatusChange, Notification, Profile, Reminder

logger = logging.getLogger(__name__)

MAX_NOTIFICATIONS = 20
MAX_HISTORY = 5


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _submitted(user):
    return Application.objects.filter(
        user=user, status__in=Application.SUBMITTED_STATUSES, submitted_at__isnull=False)


def _candidate(user) -> ProfileData:
    """Perfil solo para redactar datos de contacto antes de llamar al LLM."""
    profile = Profile.objects.filter(user=user).only("data").first()
    try:
        return ProfileData.model_validate(profile.data) if profile else ProfileData()
    except ValidationError:
        return ProfileData()


def _snapshot(application) -> TrackedApplication:
    audit = application.audit or {}
    return TrackedApplication(
        application_id=application.id,
        vacancy_id=application.vacancy_id,
        title=application.title,
        company=application.company,
        score=application.score,
        status=application.status,
        submitted_at=application.submitted_at,
        matched_skills=audit.get("matched_skills") or [],
        missing_required=audit.get("missing_required") or [],
        warnings=application.warnings or [],
        plan_status=application.next_step_status,
    )


def _record_change(application, from_status, to_status, reason):
    """Guarda el cambio que hizo el usuario en el historial (evento ESTADO CAMBIADO)."""
    change = ApplicationStatusChange.objects.create(
        application=application, from_status=from_status, to_status=to_status, reason=reason[:300],
        source=ApplicationStatusChange.USER)
    # Los recordatorios pendientes de otros estados dejan de aplicar.
    application.reminders.filter(status=Reminder.PENDING).exclude(key__startswith=f"{to_status}:").update(
        status=Reminder.DISMISSED)
    return change


def _save_notification(application, change_id, title, message):
    # OneToOne con el cambio de estado: el mismo cambio nunca se notifica dos veces.
    Notification.objects.get_or_create(
        status_change_id=change_id,
        defaults={"user": application.user, "application": application, "title": title, "message": message},
    )


def _save_plan(application, plan):
    application.next_step = plan.next_step
    application.next_step_source = plan.source
    application.next_step_status = plan.status
    application.save(update_fields=["next_step", "next_step_source", "next_step_status", "updated_at"])
    for item in plan.reminders:
        reminder = application.reminders.filter(key=item.key).first()
        if reminder is None:
            Reminder.objects.create(application=application, key=item.key, title=item.title[:160],
                                    detail=item.detail[:400], due_date=item.due_date, source=plan.source)
        elif reminder.status == Reminder.DISMISSED:
            reminder.title, reminder.detail = item.title[:160], item.detail[:400]
            reminder.due_date, reminder.source, reminder.status = item.due_date, plan.source, Reminder.PENDING
            reminder.save()


def _run_and_persist(user, applications, changes=()) -> dict:
    """Ejecuta el agente fuera de la transacción (puede llamar al LLM) y guarda solo lo que sigue vigente."""
    snapshots = [_snapshot(application) for application in applications]
    result = run_followup_agent(
        snapshots,
        [StatusChange(change_id=change.id, application_id=change.application_id, from_status=change.from_status,
                      to_status=change.to_status, reason=change.reason) for change in changes],
        _candidate(user),
    )
    expected = {snapshot.application_id: snapshot.status for snapshot in snapshots}

    with transaction.atomic():
        current = {app.id: app for app in Application.objects.select_for_update().filter(
            user=user, id__in=expected.keys())}

        for draft in result["notifications"]:
            if draft.change_id is not None and draft.application_id in current:
                _save_notification(current[draft.application_id], draft.change_id, draft.title, draft.message)

        for plan in result["plans"]:
            application = current.get(plan.application_id)
            # Si el usuario movió la tarjeta mientras el agente trabajaba, el plan ya no aplica.
            if application is not None and application.status == plan.status == expected[plan.application_id]:
                _save_plan(application, plan)

    return result


def _serialize_change(change) -> dict:
    return {
        "from_status": change.from_status,
        "to_status": change.to_status,
        "from_label": STATUS_LABELS.get(change.from_status, change.from_status),
        "to_label": STATUS_LABELS.get(change.to_status, change.to_status),
        "reason": change.reason,
        "source": change.source,
        "created_at": change.created_at.isoformat(),
    }


def serialize_tracked(application) -> dict:
    changes = list(application.status_changes.all())
    reminders = [reminder for reminder in application.reminders.all() if reminder.status != Reminder.DISMISSED]
    last = changes[-1] if changes else None
    return {
        "id": application.id,
        "vacancy_id": application.vacancy_id,
        "title": application.title,
        "company": application.company,
        "score": application.score,
        "status": application.status,
        "status_label": STATUS_LABELS[application.status],
        "submitted_at": application.submitted_at.isoformat(),
        "next_step": application.next_step if application.next_step_status == application.status else "",
        "next_step_source": application.next_step_source,
        "warnings": application.warnings or [],
        "reminders": [
            {
                "id": reminder.id,
                "title": reminder.title,
                "detail": reminder.detail,
                "due_date": reminder.due_date.isoformat(),
                "status": reminder.status,
                "source": reminder.source,
            }
            for reminder in reminders
        ],
        "last_activity": (
            _serialize_change(last) if last
            else {"to_label": "Postulada", "reason": "Postulación enviada.", "source": "agente",
                  "created_at": application.submitted_at.isoformat()}
        ),
        "history": [_serialize_change(change) for change in changes[-MAX_HISTORY:]],
    }


def board_payload(user) -> dict:
    applications = _submitted(user).prefetch_related("status_changes", "reminders")
    notifications = Notification.objects.filter(user=user).select_related("application")[:MAX_NOTIFICATIONS]
    unread = Notification.objects.filter(user=user, is_read=False).count()
    return {
        "applications": [serialize_tracked(application) for application in applications],
        "notifications": [
            {
                "id": notification.id,
                "title": notification.title,
                "message": notification.message,
                "is_read": notification.is_read,
                "created_at": notification.created_at.isoformat(),
                "vacancy_id": notification.application.vacancy_id,
            }
            for notification in notifications
        ],
        "unread_count": unread,
        "unread_label": _plural(unread, "notificación sin leer", "notificaciones sin leer"),
    }


def _ok(user, **extra) -> JsonResponse:
    return JsonResponse({"success": True, "board": board_payload(user), **extra})


@login_required
def followup_page(request):
    profile = Profile.objects.filter(user=request.user).first()
    if profile is None or not has_professional_information(profile.data):
        return redirect("home")
    if not _submitted(request.user).exists():
        return redirect("applications")
    return render(request, "pages/followup.html", {
        "page_title": "Seguimiento",
        "board": board_payload(request.user),
    })


@login_required
@require_POST
def run_followup(request):
    applications = list(_submitted(request.user))
    if not applications:
        return JsonResponse(
            {"success": False, "error": "Aún no tienes postulaciones enviadas para hacer seguimiento."}, status=409)
    try:
        result = _run_and_persist(request.user, applications)
    except Exception:
        logger.exception("Error inesperado en el agente de seguimiento")
        return JsonResponse(
            {"success": False, "error": "No pudimos actualizar el seguimiento. Intenta de nuevo."}, status=500)
    return _ok(request.user, events=result["events"])


@login_required
@require_POST
def move_application(request, application_id):
    application = get_object_or_404(_submitted(request.user), id=application_id)
    new_status = request.POST.get("status", "")
    if new_status not in Application.SUBMITTED_STATUSES:
        return JsonResponse({"success": False, "error": "Elige un estado válido."}, status=400)
    if new_status == application.status:
        return JsonResponse({"success": False, "error": "La postulación ya está en ese estado."}, status=400)

    with transaction.atomic():
        previous = application.status
        application.status = new_status
        application.save(update_fields=["status", "updated_at"])
        change = _record_change(application, previous, new_status,
                                f"Moviste la postulación a {STATUS_LABELS[new_status]}.")

    # ESTADO CAMBIADO: el agente notifica y actualiza el próximo paso y los recordatorios.
    events = []
    try:
        events = _run_and_persist(request.user, [application], [change])["events"]
    except Exception:
        logger.exception("No se pudo actualizar el seguimiento de %s", application.vacancy_id)
    if not Notification.objects.filter(status_change=change).exists():
        # Si el agente falla, el cambio igual se notifica.
        draft = build_notification(application.id, application.vacancy_id, application.title, application.company,
                                   previous, new_status, change.reason, change.id)
        _save_notification(application, change.id, draft.title, draft.message)
    return _ok(request.user, events=events)


@login_required
@require_POST
def complete_reminder(request, reminder_id):
    reminder = get_object_or_404(Reminder, id=reminder_id, application__user=request.user)
    if reminder.status == Reminder.PENDING:
        reminder.status = Reminder.DONE
        reminder.completed_at = timezone.now()
        reminder.save(update_fields=["status", "completed_at"])
    return _ok(request.user)


@login_required
@require_POST
def read_notification(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])
    return _ok(request.user)


@login_required
@require_POST
def read_all_notifications(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True, read_at=timezone.now())
    return _ok(request.user)
