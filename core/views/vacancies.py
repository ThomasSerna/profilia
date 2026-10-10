import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from pydantic import ValidationError

from agents.career.cache import get_career_data
from agents.profile.schemas import ProfileData
from agents.vacancies.graph import run_vacancy_agent
from agents.vacancies.schemas import Preferences
from core.models import Profile

logger = logging.getLogger(__name__)


@login_required
@require_POST
def match_vacancies(request):
    profile = Profile.objects.filter(user=request.user).first()
    if profile is None:
        return JsonResponse(
            {"success": False, "error": "Primero debes procesar tu hoja de vida."},
            status=404,
        )

    try:
        candidate = ProfileData.model_validate(profile.data)
    except ValidationError:
        return JsonResponse(
            {"success": False, "error": "No pudimos recuperar tu hoja de vida. Vuelve a cargarla para continuar."},
            status=409,
        )

    try:
        preferences = Preferences.model_validate({
            "modality": (request.POST.get("modality") or "any").strip(),
            "city": (request.POST.get("city") or "").strip() or None,
            "salary_min": (request.POST.get("salary_min") or "").strip() or None,
        })
    except ValidationError:
        return JsonResponse(
            {"success": False, "error": "Revisa tus preferencias: modalidad, ciudad o salario no válidos."},
            status=400,
        )

    try:
        saved = get_career_data(profile)
        result = run_vacancy_agent(
            candidate, preferences, saved["clarifications"], saved["role_names"], saved["skill_results"],
        )
    except Exception:
        logger.exception("Error inesperado en el agente de vacantes")
        return JsonResponse(
            {"success": False, "error": "No pudimos calcular tus coincidencias. Intenta de nuevo."},
            status=500,
        )

    return JsonResponse({
        "success": True,
        "count": len(result["matches"]),
        "matches": [match.model_dump() for match in result["matches"]],
        "skipped": result["skipped"],
    })


@login_required
def vacancies_page(request):
    profile = Profile.objects.filter(user=request.user).first()
    if profile is None or not profile.raw_text.strip():
        return redirect("home")
    return render(request, "pages/vacancies.html")
