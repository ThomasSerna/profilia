import copy
import hashlib
import json
import uuid

from django.conf import settings
from django.utils import timezone
from pydantic import ValidationError

from .assessment import SKILL_ALIASES, normalize_skill, role_skills
from .kev_assessment import build_role_assessment
from .llm import build_recommendation_key
from .roles import get_role_by_name
from .schemas import KEV_EVALUATOR_VERSION, KevChoiceAnswer, RoleAssessment


class StaleProfileError(ValueError):
    pass


def fingerprint(value) -> str:
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def profile_hash(profile) -> str:
    return fingerprint({"id": profile.pk, "data": profile.data,
                        "document": profile.document_hash, "text": fingerprint(profile.raw_text)})


def build_skill_key(profile) -> str:
    return fingerprint({"profile": profile_hash(profile), "evaluator": KEV_EVALUATOR_VERSION,
                        "checkpoint": settings.KEV_CHECKPOINT, "aliases": SKILL_ALIASES})


def get_career_data(profile):
    saved = copy.deepcopy(profile.career_data)
    if not isinstance(saved, dict) or saved.get("schema_version") != 2 or saved.get("profile_hash") != profile_hash(profile):
        saved = {"schema_version": 2, "profile_hash": profile_hash(profile),
                 "clarifications": {}, "role_names": [], "inference_runs": []}
    for field in ("clarifications", "skill_results", "assessments"):
        if not isinstance(saved.get(field), dict):
            saved[field] = {}
    if not isinstance(saved.get("role_names"), list):
        saved["role_names"] = []
    if not isinstance(saved.get("inference_runs"), list):
        saved["inference_runs"] = []
    if saved.get("skill_key") != build_skill_key(profile):
        saved.update(skill_key=build_skill_key(profile), skill_results={}, assessments={})
    try:
        saved["skill_results"] = {
            skill: KevChoiceAnswer.model_validate(answer).model_dump()
            for skill, answer in saved["skill_results"].items()
        }
    except ValidationError:
        saved["skill_results"] = {}
        saved["assessments"] = {}
    return saved


def get_profile_revision(profile) -> str:
    saved = get_career_data(profile)
    return fingerprint({"profile": profile_hash(profile), "clarifications": saved["clarifications"]})


def get_cached_assessments(saved):
    assessments = {}
    for name, item in saved["assessments"].items():
        try:
            assessment = RoleAssessment.model_validate(item)
            if assessment.role_name == name:
                assessments[name] = assessment
        except (TypeError, ValidationError):
            continue
    return assessments


def get_saved_career_data(profile):
    if profile is None:
        return None
    from agents.profile.schemas import ProfileData

    saved = get_career_data(profile)
    try:
        profile_data = ProfileData.model_validate(profile.data)
    except ValidationError:
        return None
    cached = get_cached_assessments(saved)
    assessments = []
    names = []
    for name in saved["role_names"]:
        role = get_role_by_name(name) if isinstance(name, str) else None
        if role is None:
            continue
        names.append(role.name)
        if any(normalize_skill(skill) not in saved["skill_results"]
               and normalize_skill(skill) not in saved["clarifications"]
               for skill in role_skills(role)):
            continue
        assessment = build_role_assessment(profile_data, role, saved["skill_results"], saved["clarifications"])
        key = build_recommendation_key(profile_data, role, assessment, saved["clarifications"])
        previous = cached.get(role.name)
        if previous and previous.recommendation_key == key:
            assessment = assessment.model_copy(update={
                "recommendation": previous.recommendation,
                "recommendation_status": previous.recommendation_status,
                "recommendation_source": previous.recommendation_source,
                "recommendation_key": previous.recommendation_key,
            })
        if assessment.group == "medium" and assessment.recommendation_status == "not_requested":
            assessment = assessment.model_copy(update={"recommendation_status": "pending"})
        assessments.append(assessment.model_dump())
    return {**saved, "role_names": names, "assessments": assessments}


