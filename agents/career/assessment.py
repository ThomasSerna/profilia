import unicodedata

from agents.profile.schemas import ProfileData
from .schemas import (
    RoleProfile,
    SkillEvidence,
    RequirementMatch,
    RoleAssessment,
)


SKILL_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "springboot": "spring boot",
    "spring-boot": "spring boot",
    "rest api": "rest apis",
    "api rest": "rest apis",
    "apis rest": "rest apis",
    "python3": "python",
    "python 3": "python",
}


def normalize_skill(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(
        character
        for character in text
        if not unicodedata.combining(character)
    )
    text = " ".join(text.casefold().split())

    return SKILL_ALIASES.get(text, text)


def collect_skill_evidence(profile: ProfileData) -> dict[str, list[SkillEvidence]]:
    items = [
        (value, f"skills[{index}]")
        for index, value in enumerate(profile.skills)
    ]

    for experience_index, experience in enumerate(profile.experience):
        for technology_index, value in enumerate(experience.technologies):
            source = (
                f"experience[{experience_index}]"
                f".technologies[{technology_index}]"
            )
            items.append((value, source))

    evidence = {}

    for value, source in items:
        key = normalize_skill(value)

        if not key:
            continue

        evidence.setdefault(key, []).append(
            SkillEvidence(value=value, source=source)
        )

    return evidence


def assess_role(profile: ProfileData, role: RoleProfile) -> RoleAssessment:
    evidence = collect_skill_evidence(profile)
    requirements = []

    groups = [
        ("required", role.required_skills),
        ("preferred", role.preferred_skills),
    ]

    for category, skills in groups:
        for skill in skills:
            matches = evidence.get(normalize_skill(skill), [])

            requirements.append(
                RequirementMatch(
                    skill=skill,
                    category=category,
                    status=(
                        "evidencia_en_perfil"
                        if matches
                        else "sin_evidencia"
                    ),
                    evidence=matches,
                )
            )

    return RoleAssessment(
        role_name=role.name,
        requirements=requirements,
    )