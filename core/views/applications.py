import logging

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST
from pydantic import ValidationError

from agents.applications.catalog import load_vacancies_by_id
from agents.applications.graph import run_application_agent
from agents.applications.schemas import CHANNEL
from agents.career.cache import get_career_data, get_profile_revision
from agents.profile.schemas import ProfileData, has_professional_information
from core.models import Application, Profile
from core.views.vacancies import stored_preferences

logger = logging.getLogger(__name__)


def serialize_application(application) -> dict:
    return {
        "vacancy_id": application.vacancy_id,
        "title": application.title,
        "company": application.company,
        "score": application.score,
        "status": application.status,
        "cover_letter": application.cover_letter,
        "letter_source": application.letter_source,
        "screening": application.screening,
        "warnings": application.warnings,
        "channel": (application.audit or {}).get("channel", CHANNEL),
        "submitted_at": application.submitted_at.isoformat() if application.submitted_at else None,
    }


def _profile_error(profile):
    """Misma validación que el agente de vacantes. Devuelve (candidate, None) o (None, JsonResponse)."""
    if profile is None:
        return None, JsonResponse(
            {"success": False, "error": "Primero guarda tu información profesional o carga tu hoja de vida."},
            status=404,
        )
    try:
        candidate = ProfileData.model_validate(profile.data)
    except ValidationError:
        return None, JsonResponse(
            {"success": False, "error": "No pudimos recuperar tu perfil. Revisa tu información o vuelve a cargar tu hoja de vida."},
            status=409,
        )
    if not has_professional_information(candidate):
        return None, JsonResponse(
            {"success": False, "error": "Añade experiencia, educación, habilidades o idiomas a tu perfil para postular."},
            status=409,
        )
    return candidate, None


@login_required
@require_POST
def select_applications(request):
    profile = Profile.objects.filter(user=request.user).first()
    _, error = _profile_error(profile)
    if error:
        return error

    requested = list(dict.fromkeys(request.POST.getlist("vacancy_ids")))
    if not requested:
        return JsonResponse({"success": False, "error": "Selecciona al menos una vacante para postular."}, status=400)

    catalog = load_vacancies_by_id()
    if any(vacancy_id not in catalog for vacancy_id in requested):
        return JsonResponse(
            {"success": False, "error": "Alguna de las vacantes seleccionadas ya no está disponible."}, status=400)

    with transaction.atomic():
        Application.objects.filter(user=request.user, status=Application.SELECTED).exclude(
            vacancy_id__in=requested).delete()
        existing = set(Application.objects.filter(
            user=request.user, vacancy_id__in=requested).values_list("vacancy_id", flat=True))
        for vacancy_id in requested:
            if vacancy_id not in existing:
                vacancy = catalog[vacancy_id]
                Application.objects.create(
                    user=request.user, vacancy_id=vacancy_id, title=vacancy.title, company=vacancy.company)

    return JsonResponse({"success": True, "count": len(requested), "redirect_url": reverse("applications")})


@login_required
@require_POST
def run_applications(request):
    profile = Profile.objects.filter(user=request.user).first()
    candidate, error = _profile_error(profile)
    if error:
        return error

    pending = list(Application.objects.filter(user=request.user, status=Application.SELECTED))
    if not pending:
        return JsonResponse(
            {"success": False, "error": "Selecciona al menos una vacante en el Agente de Vacantes antes de postular."},
            status=409,
        )

    try:
        saved = get_career_data(profile)
        revision = get_profile_revision(profile)
        result = run_application_agent(
            candidate,
            stored_preferences(profile),
            saved["clarifications"],
            saved["role_names"],
            saved["skill_results"],
            [application.vacancy_id for application in pending],
            request.user.full_name,
        )
    except Exception:
        logger.exception("Error inesperado en el agente de postulación")
        return JsonResponse(
            {"success": False, "error": "No pudimos preparar tus postulaciones. Intenta de nuevo."}, status=500)

    packages = {package.vacancy_id: package for package in result["packages"]}
    runs = {run["vacancy_id"]: run for run in result["inference_runs"] if run.get("vacancy_id")}
    done = []

    with transaction.atomic():
        for application in pending:
            package = packages.get(application.vacancy_id)
            if package is None:
                # La vacante ya no existe en el dataset: se retira de la selección.
                application.delete()
                continue
            application.title = package.title
            application.company = package.company
            application.score = package.score
            application.status = Application.APPLIED
            application.cover_letter = package.cover_letter
            application.letter_source = package.letter_source
            application.screening = [answer.model_dump() for answer in package.screening]
            application.warnings = package.warnings
            application.audit = {**package.audit, "profile_revision": revision,
                                 "inference": runs.get(application.vacancy_id)}
            application.submitted_at = parse_datetime(package.submitted_at)
            application.save()
            done.append(application)

    return JsonResponse({
        "success": True,
        "count": len(done),
        "applications": [serialize_application(application) for application in done],
        "events": result["events"],
        "skipped": result["skipped"],
    })


@login_required
def applications_page(request):
    profile = Profile.objects.filter(user=request.user).first()
    if profile is None or not has_professional_information(profile.data):
        return redirect("home")
    applications = Application.objects.filter(user=request.user)
    return render(request, "pages/applications.html", {
        "page_title": "Postulaciones",
        "applications": [serialize_application(application) for application in applications],
    })
