from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from pydantic import ValidationError

from agents.applications.catalog import load_vacancies_by_id
from agents.career.cache import get_career_data, get_profile_state
from agents.profile.schemas import ProfileData, has_professional_information
from agents.vacancies.graph import run_vacancy_agent
from agents.vacancies.schemas import Preferences
from core.models import Application, Profile
from core.views.vacancies import stored_preferences

MODALITY_LABELS = {
    "any": "Cualquier modalidad",
    "remoto": "Remoto",
    "hibrido": "Híbrido",
    "presencial": "Presencial",
}

GROUP_LABELS = {
    "high": "Alta coincidencia con los requisitos del cargo",
    "medium": "Coincidencia parcial con oportunidades de mejora",
    "low": "Aún requiere fortalecer requisitos clave",
    "pending": "Con información pendiente por confirmar",
}

SCREENING_STATUS_LABELS = {
    "cumple": "Con respaldo en tu perfil",
    "sin_evidencia": "Sin información suficiente en tu perfil",
    "informativa": "Según tus preferencias declaradas",
}


def _candidate_from_profile(profile) -> ProfileData | None:
    if profile is None or not isinstance(profile.data, dict):
        return None
    try:
        candidate = ProfileData.model_validate(profile.data)
    except ValidationError:
        return None
    return candidate if has_professional_information(candidate) else None


