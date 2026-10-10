import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from pydantic import ValidationError

from agents.career.cache import StaleProfileError, get_profile_revision, get_profile_state
from agents.profile.schemas import ProfileData
from core.forms import (
    EducationFormSet, ExperienceFormSet, FORMSET_ERRORS, LanguageFormSet,
    PersonalInformationForm, SkillFormSet,
)
from core.models import Profile
from core.profile_updates import update_profile

logger = logging.getLogger(__name__)

COLLECTIONS = (
    ("skills", "Habilidades", "Incluye habilidades técnicas y personales relevantes para tu trabajo.",
     "Añadir habilidad", SkillFormSet),
    ("experience", "Experiencia", "Describe tu experiencia laboral, proyectos o trabajo voluntario.",
     "Añadir experiencia", ExperienceFormSet),
    ("education", "Educación", "Añade tus estudios y formación, incluso si aún están en curso.",
     "Añadir educación", EducationFormSet),
    ("languages", "Idiomas", "Indica los idiomas que conoces y su nivel si deseas precisarlo.",
     "Añadir idioma", LanguageFormSet),
)


def set_field_accessibility(form):
    for field in form.visible_fields():
        described_by = []
        if field.help_text:
            described_by.append(f"{field.auto_id}-help")
        if field.errors:
            described_by.append(f"{field.auto_id}-errors")
            field.field.widget.attrs["aria-invalid"] = "true"
        if described_by:
            field.field.widget.attrs["aria-describedby"] = " ".join(described_by)


@login_required
@require_http_methods(["GET", "POST"])
def edit_profile(request):
    profile = Profile.objects.filter(user=request.user).first()
    revision = get_profile_revision(profile) if profile else ""
    try:
        initial = ProfileData.model_validate(profile.data if profile else {}).model_dump()
    except ValidationError:
        # Keep the saved record intact; only a successful validated save can replace it.
        initial = ProfileData().model_dump()

    if profile is None:
        initial.update(name=request.user.full_name, email=request.user.email)
    bound = request.POST if request.method == "POST" else None
    personal_form = PersonalInformationForm(bound, initial=initial)
    sections = []
    for key, title, help_text, add_label, factory in COLLECTIONS:
        values = initial[key]
        if key in ("skills", "languages"):
            values = [{"value": value} for value in values]
        elif key == "experience":
            values = [{**item, "technologies": "\n".join(item["technologies"])} for item in values]
        source = ("Revisado por ti" if profile and key in profile.manual_fields else
                  "Extraído de tu CV" if profile and profile.document_hash and values else "Información por completar")
        formset = factory(bound, initial=values, prefix=key, error_messages=FORMSET_ERRORS)
        empty_form = formset.empty_form
        set_field_accessibility(empty_form)
        sections.append({"key": key, "title": title, "help": help_text, "add_label": add_label,
                         "source": source, "formset": formset, "empty_form": empty_form,
                         "entry_label": {"skills": "Habilidad", "experience": "Experiencia",
                                         "education": "Formación", "languages": "Idioma"}[key]})

    error = ""
    status = 200
    conflict = False
    if request.method == "POST":
        valid = personal_form.is_valid()
        for section in sections:
            valid = section["formset"].is_valid() and valid
        if not valid:
            status = 400
            error = "Revisa los campos indicados. Tus cambios todavía no se han guardado."
        elif request.POST.get("profile_revision") != revision:
            status, conflict = 409, True
            error = "Tu perfil cambió en otra pestaña. Conservamos lo que escribiste; revisa el perfil actualizado antes de volver a guardar."
        else:
            data = {key: value or None for key, value in personal_form.cleaned_data.items()}
            for section in sections:
                values = []
                for form in section["formset"].forms:
                    item = {key: value for key, value in form.cleaned_data.items() if key != "DELETE"}
                    if form.cleaned_data.get("DELETE") or not any(item.values()):
                        continue
                    values.append(item["value"] if section["key"] in ("skills", "languages") else
                                  {key: value if isinstance(value, list) else value or None for key, value in item.items()})
                data[section["key"]] = values
            data = ProfileData.model_validate(data).model_dump()
            previous_data = initial if profile else ProfileData().model_dump()
            changed = {key for key in data if data[key] != previous_data[key]}
            protected = sorted(set(profile.manual_fields if profile else []) | changed)
            try:
                profile = update_profile(profile or Profile(user=request.user), revision, data,
                                         manual_fields=protected)
                state = get_profile_state(profile)
                messages.success(request, "Tu perfil se actualizó." if changed else "Tu perfil está guardado.")
                if "application/json" in request.headers.get("Accept", ""):
                    return JsonResponse({"success": True, "redirect_url": reverse("edit_profile"), **state})
                return redirect("edit_profile")
            except (StaleProfileError, IntegrityError):
                status, conflict = 409, True
                error = "Tu perfil cambió mientras guardabas. Conservamos lo que escribiste; revisa el perfil actualizado antes de volver a guardar."
            except Exception:
                logger.exception("No se pudo guardar el perfil editado")
                status = 500
                error = "No pudimos guardar tu perfil. Conservamos tus cambios para que puedas volver a intentarlo."

    forms = [personal_form]
    for section in sections:
        forms.extend(section["formset"].forms)
    for form in forms:
        set_field_accessibility(form)

    if status != 200 and "application/json" in request.headers.get("Accept", ""):
        field_errors = {form[field].html_name: list(errors) for form in forms
                        for field, errors in form.errors.items() if field != "__all__"}
        non_field_errors = [str(message) for form in forms for message in form.non_field_errors()]
        non_field_errors.extend(str(message) for section in sections
                                for message in section["formset"].non_form_errors())
        return JsonResponse({"success": False, "error": error, "field_errors": field_errors,
                             "non_field_errors": non_field_errors}, status=status)

    state = get_profile_state(profile)
    return render(request, "pages/profile_edit.html", {
        "page_title": "Editar perfil", "personal_form": personal_form, "sections": sections,
        "profile_revision": request.POST.get("profile_revision", "") if bound is not None else revision,
        "profile_exists": profile is not None, "profile_ready": state["profile_ready"],
        "needs_reassessment": state["needs_reassessment"], "has_errors": status != 200,
        "has_selected_roles": bool(state["role_names"]),
        "save_error": error, "conflict": conflict,
    }, status=status)
