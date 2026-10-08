from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from agents.career.cache import get_profile_state
from agents.career.roles import ROLE_CATALOG
from core.models import Profile


@login_required
def home(request):
    profile = Profile.objects.filter(
        user=request.user
    ).first()

    saved_state = get_profile_state(profile)

    return render(
        request,
        "pages/home.html",
        {
            "roles": ROLE_CATALOG,
            "saved_state": saved_state,
        },
    )
