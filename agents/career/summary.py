from fractions import Fraction

from .assessment import normalize_skill
from .schemas import RoleAssessment


def add_assessment_summary(assessment: RoleAssessment) -> RoleAssessment:
    required = [item for item in assessment.requirements if item.category == "required"]
    preferred = [item for item in assessment.requirements if item.category == "preferred"]
    if not required and not preferred:
        raise ValueError("El cargo no tiene requisitos de habilidades.")

    minimum = Fraction(0)
    maximum = Fraction(0)
    for requirements, weight in (
        (required, 80 if preferred else 100),
        (preferred, 20 if required else 100),
    ):
        if not requirements:
            continue
        minimum += Fraction(weight * sum(item.status == "cumple" for item in requirements), len(requirements))
        maximum += Fraction(weight * sum(item.status != "incumple" for item in requirements), len(requirements))

    mandatory_failure = any(item.status == "incumple" for item in required)
    mandatory_complete = all(item.status == "cumple" for item in required)
    high_possible = not mandatory_failure and maximum >= 70

    if mandatory_complete and minimum >= 70:
        group = "high"
    elif maximum < 40:
        group = "low"
    elif minimum >= 40 and not high_possible:
        group = "medium"
    else:
        group = "pending"

    strengths = [item.skill for item in assessment.requirements if item.status == "cumple"]
    gaps = [item.skill for item in assessment.requirements if item.status == "incumple"]
    unknowns = [item.skill for item in assessment.requirements if item.status == "sin_evidencia"]
    unknown_skills = []
    if group == "pending":
        for requirement in assessment.requirements:
            if requirement.status != "sin_evidencia":
                continue
            for item in requirement.alternatives or [requirement]:
                if item.status == "sin_evidencia":
                    key = normalize_skill(item.skill)
                    if key not in unknown_skills:
                        unknown_skills.append(key)

    if group == "high":
        summary = (
            f"Encontramos una base sólida en tu perfil para {assessment.role_name}. "
            f"Estas son tus fortalezas para este cargo: {', '.join(strengths)}. "
            "Profilia te recomienda destacar proyectos y resultados que muestren esas habilidades "
            "en tu hoja de vida."
        )
    elif group == "low":
        summary = f"Profilia te recomienda preparar algunas habilidades para acercarte a {assessment.role_name}. "
        if gaps:
            summary += f"Prioriza desarrollar: {', '.join(gaps)}. "
        if strengths:
            summary += f"Puedes apoyarte en: {', '.join(strengths)}. "
        if unknowns:
            summary += f"Necesitamos más información sobre: {', '.join(unknowns)}; esto no significa que no las conozcas."
    elif group == "medium":
        summary = f"Tu perfil tiene una base para aspirar a {assessment.role_name}. "
        if strengths:
            summary += f"Encontramos estas fortalezas en tu perfil: {', '.join(strengths)}. "
        if gaps:
            summary += f"Habilidades por desarrollar: {', '.join(gaps)}. "
        if unknowns:
            summary += f"Necesitamos más información sobre: {', '.join(unknowns)}. "
    else:
        # The chat shows this text only after the user has answered every question, so it closes the conversation.
        summary = (
            f"Todavía no tenemos información suficiente para darte una orientación completa hacia {assessment.role_name}. "
            f"No encontramos datos suficientes sobre {', '.join(unknowns)} en tu hoja de vida ni en tus respuestas, "
            "y eso no significa que no tengas la capacidad. "
            "Si has utilizado alguna de estas habilidades, Profilia te recomienda incluirla en tu hoja de vida "
            "con un ejemplo concreto; si todavía no la conoces, puede ser un buen punto de partida para aprender."
        )

    declared = [item.skill for item in assessment.requirements if item.source == "user_clarification"
                or any(alternative.source == "user_clarification" for alternative in item.alternatives)]
    if declared:
        summary += f" También tomamos en cuenta lo que nos contaste sobre: {', '.join(declared)}."
    return assessment.model_copy(update={
        "score_min": float(minimum),
        "score_max": float(maximum),
        "required_coverage": (
            sum(item.status == "cumple" for item in required) / len(required) if required else 1
        ),
        "group": group,
        "strengths": strengths,
        "gaps": gaps,
        "unknowns": unknowns,
        "unknown_skills": unknown_skills,
        "summary": summary.strip(),
        "recommendation": None,
        "recommendation_status": "ready" if group in ("high", "low") else "not_requested",
        "recommendation_source": "template" if group in ("high", "low", "pending") else "none",
    })