def _build_profile_stage(profile, candidate: ProfileData | None, state: dict) -> dict:
    has_profile = candidate is not None
    has_cv = bool(state.get("has_cv"))
    manual_fields = state.get("manual_fields") or []
    assessments = state.get("assessments") or []
    answered = state.get("answered_questions") or []
    pending = state.get("pending_questions") or []
    role_names = state.get("role_names") or []

    skills = list(candidate.skills) if candidate else []
    experiences = len(candidate.experience) if candidate else 0
    educations = len(candidate.education) if candidate else 0
    languages = list(candidate.languages) if candidate else []

    if not has_profile:
        source_status = "pending"
        source_what = (
            "Profilia está lista para leer tu hoja de vida en PDF o registrar los datos "
            "que completes manualmente en tu perfil."
        )
        source_items = [
            "Puedes subir un archivo PDF o usar el editor manual de perfil.",
            "Tus datos de contacto, experiencia y estudios se mantendrán bajo tu control.",
        ]
    elif has_cv and manual_fields:
        source_status = "completed"
        source_what = (
            "Profilia combinó la lectura de tu hoja de vida en PDF con las secciones "
            "que editaste personalmente para conservar tus cambios."
        )
        source_items = [
            "Documento PDF leído y procesado en tu cuenta.",
            f"Secciones ajustadas por ti: {len(manual_fields)}.",
        ]
    elif has_cv:
        source_status = "completed"
        source_what = "Profilia leyó tu hoja de vida en PDF para identificar tu trayectoria profesional."
        source_items = ["Hoja de vida en PDF cargada en tu cuenta."]
    else:
        source_status = "completed"
        source_what = "Profilia registró la información profesional que ingresaste manualmente en el editor."
        source_items = ["Perfil creado y mantenido directamente por ti."]

    structure_status = "completed" if has_profile else "pending"
    structure_items = []
    if has_profile:
        if skills:
            structure_items.append(f"Habilidades registradas: {', '.join(skills[:6])}.")
        if experiences:
            structure_items.append(f"Experiencias laborales o proyectos: {experiences}.")
        if educations:
            structure_items.append(f"Registros de educación: {educations}.")
        if languages:
            structure_items.append(f"Idiomas: {', '.join(languages[:4])}.")
    if not structure_items:
        structure_items = ["Aún no hay habilidades, experiencia ni estudios guardados en tu perfil."]

    confirmed_yes = [item["label"] for item in answered if item.get("answer") == "yes"]
    confirmed_no = [item["label"] for item in answered if item.get("answer") in ("no", "unknown")]
    pending_labels = [item["label"] for item in pending]

    if answered or (assessments and not pending):
        gaps_status = "completed"
    elif pending or has_profile:
        gaps_status = "in_progress"
    else:
        gaps_status = "pending"

    gaps_items = []
    if confirmed_yes:
        gaps_items.append(f"Habilidades confirmadas por ti en la conversación: {', '.join(confirmed_yes[:5])}.")
    if confirmed_no:
        gaps_items.append(f"Habilidades marcadas por fortalecer: {', '.join(confirmed_no[:5])}.")
    if pending_labels:
        gaps_items.append(f"Información pendiente por conversar: {', '.join(pending_labels[:5])}.")
    if not gaps_items:
        gaps_items.append(
            "Cuando eliges cargos de interés, Profilia revisa qué requisitos aún no aparecen en tu hoja de vida "
            "para preguntarte antes de asumir que no los conoces."
        )

    roles_status = "completed" if assessments else ("in_progress" if has_profile else "pending")
    roles_items = []
    for item in assessments[:3]:
        group_label = GROUP_LABELS.get(item.get("group"), "Evaluación en curso")
        roles_items.append(f"{item['role_name']}: {group_label}.")
    if not roles_items:
        roles_items = [
            "Selecciona entre 1 y 3 cargos en Mi perfil para recibir orientación personalizada de Profilia."
        ]

    stage_status = "completed" if (has_profile and assessments and not pending) else (
        "in_progress" if has_profile else "pending"
    )

    return {
        "id": "profile",
        "step": 1,
        "title": "Perfil y orientación",
        "subtitle": "Estructura tu hoja de vida, detecta vacíos y orienta tus cargos",
        "icon": "fa-id-card",
        "status": stage_status,
        "status_label": (
            "Completado" if stage_status == "completed"
            else "En curso" if stage_status == "in_progress"
            else "Pendiente"
        ),
        "action_url": reverse("home"),
        "action_label": "Ir a Mi perfil",
        "summary": (
            "Profilia organiza tu experiencia y habilidades, distingue lo que aparece en tu hoja de vida "
            "de lo que nos cuentas directamente y evalúa qué tan cerca estás de los cargos que te interesan."
        ),
        "metrics": [
            {"label": "Habilidades en perfil", "value": str(len(skills))},
            {"label": "Cargos evaluados", "value": str(len(role_names))},
            {"label": "Aclaraciones hechas", "value": str(len(answered))},
        ],
        "nodes": [
            {
                "id": "profile-source",
                "step_label": "Paso 1.1",
                "title": "Recepción de datos",
                "caption": "Lectura de CV o edición manual",
                "icon": "fa-file-arrow-up",
                "status": source_status,
                "status_label": "Completado" if source_status == "completed" else "Pendiente",
                "badge": "PDF / Manual" if has_profile else "Sin datos",
                "live_action": "Recibiendo tu información profesional y respetando las secciones editadas a mano...",
                "what_did": source_what,
                "why_did": (
                    "Para ahorrarte tiempo al cargar tu hoja de vida sin perder nunca las correcciones "
                    "o adiciones que hagas manualmente."
                ),
                "items": source_items,
            },
            {
                "id": "profile-structure",
                "step_label": "Paso 1.2",
                "title": "Estructura del perfil",
                "caption": "Habilidades, estudios y experiencia",
                "icon": "fa-diagram-project",
                "status": structure_status,
                "status_label": "Completado" if structure_status == "completed" else "Pendiente",
                "badge": f"{len(skills)} hab. · {experiences} exp.",
                "live_action": "Organizando tus habilidades, estudios, experiencia e idiomas en secciones claras...",
                "what_did": (
                    f"Profilia identificó {len(skills)} habilidad(es), {experiences} experiencia(s) "
                    f"y {educations} registro(s) educativo(s) en tu perfil."
                    if has_profile else
                    "Profilia espera tu información profesional para estructurar tus fortalezas."
                ),
                "why_did": (
                    "Tener tu información separada por habilidades, experiencia y educación permite compararla "
                    "de forma justa con los requisitos de cada cargo."
                ),
                "items": structure_items,
            },
            {
                "id": "profile-gaps",
                "step_label": "Paso 1.3",
                "title": "Detección de vacíos",
                "caption": "Preguntas sobre lo que no figura en el CV",
                "icon": "fa-magnifying-glass-chart",
                "status": gaps_status,
                "status_label": (
                    "Completado" if gaps_status == "completed"
                    else "En curso" if gaps_status == "in_progress"
                    else "Pendiente"
                ),
                "badge": f"{len(answered)} aclaradas · {len(pending)} pend.",
                "live_action": "Revisando qué habilidades de tus cargos no aparecen aún en tu hoja de vida...",
                "what_did": (
                    f"Profilia detectó {len(answered) + len(pending)} habilidad(es) por confirmar para tus cargos: "
                    f"ya respondiste {len(answered)} y quedan {len(pending)} pendiente(s)."
                    if (answered or pending) else
                    "Profilia compara tu perfil con los cargos elegidos para identificar información pendiente."
                ),
                "why_did": (
                    "Que una herramienta no aparezca escrita en tu hoja de vida no significa que no la conozcas. "
                    "Por eso te preguntamos antes de dar una recomendación."
                ),
                "items": gaps_items,
            },
            {
                "id": "profile-guidance",
                "step_label": "Paso 1.4",
                "title": "Orientación profesional",
                "caption": "Fortalezas y plan por cargo",
                "icon": "fa-compass",
                "status": roles_status,
                "status_label": (
                    "Completado" if roles_status == "completed"
                    else "En curso" if roles_status == "in_progress"
                    else "Pendiente"
                ),
                "badge": f"{len(assessments)} cargo(s)",
                "live_action": "Preparando tus fortalezas, brechas y recomendaciones prácticas por cargo...",
                "what_did": (
                    f"Profilia evaluó tu afinidad con {len(assessments)} cargo(s) de interés y organizó "
                    "recomendaciones concretas según tus fortalezas y vacíos."
                    if assessments else
                    "Profilia preparará recomendaciones personalizadas en cuanto elijas entre 1 y 3 cargos."
                ),
                "why_did": (
                    "Para orientarte con honestidad sobre qué requisitos ya respaldas con tu perfil "
                    "y qué habilidades te conviene reforzar."
                ),
                "items": roles_items,
            },
        ],
        "edges": [
            {"from": "profile-source", "to": "profile-structure", "label": "Texto y secciones"},
            {"from": "profile-structure", "to": "profile-gaps", "label": "Habilidades detectadas"},
            {"from": "profile-gaps", "to": "profile-guidance", "label": "Evidencia + aclaraciones"},
        ],
    }


