import hashlib
import json

from pydantic import ValidationError

from .schemas import RoleAssessment
from .summary import add_assessment_summary
from .assessment import SKILL_ALIASES
from .roles import get_role_by_name
from .schemas import KEV_EVALUATOR_VERSION
from django.conf import settings


def build_assessment_key(profile, roles) -> str:
    payload = {
        "profile_id": profile.pk,
        "profile": profile.data,
        "document_hash": profile.document_hash,
        "raw_text": profile.raw_text,
        "roles": [
            role.model_dump()
            for role in sorted(roles, key=lambda role: role.name)
        ],
        "evaluator": KEV_EVALUATOR_VERSION,
        "checkpoint": settings.KEV_CHECKPOINT,
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

    try:
        assessments = [
            add_assessment_summary(
                RoleAssessment.model_validate(item)
            ).model_dump()
            for item in saved["assessments"]
        ]

    except (KeyError, TypeError, ValidationError):
        return None

    return {
        **saved,
        "assessments": assessments,
    }