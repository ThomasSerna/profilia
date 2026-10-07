from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from agents.career.cache import get_saved_career_data
from agents.career.roles import ROLE_CATALOG
from core.models import Profile


@login_required
def home(request):
    profile = Profile.objects.filter(
        user=request.user
    ).first()

    saved = get_saved_career_data(profile)

    saved_state = {
        "profile": profile.data if profile else None,
        "role_names": saved["role_names"] if saved else [],
        "assessments": saved["assessments"] if saved else [],
    }

    return render(
        request,
        "pages/home.html",
        {
            "roles": ROLE_CATALOG,
            "saved_state": saved_state,
        },
    )