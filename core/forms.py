from django import forms
from django.forms import BaseFormSet, formset_factory


class ProfileEditorForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.error_messages.update({
                "required": "Completa este campo.",
                "max_length": "Este texto es demasiado extenso. Usa como máximo %(limit_value)s caracteres.",
            })


class PersonalInformationForm(ProfileEditorForm):
    name = forms.CharField(label="Nombre completo", max_length=150, required=False,
                           widget=forms.TextInput(attrs={"autocomplete": "name"}))
    email = forms.EmailField(label="Correo de contacto", required=False,
                             error_messages={"invalid": "Introduce un correo electrónico válido."},
                             help_text="Este correo no cambia el que usas para iniciar sesión.",
                             widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    phone = forms.CharField(label="Teléfono", max_length=40, required=False,
                            widget=forms.TextInput(attrs={"type": "tel", "autocomplete": "tel"}))


class SkillForm(ProfileEditorForm):
    value = forms.CharField(label="Habilidad", max_length=120, required=False)


class LanguageForm(ProfileEditorForm):
    value = forms.CharField(label="Idioma y nivel, si lo conoces", max_length=120, required=False)


class ExperienceForm(ProfileEditorForm):
    company = forms.CharField(label="Empresa u organización", max_length=250, required=False)
    role = forms.CharField(label="Cargo", max_length=250, required=False)
    start_date = forms.CharField(label="Fecha de inicio", max_length=100, required=False,
                                 help_text="Por ejemplo: enero de 2024.")
    end_date = forms.CharField(label="Fecha de finalización", max_length=100, required=False,
                               help_text="Puedes escribir Actualidad si continúas allí.")
    description = forms.CharField(label="Responsabilidades y logros", max_length=5000, required=False,
                                   widget=forms.Textarea(attrs={"rows": 3}))
    technologies = forms.CharField(label="Tecnologías y herramientas", max_length=10000, required=False,
                                    help_text="Escribe una tecnología o herramienta por línea.",
                                    widget=forms.Textarea(attrs={"rows": 2}))

    def clean_technologies(self):
        values = []
        seen = set()
        for line in self.cleaned_data["technologies"].splitlines():
            value = line.strip()
            if not value:
                continue
            if len(value) > 120:
                raise forms.ValidationError("Usa como máximo 120 caracteres por tecnología o herramienta.")
            if value.casefold() not in seen:
                values.append(value)
                seen.add(value.casefold())
        if len(values) > 100:
            raise forms.ValidationError("Incluye como máximo 100 tecnologías o herramientas por experiencia.")
        return values

    def clean(self):
        data = super().clean()
        if (data.get("start_date") or data.get("end_date")) and not any(
            data.get(key) for key in ("company", "role", "description", "technologies")
        ):
            raise forms.ValidationError("Describe esta experiencia o elimínala si no deseas incluirla.")
        return data


class EducationForm(ProfileEditorForm):
    institution = forms.CharField(label="Institución", max_length=250, required=False)
    degree = forms.CharField(label="Título o formación", max_length=250, required=False)
    field = forms.CharField(label="Área de estudio", max_length=250, required=False)
    start_date = forms.CharField(label="Fecha de inicio", max_length=100, required=False)
    end_date = forms.CharField(label="Fecha de finalización", max_length=100, required=False,
                               help_text="Puedes escribir En curso si aún estás estudiando.")

    def clean(self):
        data = super().clean()
        if (data.get("start_date") or data.get("end_date")) and not any(
            data.get(key) for key in ("institution", "degree", "field")
        ):
            raise forms.ValidationError("Describe esta formación o elimínala si no deseas incluirla.")
        return data


class ProfileCollectionFormSet(BaseFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        seen = set()
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
            value = form.cleaned_data.get("value", "")
            if value and value.casefold() in seen:
                form.add_error("value", "Ya incluiste esta información. Conserva una sola entrada.")
            seen.add(value.casefold())


FORMSET_ERRORS = {
    "missing_management_form": "No pudimos leer esta sección. Recarga la página antes de continuar.",
    "too_many_forms": "Incluye como máximo 100 entradas por sección.",
}

SkillFormSet = formset_factory(SkillForm, formset=ProfileCollectionFormSet, extra=0,
                               can_delete=True, max_num=100, absolute_max=100, validate_max=True)
LanguageFormSet = formset_factory(LanguageForm, formset=ProfileCollectionFormSet, extra=0,
                                  can_delete=True, max_num=100, absolute_max=100, validate_max=True)
ExperienceFormSet = formset_factory(ExperienceForm, extra=0, can_delete=True,
                                    max_num=100, absolute_max=100, validate_max=True)
EducationFormSet = formset_factory(EducationForm, extra=0, can_delete=True,
                                   max_num=100, absolute_max=100, validate_max=True)
