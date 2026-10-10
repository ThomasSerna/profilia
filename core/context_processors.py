from agents.profile.schemas import has_professional_information
from core.models import Profile

PROFILE_STEP_PERCENT = 25


def sidebar_state(request):
    """Estado que necesita la barra lateral en todas las páginas."""
    completed = False
    if request.user.is_authenticated:
        profile = Profile.objects.filter(user=request.user).only("data").first()
        completed = bool(profile and has_professional_information(profile.data))

    resolver = getattr(request, "resolver_match", None)
    return {
        "profile_completed": completed,
        "current_url_name": getattr(resolver, "url_name", "") if resolver else "",
        "flow_progress": PROFILE_STEP_PERCENT if completed else 0,
    }
