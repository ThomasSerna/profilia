from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from pydantic import ValidationError

from agents.career.cache import (
    build_assessment_key,
    get_saved_career_data,
)

from agents.career.graph import career_graph
from agents.career.kev import KevError
from agents.career.schemas import RoleAssessment
from agents.career.cache import build_assessment_key
from agents.career.roles import get_role_by_name
from agents.career.kev import KevError
from agents.career.kev_assessment import assess_role_with_kev
from agents.profile.schemas import ProfileData
from core.models import Profile


@login_required
@require_POST
def assess_career(request):
    role_names = request.POST.getlist("roles")

    roles = []

    for name in role_names:
        role = get_role_by_name(name.strip())

        if role is None:
            return JsonResponse(
                {
                    "success": False,
                    "error": f"El cargo '{name}' no existe en el catálogo.",
                },
                status=400,
            )

        if role not in roles:
            roles.append(role)

    if not 1 <= len(roles) <= 3:
        return JsonResponse(
            {
                "success": False,
                "error": "Debes seleccionar entre 1 y 3 cargos diferentes.",
            },
            status=400,
        )

    try:
        profile = Profile.objects.get(user=request.user)

    except Profile.DoesNotExist:
        return JsonResponse(
            {
                "success": False,
                "error": "Primero debes procesar tu hoja de vida.",
            },
            status=404,
        )

    try:
        profile_data = ProfileData.model_validate(profile.data)

    except ValidationError:
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "El perfil guardado tiene un formato incompatible. "
                    "Vuelve a procesar tu hoja de vida."
                ),
            },
            status=409,
        )

    if not profile.raw_text.strip():
        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Vuelve a procesar tu CV "
                    "para guardar su texto."
                ),
            },
            status=409,
        )

    key = build_assessment_key(profile, roles)

    saved = get_saved_career_data(profile)

    reused = (
            saved is not None
            and saved["key"] == key
    )

    cached_assessments = [
        RoleAssessment.model_validate(item)
        for item in saved["assessments"]
    ] if reused else []

    try:
        result = career_graph.invoke({
            "profile": profile_data,
            "raw_text": profile.raw_text,
            "roles": roles,
            "assessments": cached_assessments,
            "reused": reused,
        })

    except KevError as error:
        return JsonResponse(
            {
                "success": False,
                "error": str(error),
            },
            status=502,
        )

    assessments = [
        assessment.model_dump()
        for assessment in result["assessments"]
    ]

    if not reused:
        profile.career_data = {
            "key": key,
            "role_names": [
                role.name for role in roles
            ],
            "assessments": assessments,
        }

        profile.save(
            update_fields=["career_data"]
        )

    return JsonResponse(
        {
            "success": True,
            "stage": "career_graph_completed",
            "profile": profile.data,
            "roles": [role.model_dump() for role in roles],
            "assessments": assessments,
            "reused": reused,
        }
    )