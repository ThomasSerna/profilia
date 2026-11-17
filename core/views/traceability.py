from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from pydantic import ValidationError

from agents.applications.catalog import load_vacancies_by_id
from agents.career.cache import get_career_data, get_profile_state
from agents.profile.schemas import ProfileData, has_professional_information
from agents.vacancies.graph import run_vacancy_agent
from agents.vacancies.schemas import Preferences
from core.models import Application, ApplicationStatusChange, Profile, Reminder
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

GROUP_SHORT_LABELS = {
    "high": "Alta coincidencia",
    "medium": "Coincidencia parcial",
    "low": "Por fortalecer",
    "pending": "En revisión",
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
        source_badge = "Sin datos"
        source_what = "Aún no has cargado tu hoja de vida ni editado tu perfil."
        source_items = ["Sube un PDF o edita tu perfil manualmente."]
        source_visuals = [
            {"label": "Hoja de vida PDF", "value": "Pendiente", "tone": "slate", "icon": "fa-file-pdf"},
            {"label": "Edición manual", "value": "Disponible", "tone": "sky", "icon": "fa-pen-to-square"},
        ]
    elif has_cv and manual_fields:
        source_status = "completed"
        source_badge = "PDF + Manual"
        source_what = f"Profilia combinó tu hoja de vida en PDF con {len(manual_fields)} sección(es) editada(s) por ti."
        source_items = [
            "Hoja de vida en PDF procesada.",
            f"Secciones ajustadas por ti: {len(manual_fields)}.",
        ]
        source_visuals = [
            {"label": "Origen principal", "value": "Hoja de vida PDF", "tone": "emerald", "icon": "fa-file-pdf"},
            {"label": "Edición protegida", "value": f"{len(manual_fields)} sección(es)", "tone": "emerald", "icon": "fa-user-pen"},
        ]
    elif has_cv:
        source_status = "completed"
        source_badge = "PDF leído"
        source_what = "Profilia leyó tu trayectoria desde tu hoja de vida en PDF."
        source_items = ["Hoja de vida en PDF cargada en tu cuenta."]
        source_visuals = [
            {"label": "Origen", "value": "Hoja de vida PDF", "tone": "emerald", "icon": "fa-file-pdf"},
            {"label": "Estado", "value": "Lectura completa", "tone": "emerald", "icon": "fa-check"},
        ]
    else:
        source_status = "completed"
        source_badge = "Manual"
        source_what = "Profilia registró la información que ingresaste en el editor de perfil."
        source_items = ["Perfil creado directamente por ti."]
        source_visuals = [
            {"label": "Origen", "value": "Editor manual", "tone": "emerald", "icon": "fa-pen-to-square"},
            {"label": "Control", "value": "Directo del usuario", "tone": "emerald", "icon": "fa-shield-halved"},
        ]

    structure_status = "completed" if has_profile else "pending"
    structure_items = []
    if has_profile:
        if skills:
            structure_items.append(f"Habilidades registradas: {', '.join(skills[:6])}.")
        if experiences:
            structure_items.append(f"Experiencias laborales: {experiences}.")
        if educations:
            structure_items.append(f"Educación: {educations}.")
        if languages:
            structure_items.append(f"Idiomas: {', '.join(languages[:4])}.")
    if not structure_items:
        structure_items = ["Sin habilidades ni experiencia registradas aún."]

    structure_visuals = [
        {"label": "Habilidades", "value": str(len(skills)), "tone": "emerald" if skills else "slate", "icon": "fa-code"},
        {"label": "Experiencia", "value": str(experiences), "tone": "emerald" if experiences else "slate", "icon": "fa-briefcase"},
        {"label": "Educación", "value": str(educations), "tone": "emerald" if educations else "slate", "icon": "fa-graduation-cap"},
        {"label": "Idiomas", "value": str(len(languages)), "tone": "emerald" if languages else "slate", "icon": "fa-language"},
    ]

    confirmed_yes = [item["label"] for item in answered if item.get("answer") == "yes"]
    confirmed_no = [item["label"] for item in answered if item.get("answer") in ("no", "unknown")]
    pending_labels = [item["label"] for item in pending]

    evidence_status = "completed" if has_profile else "pending"
    evidence_items = (
        [f"Respaldo en CV: {', '.join(skills[:6])}."]
        if skills else ["Sube o edita tu perfil para detectar tus fortalezas actuales."]
    )
    evidence_visuals = [
        {"label": skill, "value": "En tu CV", "tone": "emerald", "icon": "fa-circle-check"}
        for skill in skills[:5]
    ] or [{"label": "Evidencia en CV", "value": "Pendiente", "tone": "slate", "icon": "fa-hourglass-half"}]

    if answered or (assessments and not pending):
        gaps_status = "completed"
    elif pending or has_profile:
        gaps_status = "in_progress"
    else:
        gaps_status = "pending"

    gaps_items = []
    if confirmed_yes:
        gaps_items.append(f"Confirmadas por ti: {', '.join(confirmed_yes[:4])}.")
    if confirmed_no:
        gaps_items.append(f"Por fortalecer: {', '.join(confirmed_no[:4])}.")
    if pending_labels:
        gaps_items.append(f"Por conversar: {', '.join(pending_labels[:4])}.")
    if not gaps_items:
        gaps_items.append("Revisa qué requisitos no figuran en tu CV para consultarte antes de asumir.")

    gaps_visuals = (
        [{"label": item, "value": "Confirmada", "tone": "emerald", "icon": "fa-check"} for item in confirmed_yes[:3]]
        + [{"label": item, "value": "Por fortalecer", "tone": "amber", "icon": "fa-arrow-trend-up"} for item in confirmed_no[:2]]
        + [{"label": item, "value": "Por responder", "tone": "sky", "icon": "fa-circle-question"} for item in pending_labels[:2]]
    ) or [{"label": "Aclaraciones", "value": "Sin preguntas pendientes", "tone": "slate", "icon": "fa-comments"}]

    roles_status = "completed" if assessments else ("in_progress" if has_profile else "pending")
    roles_items = [
        f"{item['role_name']}: {GROUP_LABELS.get(item.get('group'), 'Evaluación en curso')}."
        for item in assessments[:3]
    ] or ["Elige entre 1 y 3 cargos en Mi perfil para activar tu orientación."]

    roles_visuals = [
        {
            "label": item["role_name"],
            "value": GROUP_SHORT_LABELS.get(item.get("group"), "En curso"),
            "tone": "emerald" if item.get("group") == "high" else ("amber" if item.get("group") == "medium" else "sky"),
            "icon": "fa-compass",
        }
        for item in assessments[:3]
    ] or [{"label": "Cargos objetivo", "value": "Selecciona 1 a 3 cargos", "tone": "slate", "icon": "fa-bullseye"}]

    stage_status = "completed" if (has_profile and assessments and not pending) else (
        "in_progress" if has_profile else "pending"
    )
    headline_metric = (
        f"{len(skills)} hab. · {len(role_names)} cargo(s)"
        if has_profile else "Sin perfil registrado"
    )

    return {
        "id": "profile",
        "step": 1,
        "title": "Perfil",
        "full_title": "Perfil y orientación",
        "subtitle": "Estructura tu CV, detecta vacíos y evalúa cargos",
        "icon": "fa-id-card",
        "status": stage_status,
        "status_label": (
            "Completado" if stage_status == "completed"
            else "En curso" if stage_status == "in_progress"
            else "Pendiente"
        ),
        "action_url": reverse("home"),
        "action_label": "Ir a Mi perfil",
        "summary": "Estructura tu perfil, separa evidencia real de vacíos y orienta tus cargos.",
        "headline_metric": headline_metric,
        "metrics": [
            {"label": "Habilidades", "value": str(len(skills))},
            {"label": "Cargos", "value": str(len(role_names))},
            {"label": "Aclaradas", "value": str(len(answered))},
        ],
        "nodes": [
            {
                "id": "profile-source",
                "step_label": "1.1",
                "title": "Fuente de datos",
                "caption": "PDF o edición manual",
                "icon": "fa-file-arrow-up",
                "status": source_status,
                "status_label": "Completado" if source_status == "completed" else "Pendiente",
                "badge": source_badge,
                "x": 9,
                "y": 50,
                "live_action": "Leyendo tu información profesional y respetando tus ediciones manuales...",
                "what_did": source_what,
                "why_did": "Puedes actualizar tu PDF cuando quieras: las secciones que edites a mano siempre se conservan.",
                "items": source_items,
                "visual_items": source_visuals,
                "scene": {
                    "kind": "scanner",
                    "has_profile": has_profile,
                    "has_cv": has_cv,
                    "manual_count": len(manual_fields),
                    "tokens": skills[:6] or ["Experiencia", "Habilidades", "Educación"],
                },
            },
            {
                "id": "profile-structure",
                "step_label": "1.2",
                "title": "Estructura CV",
                "caption": "Secciones normalizadas",
                "icon": "fa-diagram-project",
                "status": structure_status,
                "status_label": "Completado" if structure_status == "completed" else "Pendiente",
                "badge": f"{len(skills)} hab · {experiences} exp",
                "x": 36,
                "y": 50,
                "live_action": "Separando habilidades, experiencia, estudios e idiomas...",
                "what_did": (
                    f"Tu perfil quedó organizado en {len(skills)} habilidad(es), {experiences} experiencia(s) y {educations} estudio(s)."
                    if has_profile else "Cuando registres tu información, la organizaremos en bloques claros."
                ),
                "why_did": "Separar tus habilidades, trayectoria, formación e idiomas permite compararte con justicia frente a los requisitos de cada cargo.",
                "items": structure_items,
                "visual_items": structure_visuals,
                "scene": {
                    "kind": "structure",
                    "blocks": [
                        {"label": "Habilidades", "count": len(skills)},
                        {"label": "Experiencia", "count": experiences},
                        {"label": "Educación", "count": educations},
                        {"label": "Idiomas", "count": len(languages)},
                    ],
                    "chips": skills[:6],
                },
            },
            {
                "id": "profile-evidence",
                "step_label": "1.3A",
                "title": "Evidencia en CV",
                "caption": "Respaldo directo",
                "icon": "fa-shield-halved",
                "status": evidence_status,
                "status_label": "Completado" if evidence_status == "completed" else "Pendiente",
                "badge": f"{len(skills)} en CV",
                "x": 63,
                "y": 23,
                "live_action": "Verificando qué requisitos ya tienen respaldo directo en tu hoja de vida...",
                "what_did": (
                    f"Encontramos respaldo directo para {len(skills)} habilidad(es) en tu perfil actual."
                    if has_profile else "Identificaremos tus fortalezas en cuanto cargues o edites tu perfil."
                ),
                "why_did": "Distinguimos lo que ya está respaldado en tu hoja de vida de aquello sobre lo que aún nos falta información.",
                "items": evidence_items,
                "visual_items": evidence_visuals,
                "scene": {
                    "kind": "evidence",
                    "verified": skills[:6],
                    "experiences": experiences,
                },
            },
            {
                "id": "profile-gaps",
                "step_label": "1.3B",
                "title": "Detección de vacíos",
                "caption": "Preguntas puntuales",
                "icon": "fa-magnifying-glass-chart",
                "status": gaps_status,
                "status_label": (
                    "Completado" if gaps_status == "completed"
                    else "En curso" if gaps_status == "in_progress"
                    else "Pendiente"
                ),
                "badge": (
                    f"{len(answered)} aclar. · {len(pending)} pend."
                    if pending else f"{len(answered)} aclarada(s)"
                ),
                "x": 63,
                "y": 77,
                "live_action": "Detectando requisitos ausentes en el CV para preguntarte directamente...",
                "what_did": (
                    f"Identificamos {len(answered) + len(pending)} requisito(s) que no figuraban en tu CV ({len(answered)} aclarado(s) contigo)."
                    if (answered or pending) else "Revisamos tus cargos objetivo para detectar requisitos que no aparecen escritos en tu hoja de vida."
                ),
                "why_did": "No encontrar una habilidad en tu hoja de vida no significa que no la conozcas; por eso te consultamos antes de descartarla.",
                "items": gaps_items,
                "visual_items": gaps_visuals,
                "scene": {
                    "kind": "decision_gate",
                    "confirmed": confirmed_yes[:4],
                    "strengthen": confirmed_no[:4],
                    "pending": pending_labels[:4],
                },
            },
            {
                "id": "profile-guidance",
                "step_label": "1.4",
                "title": "Orientación",
                "caption": "Ruta por cargo",
                "icon": "fa-compass",
                "status": roles_status,
                "status_label": (
                    "Completado" if roles_status == "completed"
                    else "En curso" if roles_status == "in_progress"
                    else "Pendiente"
                ),
                "badge": f"{len(assessments)} cargo(s)",
                "x": 90,
                "y": 50,
                "live_action": "Consolidando tu nivel de coincidencia y plan de mejora por cargo...",
                "what_did": (
                    f"Profilia preparó tu orientación para {len(assessments)} cargo(s) combinando tu CV y tus aclaraciones."
                    if assessments else "Elige entre 1 y 3 cargos de tu interés en Mi perfil para recibir tu orientación."
                ),
                "why_did": "Así sabes en qué roles tienes mayor coincidencia hoy y qué habilidades te conviene fortalecer primero.",
                "items": roles_items,
                "visual_items": roles_visuals,
                "scene": {
                    "kind": "roles_meter",
                    "roles": [
                        {
                            "name": item["role_name"],
                            "group": item.get("group", "pending"),
                            "label": GROUP_SHORT_LABELS.get(item.get("group"), "En curso"),
                        }
                        for item in assessments[:3]
                    ],
                },
            },
        ],
        "edges": [
            {"from": "profile-source", "to": "profile-structure", "label": "Lee y ordena", "active": has_profile},
            {"from": "profile-structure", "to": "profile-evidence", "label": "Figura en CV", "active": has_profile},
            {"from": "profile-structure", "to": "profile-gaps", "label": "No figura en CV", "active": bool(has_profile or answered or pending)},
            {"from": "profile-evidence", "to": "profile-guidance", "label": "Fortalezas", "active": bool(assessments)},
            {"from": "profile-gaps", "to": "profile-guidance", "label": "Aclaraciones", "active": bool(assessments or answered)},
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
        if preferences.salary_min else "Sin mínimo"
    )

    prefs_status = "completed" if has_saved_prefs else ("in_progress" if candidate else "pending")
    match_status = "completed" if matches else "pending"
    stage_status = "completed" if (matches and has_saved_prefs) else ("in_progress" if matches else "pending")

    match_items = [
        f"{item.title} ({item.company}): {item.score}% de coincidencia con los requisitos del cargo."
        for item in top_matches
    ] or ["Completa tu perfil para calcular tu coincidencia con cada oferta."]

    match_visuals = [
        {
            "label": f"{item.title} · {item.company}",
            "value": f"{item.score}%",
            "score": item.score,
            "tone": "emerald" if item.score >= 75 else ("amber" if item.score >= 50 else "sky"),
            "icon": "fa-ranking-star",
        }
        for item in matches[:4]
    ] or [{"label": "Ranking de ofertas", "value": "Pendiente de perfil", "tone": "slate", "icon": "fa-hourglass-start"}]

    return {
        "id": "vacancies",
        "step": 2,
        "title": "Vacantes",
        "full_title": "Vacantes y afinidad",
        "subtitle": "Normaliza el catálogo, filtra preferencias y ordena por coincidencia",
        "icon": "fa-briefcase",
        "status": stage_status,
        "status_label": (
            "Completado" if stage_status == "completed"
            else "En curso" if stage_status == "in_progress"
            else "Pendiente"
        ),
        "action_url": reverse("vacancies") if candidate else reverse("home"),
        "action_label": "Explorar vacantes" if candidate else "Completar perfil",
        "summary": "Estandariza las ofertas disponibles y cruza en paralelo tus habilidades y tus filtros.",
        "headline_metric": (
            f"{total_catalog} ofertas · {matching_prefs_count} acordes"
            if matches else f"{total_catalog} ofertas en catálogo"
        ),
        "metrics": [
            {"label": "Ofertas", "value": str(total_catalog)},
            {"label": "Acordes", "value": str(matching_prefs_count if matches else 0)},
            {"label": "Afinidad", "value": f"{top_matches[0].score}%" if top_matches else "—"},
        ],
        "nodes": [
            {
                "id": "vacancies-ingest",
                "step_label": "2.1",
                "title": "Catálogo",
                "caption": "Ingesta de ofertas",
                "icon": "fa-database",
                "status": "completed" if candidate else "pending",
                "status_label": "Completado" if candidate else "Pendiente",
                "badge": f"{total_catalog} ofertas",
                "x": 9,
                "y": 50,
                "live_action": "Cargando las ofertas disponibles en el catálogo laboral...",
                "what_did": f"Reunimos {total_catalog} ofertas activas con sus requisitos técnicos y condiciones laborales.",
                "why_did": "Revisar todo el catálogo en un solo paso te ahorra buscar y leer oferta por oferta.",
                "items": [f"Total de vacantes en catálogo: {total_catalog}."],
                "visual_items": [
                    {"label": "Ofertas activas", "value": str(total_catalog), "tone": "emerald", "icon": "fa-layer-group"},
                    {"label": "Áreas", "value": "Software · Datos · Nube", "tone": "sky", "icon": "fa-laptop-code"},
                ],
                "scene": {
                    "kind": "catalog_grid",
                    "total": total_catalog,
                    "titles": [m.title for m in top_matches] or ["Desarrollador Python", "Ingeniero de Datos", "DevOps"],
                },
            },
            {
                "id": "vacancies-normalize",
                "step_label": "2.2",
                "title": "Normalización",
                "caption": "Limpieza de formato",
                "icon": "fa-sliders",
                "status": "completed" if candidate else "pending",
                "status_label": "Completado" if candidate else "Pendiente",
                "badge": "Estándar limpio",
                "x": 36,
                "y": 50,
                "live_action": "Unificando nombres de habilidades, modalidades y salarios...",
                "what_did": "Unificamos el formato de habilidades obligatorias, deseables, ciudades, modalidades y salarios.",
                "why_did": "Evita que pierdas oportunidades solo porque una empresa escribió una herramienta o modalidad con otro nombre.",
                "items": ["Separación entre requisitos obligatorios y deseables."],
                "visual_items": [
                    {"label": "Habilidades", "value": "Oblig. vs Deseables", "tone": "emerald", "icon": "fa-list-check"},
                    {"label": "Condiciones", "value": "Ciudad · Modalidad · Salario", "tone": "emerald", "icon": "fa-scale-balanced"},
                ],
                "scene": {
                    "kind": "normalizer",
                    "pairs": [
                        {"raw": "Py / Python 3", "clean": "Python"},
                        {"raw": "Home office", "clean": "Remoto"},
                        {"raw": " PostgreSQL ", "clean": "SQL"},
                    ],
                },
            },
            {
                "id": "vacancies-skills",
                "step_label": "2.3A",
                "title": "Cruce técnico",
                "caption": "Evidencia + aclaraciones",
                "icon": "fa-code-compare",
                "status": match_status,
                "status_label": "Completado" if match_status == "completed" else "Pendiente",
                "badge": f"{len( candidate.skills ) if candidate else 0} hab. cruzadas",
                "x": 63,
                "y": 23,
                "live_action": "Comparando tus habilidades confirmadas con los requisitos de cada vacante...",
                "what_did": (
                    f"Comparamos tus {len(candidate.skills) if candidate else 0} habilidades registradas y tus aclaraciones frente a cada vacante."
                    if matches else "Cruzaremos tus habilidades y aclaraciones con cada oferta apenas completes tu perfil."
                ),
                "why_did": "Damos prioridad a los requisitos indispensables del cargo y sumamos tus fortalezas deseables con transparencia.",
                "items": match_items[:2],
                "visual_items": [
                    {
                        "label": m.title,
                        "value": f"{len(m.matched_skills)} cubiertas · {len(m.missing_required)} pend.",
                        "tone": "emerald" if not m.missing_required else "amber",
                        "icon": "fa-puzzle-piece",
                    }
                    for m in top_matches
                ] or [{"label": "Cruce técnico", "value": "Requiere perfil activo", "tone": "slate", "icon": "fa-code"}],
                "scene": {
                    "kind": "skill_matrix",
                    "matches": [
                        {
                            "title": m.title,
                            "score": m.score,
                            "matched": len(m.matched_skills),
                            "missing": len(m.missing_required),
                        }
                        for m in top_matches
                    ],
                },
            },
            {
                "id": "vacancies-preferences",
                "step_label": "2.3B",
                "title": "Tus filtros",
                "caption": "Modalidad, ciudad y salario",
                "icon": "fa-filter",
                "status": prefs_status,
                "status_label": (
                    "Completado" if prefs_status == "completed"
                    else "En curso" if prefs_status == "in_progress"
                    else "Pendiente"
                ),
                "badge": modality_text,
                "x": 63,
                "y": 77,
                "live_action": "Contrastando modalidad, ubicación y salario con tus preferencias...",
                "what_did": f"Contrastamos las ofertas con tus preferencias: {modality_text.lower()}, {city_text} y {salary_text.lower()}.",
                "why_did": "Te señalamos con claridad cuándo una oferta coincide con tu perfil técnico pero se aparta de tus condiciones.",
                "items": [
                    f"Modalidad: {modality_text}.",
                    f"Ciudad: {city_text}.",
                    f"Salario: {salary_text}.",
                ],
                "visual_items": [
                    {"label": "Modalidad", "value": modality_text, "tone": "emerald", "icon": "fa-house-laptop"},
                    {"label": "Ciudad", "value": city_text, "tone": "sky", "icon": "fa-location-dot"},
                    {"label": "Salario", "value": salary_text, "tone": "emerald", "icon": "fa-coins"},
                ],
                "scene": {
                    "kind": "filter_gate",
                    "modality": modality_text,
                    "city": city_text,
                    "salary": salary_text,
                    "passed": matching_prefs_count,
                    "total": len(matches) or total_catalog,
                },
            },
            {
                "id": "vacancies-matching",
                "step_label": "2.4",
                "title": "Ranking afinidad",
                "caption": "Orden final de ofertas",
                "icon": "fa-ranking-star",
                "status": match_status,
                "status_label": "Completado" if match_status == "completed" else "Pendiente",
                "badge": f"Máx {top_matches[0].score}%" if top_matches else "Pendiente",
                "x": 90,
                "y": 50,
                "live_action": "Ordenando las ofertas por coincidencia con los requisitos del cargo...",
                "what_did": (
                    f"Ordenamos las {len(matches)} ofertas según tu coincidencia con los requisitos del cargo ({matching_prefs_count} cumplen tus filtros)."
                    if matches else "Ordenaremos las ofertas por coincidencia en cuanto registres tu perfil profesional."
                ),
                "why_did": "Te ayuda a enfocar tus postulaciones donde tienes mayor respaldo real y ver qué requisito te faltaría cubrir.",
                "items": match_items,
                "visual_items": match_visuals,
                "scene": {
                    "kind": "ranking_bars",
                    "bars": [
                        {
                            "title": m.title,
                            "company": m.company,
                            "score": m.score,
                            "meets_prefs": m.meets_preferences,
                        }
                        for m in matches[:4]
                    ],
                },
            },
        ],
        "edges": [
            {"from": "vacancies-ingest", "to": "vacancies-normalize", "label": "Unifica datos", "active": candidate is not None},
            {"from": "vacancies-normalize", "to": "vacancies-skills", "label": "Requisitos", "active": candidate is not None},
            {"from": "vacancies-normalize", "to": "vacancies-preferences", "label": "Condiciones", "active": candidate is not None},
            {"from": "vacancies-skills", "to": "vacancies-matching", "label": "Coincidencia", "active": bool(matches)},
            {"from": "vacancies-preferences", "to": "vacancies-matching", "label": f"{matching_prefs_count} acordes" if matches else "Tus filtros", "active": bool(matches)},
        ],
    }


def _build_applications_stage(candidate: ProfileData | None, applications: list[Application]) -> dict:
    total_selected = len(applications)
    applied = [app for app in applications if app.status in Application.SUBMITTED_STATUSES]
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
        f"{app.title} · {app.company} ({'Postulada' if app.status in Application.SUBMITTED_STATUSES else 'En cola'})."
        for app in applications[:4]
    ] or ["Aún no has seleccionado vacantes para postular."]

    letter_items = [
        f"{app.title} ({app.company}): Carta adaptada con tus fortalezas reales."
        for app in applied[:3]
    ] or ["Redactará una carta honesta por vacante al iniciar el envío."]

    screening_items = []
    screening_visuals = []
    for app in applied[:2]:
        for answer in (app.screening or [])[:2]:
            status_text = SCREENING_STATUS_LABELS.get(answer.get("status"), "Revisada")
            screening_items.append(f"{app.title} — {answer.get('question')}: {status_text}.")
            screening_visuals.append({
                "label": answer.get("question") or app.title,
                "value": status_text,
                "tone": "emerald" if answer.get("status") == "cumple" else ("amber" if answer.get("status") == "sin_evidencia" else "sky"),
                "icon": "fa-clipboard-check",
            })
    if not screening_items:
        screening_items = ["Responde preguntas técnicas y de preferencias usando solo datos reales de tu cuenta."]
    if not screening_visuals:
        screening_visuals = [{"label": "Preguntas de filtro", "value": "Pendiente de envío", "tone": "slate", "icon": "fa-clipboard-question"}]

    submission_items = [
        f"Constancia guardada: {app.title} en {app.company} ({app.score}% de coincidencia)."
        for app in applied[:3]
    ] or ["Guarda la constancia completa de cada postulación simulada."]

    return {
        "id": "applications",
        "step": 3,
        "title": "Postulaciones",
        "full_title": "Postulaciones y constancia",
        "subtitle": "Redacta tu carta, responde preguntas de filtro y guarda evidencia",
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
            else ("Elegir vacantes" if candidate else "Completar perfil")
        ),
        "summary": "En paralelo redacta tu carta honesta y responde preguntas de filtro antes de registrar el envío.",
        "headline_metric": (
            f"{len(applied)} enviada(s) · {total_screening} resp."
            if applied else (
                f"{total_selected} elegida(s) por enviar"
                if total_selected else "Sin postulaciones activas"
            )
        ),
        "metrics": [
            {"label": "Elegidas", "value": str(total_selected)},
            {"label": "Enviadas", "value": str(len(applied))},
            {"label": "Filtro", "value": str(total_screening)},
        ],
        "nodes": [
            {
                "id": "applications-select",
                "step_label": "3.1",
                "title": "Selección",
                "caption": "Ofertas confirmadas",
                "icon": "fa-check-double",
                "status": selection_status,
                "status_label": "Completado" if selection_status == "completed" else "Pendiente",
                "badge": f"{total_selected} elegida(s)",
                "x": 10,
                "y": 50,
                "live_action": "Verificando las vacantes que seleccionaste para postular...",
                "what_did": (
                    f"Confirmaste {total_selected} vacante(s) para postular ({len(applied)} enviada(s) y {len(pending)} en preparación)."
                    if applications else "Aún no has seleccionado vacantes para preparar tu postulación."
                ),
                "why_did": "Tú tienes siempre la última palabra sobre a qué ofertas postular; Profilia nunca envía nada sin tu confirmación.",
                "items": selection_items,
                "visual_items": [
                    {
                        "label": f"{app.title} · {app.company}",
                        "value": "Postulada" if app.status in Application.SUBMITTED_STATUSES else "Seleccionada",
                        "tone": "emerald" if app.status in Application.SUBMITTED_STATUSES else "amber",
                        "icon": "fa-briefcase",
                    }
                    for app in applications[:4]
                ] or [{"label": "Vacantes elegidas", "value": "0 seleccionadas", "tone": "slate", "icon": "fa-square-plus"}],
                "scene": {
                    "kind": "selection_queue",
                    "items": [
                        {
                            "title": app.title,
                            "company": app.company,
                            "score": app.score,
                            "applied": app.status in Application.SUBMITTED_STATUSES,
                        }
                        for app in applications[:4]
                    ],
                },
            },
            {
                "id": "applications-letter",
                "step_label": "3.2A",
                "title": "Carta adaptada",
                "caption": "Redacción honesta",
                "icon": "fa-envelope-open-text",
                "status": execution_status,
                "status_label": (
                    "Completado" if execution_status == "completed"
                    else "En curso" if execution_status == "in_progress"
                    else "Pendiente"
                ),
                "badge": f"{len(applied)} carta(s)",
                "x": 39,
                "y": 23,
                "live_action": "Redactando cartas personalizadas con las fortalezas reales de tu perfil...",
                "what_did": (
                    f"Profilia redactó {len(applied)} carta(s) de presentación adaptada(s) a cada cargo y empresa."
                    if applied else "Redactaremos una carta personalizada por cada vacante cuando inicies el envío."
                ),
                "why_did": "Cada carta destaca únicamente las fortalezas y experiencias reales de tu cuenta, sin exagerar ni inventar datos.",
                "items": letter_items,
                "visual_items": [
                    {
                        "label": f"Carta · {app.company}",
                        "value": app.title,
                        "tone": "emerald",
                        "icon": "fa-file-signature",
                    }
                    for app in applied[:3]
                ] or [{"label": "Carta de presentación", "value": "Lista para redactar", "tone": "slate", "icon": "fa-pen-nib"}],
                "scene": {
                    "kind": "letter_composer",
                    "letters": [
                        {"title": app.title, "company": app.company, "score": app.score}
                        for app in applied[:3]
                    ],
                },
            },
            {
                "id": "applications-screening",
                "step_label": "3.2B",
                "title": "Filtro técnico",
                "caption": "Respuestas con respaldo",
                "icon": "fa-clipboard-question",
                "status": execution_status,
                "status_label": (
                    "Completado" if execution_status == "completed"
                    else "En curso" if execution_status == "in_progress"
                    else "Pendiente"
                ),
                "badge": f"{total_screening} resp.",
                "x": 39,
                "y": 77,
                "live_action": "Respondiendo preguntas de requisitos, modalidad y salario...",
                "what_did": (
                    f"Respondimos {total_screening} pregunta(s) de filtro con base en tu perfil y tus preferencias."
                    if applied else "Prepararemos las respuestas a las preguntas de cada oferta usando solo tu información real."
                ),
                "why_did": "Distinguir con honestidad lo respaldado en tu perfil de lo pendiente cuida tu credibilidad ante cada empresa.",
                "items": screening_items,
                "visual_items": screening_visuals,
                "scene": {
                    "kind": "screening_check",
                    "answers": screening_visuals[:4],
                },
            },
            {
                "id": "applications-validate",
                "step_label": "3.3",
                "title": "Validación",
                "caption": "Control de avisos",
                "icon": "fa-magnifying-glass-arrow-right",
                "status": execution_status,
                "status_label": (
                    "Completado" if execution_status == "completed"
                    else "En curso" if execution_status == "in_progress"
                    else "Pendiente"
                ),
                "badge": f"{total_warnings} aviso(s)" if applied else "Revisión",
                "x": 64,
                "y": 50,
                "live_action": "Verificando consistencia del paquete y avisos de requisitos...",
                "what_did": (
                    f"Revisamos {len(applied)} paquete(s) de postulación y registramos {total_warnings} aviso(s) para tu conocimiento."
                    if applied else "Antes de registrar el envío, verificamos que la carta y las respuestas sean consistentes con tu perfil."
                ),
                "why_did": "Te advierte si una oferta pide algún requisito aún sin respaldo en tu perfil o si difiere de tus preferencias.",
                "items": [
                    f"Paquetes validados: {len(applied)}.",
                    f"Avisos registrados para tu revisión: {total_warnings}.",
                ],
                "visual_items": [
                    {"label": "Paquetes verificados", "value": str(len(applied)), "tone": "emerald" if applied else "slate", "icon": "fa-box-archive"},
                    {"label": "Avisos preventivos", "value": str(total_warnings), "tone": "amber" if total_warnings else "emerald", "icon": "fa-triangle-exclamation"},
                ],
                "scene": {
                    "kind": "package_validator",
                    "applied_count": len(applied),
                    "warnings_count": total_warnings,
                    "screening_count": total_screening,
                },
            },
            {
                "id": "applications-submit",
                "step_label": "3.4",
                "title": "Envío y constancia",
                "caption": "Simulación Magneto 365",
                "icon": "fa-circle-check",
                "status": "completed" if applied else "pending",
                "status_label": "Completado" if applied else "Pendiente",
                "badge": f"{len(applied)} enviada(s)",
                "x": 90,
                "y": 50,
                "live_action": "Simulando el envío a Magneto 365 y guardando la evidencia...",
                "what_did": (
                    f"Guardamos la constancia completa de {len(applied)} postulación(es) simulada(s) para Magneto 365."
                    if applied else "Al completar el envío, guardaremos la constancia con fecha, carta y respuestas en tu cuenta."
                ),
                "why_did": "Puedes consultar en cualquier momento qué se envió a cada empresa y prepararte mejor si te contactan.",
                "items": submission_items,
                "visual_items": [
                    {
                        "label": f"{app.title} · {app.company}",
                        "value": f"Enviada · {app.score}%",
                        "score": app.score,
                        "tone": "emerald",
                        "icon": "fa-paper-plane",
                    }
                    for app in applied[:3]
                ] or [{"label": "Constancia de envío", "value": "Sin envíos aún", "tone": "slate", "icon": "fa-inbox"}],
                "scene": {
                    "kind": "submission_dispatch",
                    "sent": [
                        {"title": app.title, "company": app.company, "score": app.score}
                        for app in applied[:3]
                    ],
                },
            },
        ],
        "edges": [
            {"from": "applications-select", "to": "applications-letter", "label": "Perfil + cargo", "active": bool(applications)},
            {"from": "applications-select", "to": "applications-screening", "label": "Preguntas", "active": bool(applications)},
            {"from": "applications-letter", "to": "applications-validate", "label": "Carta lista", "active": bool(applied)},
            {"from": "applications-screening", "to": "applications-validate", "label": "Respuestas", "active": bool(applied)},
            {"from": "applications-validate", "to": "applications-submit", "label": "Paquete listo", "active": bool(applied)},
        ],
    }


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _status_label(status: str) -> str:
    return "Completado" if status == "completed" else "En curso" if status == "in_progress" else "Pendiente"


