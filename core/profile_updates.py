from django.db import transaction
from django.utils import timezone
from pydantic import ValidationError

from agents.career.cache import (
    StaleProfileError, build_skill_key, get_cached_assessments, get_career_data, get_profile_revision, profile_hash,
)
from agents.career.llm import build_recommendation_key
from agents.career.roles import get_role_by_name
from agents.profile.schemas import ProfileData, has_professional_information
from core.models import Profile


def update_profile(profile, expected_revision, data, *, manual_fields=None, raw_text=None, document_hash=None):
    candidate = ProfileData.model_validate(data)
    data = candidate.model_dump()
    if manual_fields is not None and not set(manual_fields) <= ProfileData.model_fields.keys():
        raise ValueError("Los campos manuales no pertenecen al perfil profesional.")
    if profile.pk is None:
        if expected_revision:
            raise StaleProfileError("El perfil cambió. Recarga la página antes de guardar.")
        with transaction.atomic():
            current, created = Profile.objects.get_or_create(user_id=profile.user_id)
            if not created:
                raise StaleProfileError("El perfil cambió. Recarga la página antes de guardar.")
            return update_profile(current, get_profile_revision(current), data, manual_fields=manual_fields,
                                  raw_text=raw_text, document_hash=document_hash)

    for _ in range(3):
        current = Profile.objects.get(pk=profile.pk, user_id=profile.user_id)
        if get_profile_revision(current) != expected_revision:
            raise StaleProfileError("El perfil cambió. Recarga la página antes de guardar.")
        previous = {field: getattr(current, field) for field in (
            "data", "manual_fields", "raw_text", "document_hash", "career_data",
        )}
        saved = get_career_data(current)
        previous_skill_key = build_skill_key(current)
        try:
            previous_data = ProfileData.model_validate(current.data).model_dump()
        except ValidationError:
            previous_data = ProfileData().model_dump()
        if manual_fields is None:
            protected = set(current.manual_fields)
            protected.update(field for field in data if data[field] != previous_data[field])
        else:
            protected = set(manual_fields)
        current.manual_fields = [field for field in ProfileData.model_fields if field in protected]
        current.data = data
        if raw_text is not None:
            current.raw_text = raw_text
        if document_hash is not None:
            current.document_hash = document_hash
        skill_key = build_skill_key(current)
        if skill_key != previous_skill_key:
            saved.update(clarifications={}, skill_results={}, assessments={},
                         needs_reassessment=has_professional_information(data))
        elif data != previous_data:
            # Contact redaction can change a key without changing professional information.
            for name, assessment in get_cached_assessments(saved).items():
                role = get_role_by_name(name)
                if role is not None:
                    saved["assessments"][name]["recommendation_key"] = build_recommendation_key(
                        candidate, role, assessment, saved["clarifications"],
                    )
        saved.update(profile_hash=profile_hash(current), skill_key=skill_key)
        updated = Profile.objects.filter(pk=current.pk, user_id=current.user_id, **previous).update(
            data=data, manual_fields=current.manual_fields, raw_text=current.raw_text,
            document_hash=current.document_hash, career_data=saved, updated_at=timezone.now(),
        )
        if updated:
            current.refresh_from_db()
            return current
    raise StaleProfileError("El perfil cambió. Recarga la página antes de guardar.")
