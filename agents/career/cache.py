import hashlib
import json

from .assessment import SKILL_ALIASES
from .roles import get_role_by_name
from .schemas import EVALUATOR_VERSION


def build_assessment_key(profile, roles) -> str:
    payload = {
        "profile_id": profile.pk,
        "profile": profile.data,
        "roles": [
            role.model_dump()
            for role in sorted(roles, key=lambda role: role.name)
        ],
        "evaluator": EVALUATOR_VERSION,
        "aliases": SKILL_ALIASES,
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def get_saved_career_data(profile):
    if profile is None or not profile.career_data:
        return None

    saved = profile.career_data

    roles = [
        get_role_by_name(name)
        for name in saved.get("role_names", [])
    ]

    if not roles or any(role is None for role in roles):
        return None

    if saved.get("key") != build_assessment_key(profile, roles):
        return None

    return saved