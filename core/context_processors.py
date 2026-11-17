from agents.profile.schemas import has_professional_information
from core.models import Application, Profile

PROFILE_STEP_PERCENT = 25
VACANCIES_STEP_PERCENT = 50
APPLICATIONS_STEP_PERCENT = 75

PAGE_ICONS = {
    "home": "fa-id-card",
    "edit_profile": "fa-id-card",
    "vacancies": "fa-briefcase",
    "applications": "fa-paper-plane",
    "traceability": "fa-list-check",
}


def sidebar_state(request):
    """Estado que necesita la barra lateral en todas las páginas."""
    completed = False
    has_applications = False
    applications_completed = False

    if request.user.is_authenticated:
        profile = Profile.objects.filter(user=request.user).only("data").first()
        completed = bool(profile and has_professional_information(profile.data))
        if completed:
            statuses = list(
                Application.objects.filter(user=request.user).values_list("status", flat=True)
            )
            has_applications = bool(statuses)
            applications_completed = bool(
                statuses and any(s == Application.APPLIED for s in statuses)
                and not any(s == Application.SELECTED for s in statuses)
            )

    applications_unlocked = bool(completed and has_applications)

    if not completed:
        flow_progress = 0
        flow_stage_label = "Mi perfil"
    elif not applications_unlocked:
        flow_progress = PROFILE_STEP_PERCENT
        flow_stage_label = "Vacantes"
    elif not applications_completed:
        flow_progress = VACANCIES_STEP_PERCENT
        flow_stage_label = "Postulaciones"
    else:
        flow_progress = APPLICATIONS_STEP_PERCENT
        flow_stage_label = "Seguimiento"

    resolver = getattr(request, "resolver_match", None)
    current_url_name = getattr(resolver, "url_name", "") if resolver else ""
    return {
        "profile_completed": completed,
        "current_url_name": current_url_name,
        "current_page_icon": PAGE_ICONS.get(current_url_name, "fa-id-card"),
        "flow_progress": flow_progress,
        "flow_stage_label": flow_stage_label,
        "applications_unlocked": applications_unlocked,
        "applications_completed": applications_completed,
    }
