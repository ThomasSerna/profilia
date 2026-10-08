import json
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from pydantic import ValidationError

from agents.career.cache import (
    StaleProfileError, get_cached_assessments, get_career_data,
    get_profile_revision, get_profile_state, persist_career_data,
)
from agents.career.graph import career_graph
from agents.career.kev import KevError
from agents.career.roles import ROLE_CATALOG, get_role_by_name
from agents.profile.schemas import ProfileData
from core.models import Profile

logger = logging.getLogger(__name__)


class CareerRequestError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def selected_roles(request):
    roles = []
    for name in request.POST.getlist("roles"):
        role = get_role_by_name(name.strip())
        if role is None:
            raise CareerRequestError("Selecciona cargos válidos del catálogo.")
        if role not in roles:
            roles.append(role)
    if not 1 <= len(roles) <= 3:
        raise CareerRequestError("Debes seleccionar entre 1 y 3 cargos diferentes.")
    return roles


def load_profile(request):
    if not request.user.is_authenticated:
        raise CareerRequestError("Vuelve a iniciar sesión para continuar.", 401)
    profile = Profile.objects.filter(user=request.user).first()
    if profile is None:
        raise CareerRequestError("Primero debes procesar tu hoja de vida.", 404)
    try:
        ProfileData.model_validate(profile.data)
    except ValidationError as error:
        raise CareerRequestError("No pudimos recuperar tu hoja de vida. Vuelve a cargarla para continuar.", 409) from error
    if not profile.raw_text.strip():
        raise CareerRequestError("Vuelve a cargar tu hoja de vida para que podamos revisarla.", 409)
    revision = request.POST.get("profile_revision")
    if not revision:
        raise CareerRequestError("Recarga la página para continuar con tu orientación.")
    if revision != get_profile_revision(profile):
        raise StaleProfileError("El perfil cambió. Recarga la página antes de continuar.")
    return profile


def read_clarifications(request, state):
    raw = request.POST.get("clarifications", "")
    if len(raw) > 60000:
        raise CareerRequestError("Tu respuesta es demasiado extensa. Describe tu experiencia de forma breve.")
    try:
        answers = json.loads(raw)
    except (TypeError, ValueError) as error:
        raise CareerRequestError("No pudimos leer tu respuesta. Elige una opción e inténtalo de nuevo.") from error
    allowed = {question["skill"] for question in state["pending_questions"]}
    if not isinstance(answers, dict) or not answers or not answers.keys() <= allowed:
        raise CareerRequestError("Responde únicamente a las habilidades pendientes de tus cargos.")
    clean = {}
    for skill, item in answers.items():
        if not isinstance(item, dict) or set(item) - {"answer", "detail"}:
            raise CareerRequestError("No pudimos guardar tu respuesta. Revísala e inténtalo de nuevo.")
        answer = item.get("answer")
        detail = item.get("detail", "")
        if answer not in ("yes", "no", "unknown") or not isinstance(detail, str) or len(detail) > 1000:
            raise CareerRequestError("Elige una respuesta válida y usa como máximo 1000 caracteres.")
        detail = detail.strip()
        if answer == "yes" and not detail:
            raise CareerRequestError("Cuéntanos dónde y cómo conoces o has utilizado esta habilidad.")
        clean[skill] = {"answer": answer, "detail": detail}
    return clean


def run_operation(request, operation):
    profile = None
    answers_saved = False
    try:
        profile = load_profile(request)
        revision = get_profile_revision(profile)
        saved = get_career_data(profile)
        retry = operation == "retry"
        if operation == "explore":
            roles = ROLE_CATALOG
        elif retry:
            role = get_role_by_name(request.POST.get("role", "").strip())
            state = get_profile_state(profile)
            assessment = next((item for item in state["assessments"] if role and item["role_name"] == role.name), None)
            if not assessment:
                raise CareerRequestError("Selecciona y evalúa este cargo antes de solicitar su recomendación.", 409)
            if assessment["group"] != "medium" or assessment["recommendation_status"] != "pending":
                raise CareerRequestError("Esta recomendación ya está disponible o todavía necesitamos completar tu información.")
            roles = [role]
        else:
            roles = selected_roles(request)
            if operation == "clarify":
                state = get_profile_state(profile)
                if {role.name for role in roles} != set(state["role_names"]):
                    raise CareerRequestError("Completa información para la selección actualmente evaluada.", 409)
                answers = read_clarifications(request, state)
                profile = persist_career_data(profile, revision, clarifications=answers)
                answers_saved = True
                revision = get_profile_revision(profile)
                saved = get_career_data(profile)

        result = career_graph.invoke({
            "profile": ProfileData.model_validate(profile.data),
            "raw_text": profile.raw_text,
            "roles": roles,
            "skill_results": saved["skill_results"],
            "clarifications": saved["clarifications"],
            "cached_assessments": get_cached_assessments(saved),
            "generate_recommendations": operation != "explore",
            "retry_recommendation": retry,
        })
        profile = persist_career_data(
            profile, revision,
            skill_results=result["skill_results"],
            assessments=result["assessments"],
            inference_runs=result.get("inference_runs", []),
            role_names=[role.name for role in roles] if operation in ("assess", "clarify") else None,
        )
        response = {"success": True, "stage": "career_graph_completed", **get_profile_state(profile),
                    "reused": not result.get("inference_runs"),
                    "roles": [role.model_dump() for role in roles]}
        if operation == "explore":
            ranked = sorted(enumerate(result["assessments"]),
                            key=lambda item: (-item[1].score_min, -item[1].required_coverage, item[0]))
            response["suggestions"] = [
                {field: getattr(assessment, field) for field in (
                    "role_name", "score_min", "score_max", "group", "strengths", "unknowns", "required_coverage")}
                for _, assessment in ranked if assessment.strengths
            ][:3]
        return JsonResponse(response)
    except CareerRequestError as error:
        return JsonResponse({"success": False, "error": str(error)}, status=error.status)
    except (StaleProfileError, KevError) as error:
        if isinstance(error, StaleProfileError):
            message, status = str(error), 409
        else:
            logger.exception("No se pudo completar la operación de orientación %s", operation)
            message, status = "No pudimos completar tu orientación. Puedes volver a intentarlo.", 502
        response = {"success": False, "error": message}
        if answers_saved:
            profile.refresh_from_db()
            response.update(get_profile_state(profile))
            if isinstance(error, KevError):
                response["error"] = "Tu respuesta está guardada. No pudimos actualizar tu orientación; puedes volver a intentarlo."
        return JsonResponse(response, status=status)
    except Exception:
        logger.exception("Error inesperado en la operación de orientación %s", operation)
        response = {"success": False, "error": "No pudimos completar tu orientación. Puedes volver a intentarlo."}
        if answers_saved:
            profile.refresh_from_db()
            response.update(get_profile_state(profile))
            response["error"] = "Tu respuesta está guardada. No pudimos actualizar tu orientación; puedes volver a intentarlo."
        return JsonResponse(response, status=500)


@require_POST
def assess_career(request):
    return run_operation(request, "assess")


@require_POST
def explore_career(request):
    return run_operation(request, "explore")


@require_POST
def clarify_career(request):
    return run_operation(request, "clarify")


@require_POST
def retry_career_recommendation(request):
    return run_operation(request, "retry")