def _build_vacancies_stage(profile, candidate: ProfileData | None, saved_career: dict) -> dict:
    catalog = load_vacancies_by_id()
    total_catalog = len(catalog)
    preferences = stored_preferences(profile) if profile else Preferences()
    raw_prefs = (profile.preferences or {}) if profile else {}
    has_saved_prefs = bool(raw_prefs)

    matches = []
    if candidate is not None:
        result = run_vacancy_agent(
            candidate,
            preferences,
            saved_career.get("clarifications") or {},
            saved_career.get("role_names") or [],
            saved_career.get("skill_results") or {},
        )
        matches = result.get("matches") or []

    matching_prefs_count = sum(1 for item in matches if item.meets_preferences)
    top_matches = matches[:3]

    modality_text = MODALITY_LABELS.get(preferences.modality, "Cualquier modalidad")
    city_text = preferences.city or "Cualquier ciudad"
    salary_text = (
        f"Desde ${preferences.salary_min:,} COP".replace(",", ".")
        if preferences.salary_min else "Sin mínimo definido"
    )

    prefs_status = "completed" if has_saved_prefs else ("in_progress" if candidate else "pending")
    match_status = "completed" if matches else "pending"
    stage_status = "completed" if (matches and has_saved_prefs) else ("in_progress" if matches else "pending")

    match_items = [
        f"{item.title} ({item.company}): {item.score}% de coincidencia con los requisitos del cargo."
        for item in top_matches
    ]
    if not match_items:
        match_items = ["Completa tu perfil profesional para que Profilia calcule tu afinidad con cada vacante."]

    return {
        "id": "vacancies",
        "step": 2,
        "title": "Vacantes",
        "subtitle": "Revisa ofertas disponibles, normaliza requisitos y calcula afinidad",
        "icon": "fa-briefcase",
        "status": stage_status,
        "status_label": (
            "Completado" if stage_status == "completed"
            else "En curso" if stage_status == "in_progress"
            else "Pendiente"
        ),
        "action_url": reverse("vacancies") if candidate else reverse("home"),
        "action_label": "Explorar vacantes" if candidate else "Completar perfil primero",
        "summary": (
            "Profilia revisa las ofertas disponibles, estandariza sus requisitos técnicos y condiciones, "
            "y las ordena según tus habilidades confirmadas y tus preferencias laborales."
        ),
        "metrics": [
            {"label": "Ofertas revisadas", "value": str(total_catalog)},
            {"label": "Acordes a tus filtros", "value": str(matching_prefs_count if matches else 0)},
            {
                "label": "Mayor coincidencia",
                "value": f"{top_matches[0].score}%" if top_matches else "—",
            },
        ],
        "nodes": [
            {
                "id": "vacancies-ingest",
                "step_label": "Paso 2.1",
                "title": "Catálogo de vacantes",
                "caption": "Lectura de ofertas disponibles",
                "icon": "fa-database",
                "status": "completed" if candidate else "pending",
                "status_label": "Completado" if candidate else "Pendiente",
                "badge": f"{total_catalog} ofertas",
                "live_action": "Consultando el catálogo de ofertas laborales disponibles para tu búsqueda...",
                "what_did": f"Profilia cargó {total_catalog} ofertas laborales activas con sus requisitos y condiciones.",
                "why_did": (
                    "Reunir todas las vacantes en un mismo flujo permite compararlas con los mismos criterios "
                    "sin que tengas que revisar cada oferta desde cero."
                ),
                "items": [
                    f"Total de vacantes analizadas en el catálogo: {total_catalog}.",
                    "Incluye cargos de desarrollo, datos, nube, pruebas y tecnología.",
                ],
            },
            {
                "id": "vacancies-normalize",
                "step_label": "Paso 2.2",
                "title": "Normalización",
                "caption": "Unificación de habilidades y salarios",
                "icon": "fa-sliders",
                "status": "completed" if candidate else "pending",
                "status_label": "Completado" if candidate else "Pendiente",
                "badge": "Requisitos limpios",
                "live_action": "Estandarizando nombres de habilidades, modalidades y rangos salariales...",
                "what_did": (
                    "Profilia unificó la escritura de habilidades obligatorias y deseables, modalidades "
                    "(remoto, híbrido, presencial) y rangos salariales."
                ),
                "why_did": (
                    "Las ofertas suelen escribir una misma habilidad de distintas maneras. Estandarizarlas "
                    "evita que pierdas coincidencias por diferencias de formato."
                ),
                "items": [
                    "Separación entre requisitos obligatorios y habilidades deseables.",
                    "Verificación de ciudad, modalidad de trabajo y rango salarial.",
                ],
            },
            {
                "id": "vacancies-preferences",
                "step_label": "Paso 2.3",
                "title": "Tus preferencias",
                "caption": "Modalidad, ciudad y salario",
                "icon": "fa-filter",
                "status": prefs_status,
                "status_label": (
                    "Completado" if prefs_status == "completed"
                    else "En curso" if prefs_status == "in_progress"
                    else "Pendiente"
                ),
                "badge": modality_text,
                "live_action": "Contrastando las condiciones de cada oferta con tus preferencias laborales...",
                "what_did": (
                    f"Profilia aplicó tus preferencias actuales: {modality_text.lower()}, "
                    f"{city_text} y salario {salary_text.lower()}."
                ),
                "why_did": (
                    "Para avisarte con claridad cuando una oferta coincide con tus habilidades técnicas "
                    "pero se aparta de la ciudad, modalidad o salario que buscas."
                ),
                "items": [
                    f"Modalidad preferida: {modality_text}.",
                    f"Ciudad preferida: {city_text}.",
                    f"Aspiración salarial: {salary_text}.",
                ],
            },
            {
                "id": "vacancies-matching",
                "step_label": "Paso 2.4",
                "title": "Cálculo de coincidencia",
                "caption": "Ordenamiento y explicación por oferta",
                "icon": "fa-ranking-star",
                "status": match_status,
                "status_label": "Completado" if match_status == "completed" else "Pendiente",
                "badge": f"{len(matches)} evaluadas" if matches else "Pendiente",
                "live_action": "Calculando la coincidencia con los requisitos de cada cargo y ordenando resultados...",
                "what_did": (
                    f"Profilia ordenó las {len(matches)} ofertas según los requisitos obligatorios y deseables "
                    f"que respaldas en tu perfil ({matching_prefs_count} cumplen además todas tus preferencias)."
                    if matches else
                    "Profilia calculará las coincidencias cuando tu perfil tenga información profesional."
                ),
                "why_did": (
                    "Así puedes priorizar las vacantes donde tu perfil tiene mayor respaldo y ver de antemano "
                    "qué requisitos obligatorios te faltaría cubrir."
                ),
                "items": match_items,
            },
        ],
        "edges": [
            {"from": "vacancies-ingest", "to": "vacancies-normalize", "label": "Ofertas brutas"},
            {"from": "vacancies-normalize", "to": "vacancies-preferences", "label": "Datos estandarizados"},
            {"from": "vacancies-preferences", "to": "vacancies-matching", "label": "Criterios + perfil"},
        ],
    }


