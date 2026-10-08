from .schemas import RoleAssessment


def add_assessment_summary(assessment: RoleAssessment) -> RoleAssessment:
    parts = []

    for category, label in [
        ("required", "Obligatorias"),
        ("preferred", "Deseables"),
    ]:
        requirements = [
            item
            for item in assessment.requirements
            if item.category == category
        ]

        if not requirements:
            continue

        compatible = sum(
            item.status == "cumple"
            for item in requirements
        )

        contradicted = sum(
            item.status == "incumple"
            for item in requirements
        )

        unknown = (
            len(requirements)
            - compatible
            - contradicted
        )

        parts.append(
            f"{label}: {compatible} compatibles según Kev, "
            f"{contradicted} posibles contradicciones "
            f"y {unknown} sin evidencia suficiente."
        )

    parts.append(
        "Resultado provisional: revisa la evidencia y las "
        "probabilidades de cada habilidad."
    )

    return assessment.model_copy(
        update={"summary": " ".join(parts)}
    )