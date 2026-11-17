from agents.profile.schemas import has_professional_information
from core.models import Application, Profile

PROFILE_STEP_PERCENT = 25

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
    if request.user.is_authenticated:
        profile = Profile.objects.filter(user=request.user).only("data").first()
        completed = bool(profile and has_professional_information(profile.data))

    applications_unlocked = bool(
        completed and Application.objects.filter(user=request.user).exists()
    )

    resolver = getattr(request, "resolver_match", None)
    current_url_name = getattr(resolver, "url_name", "") if resolver else ""
    return {
        "profile_completed": completed,
        "current_url_name": current_url_name,
        "current_page_icon": PAGE_ICONS.get(current_url_name, "fa-id-card"),
        "flow_progress": PROFILE_STEP_PERCENT if completed else 0,
        "applications_unlocked": applications_unlocked,
    }