def _build_applications_stage(candidate: ProfileData | None, applications: list[Application]) -> dict:
    total_selected = len(applications)
    applied = [app for app in applications if app.status == Application.APPLIED]
    pending = [app for app in applications if app.status == Application.SELECTED]

    total_screening = sum(len(app.screening or []) for app in applied)
    total_warnings = sum(len(app.warnings or []) for app in applied)

    if applied and not pending:
        stage_status = "completed"
    elif applications:
        stage_status = "in_progress"
    else:
        stage_status = "pending"

    selection_status = "completed" if applications else "pending"
    execution_status = "completed" if applied else ("in_progress" if pending else "pending")

    selection_items = [
        f"{app.title} · {app.company} ({'Postulada' if app.status == Application.APPLIED else 'Seleccionada para envío'})."
        for app in applications[:4]
    ] or ["Aún no has seleccionado vacantes en la sección de Vacantes."]

    letter_items = [
        f"{app.title} ({app.company}): Carta personalizada preparada con tus fortalezas."
        for app in applied[:3]
    ] or [
        "Cuando inicies el envío en Postulaciones, Profilia redactará una carta de presentación para cada vacante."
    ]

    screening_items = []
    for app in applied[:2]:
        for answer in (app.screening or [])[:2]:
            status_text = SCREENING_STATUS_LABELS.get(answer.get("status"), "Revisada")
            screening_items.append(f"{app.title} — {answer.get('question')}: {status_text}.")
    if not screening_items:
        screening_items = [
            "Profilia responde preguntas sobre tus habilidades, modalidad y aspiración salarial usando solo datos reales de tu cuenta."
        ]

    submission_items = [
        f"Constancia registrada para {app.title} en {app.company} ({app.score}% de coincidencia con los requisitos)."
        for app in applied[:3]
    ]
    if total_warnings:
        submission_items.append(
            f"Se incluyeron {total_warnings} aviso(s) sobre requisitos o preferencias para que los tengas presentes."
        )
    if not submission_items:
        submission_items = [
            "Al finalizar el proceso, Profilia guarda la evidencia de cada postulación simulada y su estado."
        ]

    return {
        "id": "applications",
        "step": 3,
        "title": "Postulaciones",
        "subtitle": "Prepara tu carta, responde preguntas de filtro y guarda constancia",
        "icon": "fa-paper-plane",
        "status": stage_status,
        "status_label": (
            "Completado" if stage_status == "completed"
            else "En curso" if stage_status == "in_progress"
            else "Pendiente"
        ),
        "action_url": (
            reverse("applications") if applications
            else (reverse("vacancies") if candidate else reverse("home"))
        ),
        "action_label": (
            "Ver mis postulaciones" if applications
            else ("Elegir vacantes" if candidate else "Completar perfil primero")
        ),
        "summary": (
            "Para cada vacante que eliges, Profilia redacta una carta de presentación honesta, "
            "responde las preguntas de filtro técnico y registra la evidencia del envío simulado."
        ),
        "metrics": [
            {"label": "Vacantes elegidas", "value": str(total_selected)},
            {"label": "Postulaciones enviadas", "value": str(len(applied))},
            {"label": "Preguntas respondidas", "value": str(total_screening)},
        ],
        "nodes": [
            {
                "id": "applications-select",
                "step_label": "Paso 3.1",
                "title": "Selección de vacantes",
                "caption": "Confirmación de ofertas a postular",
                "icon": "fa-check-double",
                "status": selection_status,
                "status_label": "Completado" if selection_status == "completed" else "Pendiente",
                "badge": f"{total_selected} seleccionada(s)",
                "live_action": "Verificando las vacantes que seleccionaste y comprobando sus requisitos...",
                "what_did": (
                    f"Profilia preparó tu lista con {total_selected} vacante(s) elegida(s) "
                    f"({len(applied)} postulada(s) y {len(pending)} pendiente(s) de envío)."
                    if applications else
                    "Profilia espera que selecciones al menos una vacante para preparar tu candidatura."
                ),
                "why_did": (
                    "Tú decides siempre a qué ofertas postular; Profilia nunca envía una candidatura "
                    "sin tu selección previa."
                ),
                "items": selection_items,
            },
            {
                "id": "applications-letter",
                "step_label": "Paso 3.2",
                "title": "Carta de presentación",
                "caption": "Redacción adaptada a cada cargo",
                "icon": "fa-envelope-open-text",
                "status": execution_status,
                "status_label": (
                    "Completado" if execution_status == "completed"
                    else "En curso" if execution_status == "in_progress"
                    else "Pendiente"
                ),
                "badge": f"{len(applied)} carta(s)",
                "live_action": "Redactando una carta de presentación personalizada con tus habilidades reales...",
                "what_did": (
                    f"Profilia redactó {len(applied)} carta(s) de presentación destacando las habilidades "
                    "de tu perfil que coinciden con cada oferta."
                    if applied else
                    "Profilia redactará una carta adaptada a cada cargo cuando inicies el proceso de postulación."
                ),
                "why_did": (
                    "Para presentar tu perfil de forma clara ante cada empresa sin inventar experiencia "
                    "ni prometer requisitos que aún no figuran en tu cuenta."
                ),
                "items": letter_items,
            },
            {
                "id": "applications-screening",
                "step_label": "Paso 3.3",
                "title": "Preguntas de filtro",
                "caption": "Respuestas respaldadas en tu perfil",
                "icon": "fa-clipboard-question",
                "status": execution_status,
                "status_label": (
                    "Completado" if execution_status == "completed"
                    else "En curso" if execution_status == "in_progress"
                    else "Pendiente"
                ),
                "badge": f"{total_screening} respuesta(s)",
                "live_action": "Respondiendo las preguntas técnicas, de modalidad y salario de cada vacante...",
                "what_did": (
                    f"Profilia completó {total_screening} respuesta(s) de filtro indicando con transparencia "
                    "cuáles cuentan con respaldo en tu perfil y cuáles siguen pendientes."
                    if applied else
                    "Profilia preparará las respuestas de filtro técnico y preferencias para tus vacantes."
                ),
                "why_did": (
                    "Mantener la honestidad sobre lo que dominas y lo que estás aprendiendo protege tu "
                    "credibilidad profesional durante el proceso de selección."
                ),
                "items": screening_items,
            },
            {
                "id": "applications-submit",
                "step_label": "Paso 3.4",
                "title": "Envío y constancia",
                "caption": "Simulación en Magneto 365 y evidencia",
                "icon": "fa-shield-check",
                "status": "completed" if applied else "pending",
                "status_label": "Completado" if applied else "Pendiente",
                "badge": f"{len(applied)} enviada(s)",
                "live_action": "Simulando el envío a Magneto 365 y guardando la constancia en tu cuenta...",
                "what_did": (
                    f"Profilia registró {len(applied)} postulación(es) simulada(s) con fecha de envío, "
                    "carta, respuestas de filtro y avisos de revisión."
                    if applied else
                    "Profilia guardará el paquete completo de cada postulación para que puedas consultarlo cuando quieras."
                ),
                "why_did": (
                    "Guardar la evidencia completa te permite revisar en cualquier momento qué enviaste "
                    "a cada empresa y prepararte mejor para una entrevista."
                ),
                "items": submission_items,
            },
        ],
        "edges": [
            {"from": "applications-select", "to": "applications-letter", "label": "Vacantes confirmadas"},
            {"from": "applications-letter", "to": "applications-screening", "label": "Carta lista"},
            {"from": "applications-screening", "to": "applications-submit", "label": "Paquete validado"},
        ],
    }


