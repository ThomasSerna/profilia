"""Scoring determinista de vacantes.

Cada vacante se puntúa con componentes ponderados. Si un componente no aplica
(por ejemplo, el candidato no dio preferencia de salario), no entra al cálculo,
y los pesos restantes se reescalan para sumar 100.
"""

from agents.career.schemas import MIN_KEV_CONFIDENCE
from agents.profile.schemas import ProfileData

from .normalize import fold_text, normalize_skill, skill_key
from .schemas import Preferences, Vacancy, VacancyMatch

REQUIRED_WEIGHT = 0.6
NICE_WEIGHT = 0.2
MODALITY_WEIGHT = 0.1
SALARY_WEIGHT = 0.2
LOCATION_WEIGHT = 0.1
ROLE_WEIGHT = 0.15

# Si el candidato cubre menos de la mitad de los requisitos obligatorios,
# ninguna otra señal puede hacer que la vacante quede en lo alto del ranking.
LOW_REQUIRED_COVERAGE = 0.5
LOW_COVERAGE_CAP = 49


def candidate_skills(profile: ProfileData) -> dict[str, str]:
    """Mapa clave -> nombre visible con todas las habilidades del candidato."""
    names = list(profile.skills)
    for experience in profile.experience:
        names.extend(experience.technologies)

    result: dict[str, str] = {}
    for name in names:
        key = skill_key(name)
        if key and key not in result:
            result[key] = normalize_skill(name)
    return result


def confirmed_skills(clarifications: dict | None) -> dict[str, str]:
    """Habilidades que el candidato confirmó como 'Sí' en la evaluación de carrera.

    Solo cuenta la respuesta "yes". "no" y "unknown" no suman habilidades.
    """
    result: dict[str, str] = {}
    for skill, item in (clarifications or {}).items():
        if isinstance(item, dict) and item.get("answer") == "yes":
            key = skill_key(skill)
            if key:
                result[key] = normalize_skill(skill)
    return result


def inferred_skills(skill_results: dict | None, clarifications: dict | None) -> dict[str, str]:
    """Habilidades que Kev dedujo del CV con confianza suficiente ("cumple").

    Igual que en la evaluación de carrera, una aclaración del usuario tiene prioridad:
    si el usuario respondió sobre una habilidad, la inferencia de Kev no cuenta.
    """
    answered = {skill_key(skill) for skill in (clarifications or {})}
    result: dict[str, str] = {}
    for skill, answer in (skill_results or {}).items():
        if not isinstance(answer, dict):
            continue
        key = skill_key(skill)
        if not key or key in answered:
            continue
        if answer.get("choice") == "cumple" and float(answer.get("confidence") or 0) >= MIN_KEV_CONFIDENCE:
            result[key] = normalize_skill(skill)
    return result


def _display(skills: list[str]) -> dict[str, str]:
    return {skill_key(skill): normalize_skill(skill) for skill in skills}


def score_vacancy(candidate: dict[str, str], vacancy: Vacancy, prefs: Preferences,
                  confirmed: dict[str, str] | None = None,
                  selected_roles: set[str] | None = None,
                  inferred: dict[str, str] | None = None) -> VacancyMatch:
    confirmed = confirmed or {}
    inferred = inferred or {}
    selected_roles = selected_roles or set()
    known = {**inferred, **candidate, **confirmed}
    required = _display(vacancy.required_skills)
    nice = _display(vacancy.nice_skills)
    reasons: list[str] = []
    meets = True

    matched_required = [key for key in required if key in known]
    missing_required = [key for key in required if key not in known]
    matched_nice = [key for key in nice if key in known]
    missing_nice = [key for key in nice if key not in known]
    confirmed_only = [
        required.get(key) or nice[key]
        for key in matched_required + matched_nice
        if key in confirmed and key not in candidate
    ]
    inferred_only = [
        required.get(key) or nice[key]
        for key in matched_required + matched_nice
        if key in inferred and key not in candidate and key not in confirmed
    ]

    required_coverage = len(matched_required) / len(required)
    components: list[tuple[float, float]] = [(REQUIRED_WEIGHT, required_coverage)]

    if nice:
        components.append((NICE_WEIGHT, len(matched_nice) / len(nice)))

    if prefs.modality != "any":
        same = vacancy.modality == prefs.modality
        components.append((MODALITY_WEIGHT, 1.0 if same else 0.0))
        if same:
            reasons.append("La modalidad coincide con tu preferencia.")
        else:
            reasons.append(f"La modalidad es {vacancy.modality}, y preferiste {prefs.modality}.")
            meets = False

    offered = vacancy.salary_max or vacancy.salary_min
    if prefs.salary_min and offered:
        components.append((SALARY_WEIGHT, min(1.0, offered / prefs.salary_min)))
        if offered >= prefs.salary_min:
            reasons.append("El salario ofrecido cumple tu aspiración.")
        else:
            reasons.append("El salario ofrecido está por debajo de tu aspiración.")
            meets = False

    if prefs.city and vacancy.modality != "remoto":
        same_city = vacancy.city is not None and fold_text(vacancy.city) == fold_text(prefs.city)
        components.append((LOCATION_WEIGHT, 1.0 if same_city else 0.0))
        if same_city:
            reasons.append(f"La vacante está en tu ciudad ({vacancy.city}).")
        else:
            reasons.append(f"La vacante está en {vacancy.city or 'una ubicación no publicada'}, no en {prefs.city}.")
            meets = False

    if selected_roles:
        same_role = fold_text(vacancy.role) in selected_roles
        components.append((ROLE_WEIGHT, 1.0 if same_role else 0.0))
        if same_role:
            reasons.append(f"Corresponde a un cargo que elegiste: {vacancy.role}.")
        else:
            reasons.append(f"No corresponde a los cargos que elegiste ({vacancy.role}).")

    total_weight = sum(weight for weight, _ in components)
    score = sum(weight * value for weight, value in components) / total_weight * 100

    if matched_required:
        reasons.insert(0, f"Cubres {len(matched_required)} de {len(required)} requisitos obligatorios.")
    if missing_required:
        reasons.insert(1, "Te faltan requisitos obligatorios: " + ", ".join(required[key] for key in missing_required) + ".")
    if confirmed_only:
        reasons.append("Incluye habilidades que confirmaste en tu evaluación de carrera: "
                       + ", ".join(dict.fromkeys(confirmed_only)) + ".")
    if inferred_only:
        reasons.append("Kev dedujo de tu CV estas habilidades: "
                       + ", ".join(dict.fromkeys(inferred_only)) + ".")
    if required_coverage < LOW_REQUIRED_COVERAGE:
        score = min(score, LOW_COVERAGE_CAP)
        reasons.append("Cubres menos de la mitad de los requisitos obligatorios.")

    return VacancyMatch(
        vacancy_id=vacancy.id,
        title=vacancy.title,
        company=vacancy.company,
        role=vacancy.role,
        modality=vacancy.modality,
        city=vacancy.city,
        salary_min=vacancy.salary_min,
        salary_max=vacancy.salary_max,
        source=vacancy.source,
        description=vacancy.description,
        score=round(score),
        matched_skills=[required[k] for k in matched_required] + [nice[k] for k in matched_nice],
        missing_required=[required[k] for k in missing_required],
        missing_nice=[nice[k] for k in missing_nice],
        reasons=reasons,
        meets_preferences=meets,
    )


def rank_matches(matches: list[VacancyMatch]) -> list[VacancyMatch]:
    return sorted(matches, key=lambda match: (-match.score, match.title))
