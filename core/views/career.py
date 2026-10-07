from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from pydantic import ValidationError

from agents.career.roles import get_role_by_name
from agents.career.assessment import assess_role
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

    assessments = [
        assess_role(profile_data, role).model_dump()
        for role in roles
    ]

    return JsonResponse(
        {
            "success": True,
            "stage": "skill_matching_completed",
            "profile": profile.data,
            "roles": [role.model_dump() for role in roles],
            "assessments": assessments,
        }
    )