def _build_followup_stage(applications: list[Application], state: dict) -> dict:
    applied = [app for app in applications if app.status == Application.APPLIED]
    assessments = state.get("assessments") or []

    missing_skills = []
    for item in assessments:
        for skill in item.get("unknown_skills") or []:
            if skill not in missing_skills:
                missing_skills.append(skill)
    for app in applied:
        for warning in app.warnings or []:
            if warning not in missing_skills:
                missing_skills.append(warning)

    active_items = [
        f"Monitoreo preparado para {app.title} en {app.company}."
        for app in applied[:3]
    ] or [
        "Vista previa: cuando envíes postulaciones, aquí verás las candidaturas activas bajo seguimiento."
    ]

    reminder_items = [
        f"Recordatorio sugerido (7 días): revisar novedades de {app.company} para {app.title}."
        for app in applied[:2]
    ] + [
        "Recordatorio sugerido: actualizar tu perfil si completas un curso o proyecto nuevo."
    ]

    practice_items = (
        [f"Punto de preparación detectado: {item}" for item in missing_skills[:3]]
        if missing_skills else [
            "Repasar las habilidades clave mencionadas en tus cartas de presentación antes de la entrevista."
        ]
    )

    next_steps_items = [
        "1. Revisar las cartas y respuestas de filtro guardadas en tus postulaciones.",
        "2. Completar cualquier habilidad pendiente en la orientación de Mi perfil.",
        "3. Explorar nuevas vacantes si cambian tus preferencias de modalidad o ciudad.",
    ]

    return {
        "id": "followup",
        "step": 4,
        "title": "Seguimiento",
        "subtitle": "Organiza recordatorios, repaso de habilidades y próximos pasos",
        "icon": "fa-chart-line",
        "status": "preview",
        "status_label": "Vista previa",
        "action_url": reverse("applications") if applications else reverse("home"),
        "action_label": "Ver postulaciones base" if applications else "Ir a Mi perfil",
        "summary": (
            "Así funciona la etapa de Seguimiento en Profilia: a partir de tus postulaciones y de los vacíos "
            "detectados en tu perfil, organiza recordatorios y próximos pasos recomendados."
        ),
        "metrics": [
            {"label": "Candidaturas base", "value": str(len(applied))},
            {"label": "Recordatorios sugeridos", "value": str(max(len(applied), 2))},
            {"label": "Próximos pasos", "value": "3"},
        ],
        "nodes": [
            {
                "id": "followup-monitor",
                "step_label": "Paso 4.1",
                "title": "Estado de envíos",
                "caption": "Consolidación de postulaciones",
                "icon": "fa-inbox",
                "status": "preview",
                "status_label": "Vista previa",
                "badge": f"{len(applied)} activa(s)",
                "live_action": "Reuniendo el estado y la fecha de tus postulaciones enviadas...",
                "what_did": (
                    f"Profilia toma tus {len(applied)} postulación(es) enviada(s) para organizar tu agenda de seguimiento."
                    if applied else
                    "En esta etapa, Profilia reúne las postulaciones que hayas enviado para darles continuidad."
                ),
                "why_did": (
                    "Llevar el control de cada candidatura evita olvidar fechas clave o perder el hilo "
                    "de las vacantes a las que aplicaste."
                ),
                "items": active_items,
            },
            {
                "id": "followup-reminders",
                "step_label": "Paso 4.2",
                "title": "Recordatorios",
                "caption": "Alertas oportunas de revisión",
                "icon": "fa-bell",
                "status": "preview",
                "status_label": "Vista previa",
                "badge": f"{len(reminder_items)} alerta(s)",
                "live_action": "Programando recordatorios sugeridos para revisar el avance de cada proceso...",
                "what_did": "Profilia genera recordatorios periódicos según la fecha en que enviaste cada candidatura.",
                "why_did": (
                    "Dar seguimiento a tiempo te ayuda a mantenerte atento a citaciones, pruebas técnicas "
                    "o actualizaciones de la oferta."
                ),
                "items": reminder_items,
            },
            {
                "id": "followup-practice",
                "step_label": "Paso 4.3",
                "title": "Refuerzo de perfil",
                "caption": "Foco en requisitos pendientes",
                "icon": "fa-graduation-cap",
                "status": "preview",
                "status_label": "Vista previa",
                "badge": "Enfoque práctico",
                "live_action": "Conectando los avisos de tus postulaciones con temas recomendados de estudio...",
                "what_did": (
                    "Profilia cruza los requisitos que quedaron pendientes en tus vacantes con tus metas de carrera."
                ),
                "why_did": (
                    "Aprovechar el tiempo de espera para practicar las habilidades que pedían las ofertas "
                    "te prepara mejor para la entrevista y para futuras postulaciones."
                ),
                "items": practice_items,
            },
            {
                "id": "followup-next",
                "step_label": "Paso 4.4",
                "title": "Próximos pasos",
                "caption": "Hoja de ruta recomendada",
                "icon": "fa-route",
                "status": "preview",
                "status_label": "Vista previa",
                "badge": "3 acciones",
                "live_action": "Sintetizando tus próximas acciones recomendadas dentro de Profilia...",
                "what_did": "Profilia resume las acciones concretas para continuar avanzando en tu búsqueda de empleo.",
                "why_did": (
                    "Para que después de postular siempre tengas claridad sobre qué paso dar a continuación."
                ),
                "items": next_steps_items,
            },
        ],
        "edges": [
            {"from": "followup-monitor", "to": "followup-reminders", "label": "Fechas de envío"},
            {"from": "followup-reminders", "to": "followup-practice", "label": "Avisos y brechas"},
            {"from": "followup-practice", "to": "followup-next", "label": "Plan de acción"},
        ],
    }


def build_traceability_payload(user) -> dict:
    profile = Profile.objects.filter(user=user).first()
    candidate = _candidate_from_profile(profile)
    state = get_profile_state(profile)
    saved_career = get_career_data(profile) if profile else {}
    applications = list(Application.objects.filter(user=user))

    stages = [
        _build_profile_stage(profile, candidate, state),
        _build_vacancies_stage(profile, candidate, saved_career),
        _build_applications_stage(candidate, applications),
        _build_followup_stage(applications, state),
    ]

    active_stage_id = "profile"
    for stage in stages:
        if stage["status"] in ("in_progress", "completed") and stage["id"] != "followup":
            active_stage_id = stage["id"]

    completed_stages = sum(1 for stage in stages if stage["status"] == "completed")

    return {
        "candidate_name": getattr(user, "full_name", "") or "Candidato Profilia",
        "active_stage_id": active_stage_id,
        "completed_stages": completed_stages,
        "total_stages": len(stages),
        "stages": stages,
    }


@login_required
def traceability_page(request):
    payload = build_traceability_payload(request.user)
    return render(request, "pages/traceability.html", {
        "page_title": "Historial de actividad",
        "traceability_data": payload,
    })