def _build_followup_stage(applications: list[Application], state: dict) -> dict:
    submitted = [app for app in applications if app.status in Application.SUBMITTED_STATUSES]
    active = [app for app in submitted if app.status in Application.ACTIVE_STATUSES]
    finished = [app for app in submitted if app.status not in Application.ACTIVE_STATUSES]
    by_id = {app.id: app for app in submitted}

    reminders = list(Reminder.objects.filter(application__in=submitted).exclude(status=Reminder.DISMISSED))
    pending_reminders = [item for item in reminders if item.status == Reminder.PENDING]
    done_reminders = [item for item in reminders if item.status == Reminder.DONE]
    changes = list(ApplicationStatusChange.objects.filter(application__in=submitted).order_by("-created_at", "-id"))
    planned = [app for app in active if app.next_step and app.next_step_status == app.status]

    missing_skills = []
    for app in active:
        for skill in (app.audit or {}).get("missing_required") or []:
            if skill not in missing_skills:
                missing_skills.append(skill)
    if not missing_skills:
        for item in state.get("assessments") or []:
            for skill in item.get("unknown_skills") or []:
                if skill not in missing_skills:
                    missing_skills.append(skill)

    if not submitted:
        stage_status = "pending"
    elif active:
        stage_status = "in_progress"
    else:
        stage_status = "completed"

    monitor_status = "completed" if submitted else "pending"
    if reminders or (submitted and not active):
        reminders_status = "completed"
    else:
        reminders_status = "in_progress" if active else "pending"
    practice_status = "completed" if submitted else "pending"
    if submitted and len(planned) == len(active):
        next_status = "completed"
    else:
        next_status = "in_progress" if active else "pending"

    status_counts = [
        (label, sum(1 for app in submitted if app.status == status))
        for status, label in Application.STATUS_CHOICES if status in Application.SUBMITTED_STATUSES
    ]
    status_tones = {"Entrevista": "emerald", "Descartada": "slate"}

    active_items = [
        f"{app.title} en {app.company}: {app.get_status_display()}."
        for app in submitted[:3]
    ] or ["Aún no tienes postulaciones enviadas bajo seguimiento."]
    active_items += [
        f"Último cambio: {by_id[change.application_id].title} pasó a {change.get_to_status_display()}."
        for change in changes[:2]
    ]

    reminder_items = [
        f"{item.due_date.strftime('%d/%m/%Y')}: {item.title} ({by_id[item.application_id].company})."
        for item in pending_reminders[:3]
    ]
    if not reminder_items:
        reminder_items = (
            [f"Completaste {_plural(len(done_reminders), 'recordatorio')}."] if done_reminders
            else ["Los recordatorios aparecerán cuando el agente revise tus postulaciones."]
        )

    practice_items = (
        [f"Reforzar: {skill}" for skill in missing_skills[:3]]
        if missing_skills else ["Repasar las habilidades clave destacadas en tus cartas."]
    )

    next_steps = [(app, app.next_step) for app in planned[:3]]
    next_steps_items = [
        f"{index}. {app.title}: {step}" for index, (app, step) in enumerate(next_steps, start=1)
    ]
    if not next_steps_items:
        next_steps_items = (
            ["Tus procesos terminaron: explora nuevas vacantes en el Agente de Vacantes."] if finished
            else ["Envía una postulación para recibir tu hoja de ruta."]
        )

    return {
        "id": "followup",
        "step": 4,
        "title": "Seguimiento",
        "full_title": "Seguimiento y próximos pasos",
        "subtitle": "Estados, recordatorios, refuerzo de brechas y hoja de ruta",
        "icon": "fa-chart-line",
        "status": stage_status,
        "status_label": _status_label(stage_status),
        "action_url": (
            reverse("followup") if submitted
            else (reverse("applications") if applications else reverse("home"))
        ),
        "action_label": (
            "Ver seguimiento" if submitted
            else ("Ver postulaciones" if applications else "Ir a Mi perfil")
        ),
        "summary": "Actualiza el estado de tus envíos, programa recordatorios y te avisa de cada cambio.",
        "headline_metric": (
            f"{_plural(len(active), 'activa')} · {_plural(len(pending_reminders), 'recordatorio')}"
            if submitted else "Sin postulaciones enviadas"
        ),
        "metrics": [
            {"label": "Activas", "value": str(len(active))},
            {"label": "Recordatorios", "value": str(len(pending_reminders))},
            {"label": "Cambios", "value": str(len(changes))},
        ],
        "nodes": [
            {
                "id": "followup-monitor",
                "step_label": "4.1",
                "title": "Estado de envíos",
                "caption": "Postulada → En revisión → Entrevista",
                "icon": "fa-inbox",
                "status": monitor_status,
                "status_label": _status_label(monitor_status),
                "badge": _plural(len(active), "activa"),
                "x": 12,
                "y": 50,
                "live_action": "Consolidando el estado y los cambios que registraste en tus postulaciones...",
                "what_did": (
                    f"Sigue {_plural(len(submitted), 'postulación enviada', 'postulaciones enviadas')} y "
                    f"registró {_plural(len(changes), 'cambio de estado', 'cambios de estado')}."
                    if submitted else "Cuando envíes una postulación, el agente seguirá su estado."
                ),
                "why_did": "Cada cambio que haces queda en el historial con su fecha y motivo, y te llega una notificación.",
                "items": active_items,
                "visual_items": [
                    {"label": label, "value": str(count), "tone": status_tones.get(label, "sky"),
                     "icon": "fa-paper-plane"}
                    for label, count in status_counts if count
                ] or [{"label": "Postulaciones enviadas", "value": "Sin envíos", "tone": "slate", "icon": "fa-inbox"}],
                "scene": {
                    "kind": "followup_radar",
                    "active_count": len(active),
                    "apps": [{"title": app.title, "company": app.company} for app in submitted[:3]],
                },
            },
            {
                "id": "followup-reminders",
                "step_label": "4.2A",
                "title": "Recordatorios",
                "caption": "Fechas clave",
                "icon": "fa-bell",
                "status": reminders_status,
                "status_label": _status_label(reminders_status),
                "badge": _plural(len(pending_reminders), "pendiente"),
                "x": 52,
                "y": 23,
                "live_action": "Programando recordatorios con fecha para cada postulación activa...",
                "what_did": (
                    f"Programó {_plural(len(reminders), 'recordatorio')}; "
                    f"{_plural(len(done_reminders), 'completado')}."
                    if reminders else "Programa recordatorios con fecha según el estado de cada postulación."
                ),
                "why_did": "Te mantiene atento a entrevistas, pruebas técnicas o novedades del proceso.",
                "items": reminder_items,
                "visual_items": [
                    {"label": item.title, "value": item.due_date.strftime("%d/%m/%Y"), "tone": "sky",
                     "icon": "fa-bell"}
                    for item in pending_reminders[:3]
                ] or [{"label": "Recordatorios", "value": "Sin pendientes", "tone": "slate", "icon": "fa-bell-slash"}],
                "scene": {
                    "kind": "followup_timeline",
                    "reminders": reminder_items[:3],
                },
            },
            {
                "id": "followup-practice",
                "step_label": "4.2B",
                "title": "Refuerzo",
                "caption": "Habilidades por cubrir",
                "icon": "fa-graduation-cap",
                "status": practice_status,
                "status_label": _status_label(practice_status),
                "badge": _plural(len(missing_skills), "foco", "focos") if missing_skills else "Repaso",
                "x": 52,
                "y": 77,
                "live_action": "Conectando los requisitos pendientes de tus vacantes con temas de estudio...",
                "what_did": (
                    "Tomó los requisitos que te faltan en tus postulaciones activas para tus recordatorios de estudio."
                    if missing_skills else "Revisa los requisitos de tus vacantes para proponerte qué repasar."
                ),
                "why_did": "Aprovechar la espera para practicar las brechas clave mejora tu preparación.",
                "items": practice_items,
                "visual_items": [
                    {"label": skill, "value": "Prioridad de estudio", "tone": "amber", "icon": "fa-book-open"}
                    for skill in (missing_skills[:3] or ["Repaso de proyectos en tu hoja de vida"])
                ],
                "scene": {
                    "kind": "followup_practice",
                    "topics": missing_skills[:3] or ["Repaso de entrevista", "Proyectos prácticos"],
                },
            },
            {
                "id": "followup-next",
                "step_label": "4.3",
                "title": "Próximos pasos",
                "caption": "Hoja de ruta",
                "icon": "fa-route",
                "status": next_status,
                "status_label": _status_label(next_status),
                "badge": _plural(len(next_steps), "acción", "acciones"),
                "x": 88,
                "y": 50,
                "live_action": "Definiendo el próximo paso concreto de cada postulación...",
                "what_did": (
                    f"Definió el próximo paso de "
                    f"{_plural(len(planned), 'postulación activa', 'postulaciones activas')}."
                    if planned else "Resume el siguiente paso concreto de cada postulación activa."
                ),
                "why_did": "Para que después de postular tengas siempre una ruta clara de acción.",
                "items": next_steps_items,
                "visual_items": [
                    {"label": f"{index}. {app.title}", "value": app.get_status_display(), "tone": "emerald",
                     "icon": "fa-route"}
                    for index, (app, _) in enumerate(next_steps, start=1)
                ] or [{"label": "Próximos pasos", "value": "Sin acciones pendientes", "tone": "slate",
                       "icon": "fa-route"}],
                "scene": {
                    "kind": "followup_roadmap",
                    "steps": [step for _, step in next_steps] or ["Explorar vacantes", "Actualizar tu perfil"],
                },
            },
        ],
        "edges": [
            {"from": "followup-monitor", "to": "followup-reminders", "label": "Fechas clave", "active": bool(submitted)},
            {"from": "followup-monitor", "to": "followup-practice", "label": "Por reforzar", "active": bool(submitted)},
            {"from": "followup-reminders", "to": "followup-next", "label": "Agenda activa", "active": bool(reminders)},
            {"from": "followup-practice", "to": "followup-next", "label": "Plan de mejora", "active": bool(planned)},
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
        if stage["status"] in ("in_progress", "completed"):
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