def pending_questions(assessments, clarifications):
    from .roles import ROLE_CATALOG

    labels = {normalize_skill(skill): skill for role in ROLE_CATALOG for skill in role_skills(role)}
    questions = {}
    for assessment in assessments:
        if assessment["group"] != "pending":
            continue
        for label in assessment["unknown_skills"]:
            skill = normalize_skill(label)
            answer = clarifications.get(skill, {})
            question = questions.setdefault(skill, {"skill": skill, "label": labels.get(skill, label), "roles": [],
                                                    "answer": answer.get("answer", ""),
                                                    "detail": answer.get("detail", "")})
            if assessment["role_name"] not in question["roles"]:
                question["roles"].append(assessment["role_name"])
    return list(questions.values())


def answered_questions(role_names, clarifications):
    active_skills = {}
    for name in role_names:
        role = get_role_by_name(name)
        if role is None:
            continue
        for label in role_skills(role):
            skill = active_skills.setdefault(normalize_skill(label), {"label": label, "roles": []})
            if role.name not in skill["roles"]:
                skill["roles"].append(role.name)
    # The chat replays answers in the order they were saved, which is the insertion order of clarifications.
    # shortcut: relies on JSON key order kept by SQLite; store an explicit answer order before moving to PostgreSQL jsonb.
    return [
        {"skill": skill, "label": active_skills[skill]["label"], "roles": active_skills[skill]["roles"],
         "answer": answer.get("answer", ""), "detail": answer.get("detail", "")}
        for skill, answer in clarifications.items() if skill in active_skills
    ]


def get_profile_state(profile):
    if profile is None:
        return {"profile": None, "profile_revision": "", "role_names": [],
                "assessments": [], "pending_questions": [], "answered_questions": []}
    saved = get_saved_career_data(profile)
    assessments = saved["assessments"] if saved else []
    names = saved["role_names"] if saved else []
    clarifications = saved["clarifications"] if saved else {}
    return {"profile": profile.data, "profile_revision": get_profile_revision(profile),
            "role_names": names, "assessments": assessments,
            "pending_questions": pending_questions(assessments, clarifications),
            "answered_questions": answered_questions(names, clarifications)}


def persist_career_data(profile, expected_revision, *, skill_results=None, assessments=None,
                        inference_runs=None, role_names=None, clarifications=None):
    from core.models import Profile

    # SQLite needs compare-and-swap because select_for_update does not lock rows.
    for _ in range(3):
        current = Profile.objects.get(pk=profile.pk, user_id=profile.user_id)
        if get_profile_revision(current) != expected_revision:
            raise StaleProfileError("El perfil cambió. Recarga la página antes de continuar.")
        saved = get_career_data(current)
        if skill_results is not None:
            saved["skill_results"].update(skill_results)
        if assessments is not None:
            for assessment in assessments:
                previous = saved["assessments"].get(assessment.role_name, {})
                if (previous.get("recommendation_key") == assessment.recommendation_key
                        and previous.get("recommendation_status") == "ready"
                        and assessment.recommendation_status != "ready"):
                    continue
                saved["assessments"][assessment.role_name] = assessment.model_dump()
        if inference_runs:
            saved["inference_runs"].extend({"id": uuid.uuid4().hex, **run} for run in inference_runs)
        if role_names is not None:
            saved["role_names"] = role_names
        if clarifications is not None:
            saved["clarifications"].update(clarifications)
        updated = Profile.objects.filter(pk=current.pk, user_id=current.user_id,
                                         data=current.data, raw_text=current.raw_text,
                                         document_hash=current.document_hash,
                                         career_data=current.career_data).update(
            career_data=saved, updated_at=timezone.now())
        if updated:
            current.career_data = saved
            return current
    raise StaleProfileError("Los resultados cambiaron. Recarga la página antes de continuar.")
