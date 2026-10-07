from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from agents.career.roles import ROLE_CATALOG

@login_required
def home(request):
    return render(
        request,
        "pages/home.html",
        {
            "roles": ROLE_CATALOG
        }
    )