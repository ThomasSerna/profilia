from langgraph.graph import END, START, StateGraph

from agents.profile.schemas import ProfileData
from agents.vacancies.schemas import Preferences

from .nodes import (
    answer_screening_node,
    draft_letters_node,
    resolve_vacancies_node,
    submit_applications_node,
)
from .state import ApplicationState


builder = StateGraph(ApplicationState)

builder.add_node("resolve", resolve_vacancies_node)
builder.add_node("draft_letters", draft_letters_node)
builder.add_node("screening", answer_screening_node)
builder.add_node("submit", submit_applications_node)

builder.add_edge(START, "resolve")
builder.add_edge("resolve", "draft_letters")
builder.add_edge("draft_letters", "screening")
builder.add_edge("screening", "submit")
builder.add_edge("submit", END)

application_graph = builder.compile()


def run_application_agent(profile: ProfileData, preferences: Preferences,
                          clarifications: dict | None = None, selected_roles: list[str] | None = None,
                          skill_results: dict | None = None, selected_ids: list[str] | None = None,
                          user_name: str = "") -> dict:
    """Prepara y registra (de forma simulada) las postulaciones a las vacantes seleccionadas.

    Recibe lo mismo que el agente de vacantes (perfil, preferencias, aclaraciones, cargos
    elegidos e inferencias de Kev) más los ids de las vacantes confirmadas por el usuario.
    """
    result = application_graph.invoke({
        "profile": profile,
        "preferences": preferences,
        "clarifications": clarifications or {},
        "skill_results": skill_results or {},
        "selected_roles": selected_roles or [],
        "selected_ids": selected_ids or [],
        "user_name": user_name,
        "vacancies": [],
        "matches": [],
        "letters": {},
        "screening": {},
        "packages": [],
        "skipped": [],
        "events": [],
        "inference_runs": [],
    })
    return {
        "packages": result["packages"],
        "skipped": result["skipped"],
        "events": result["events"],
        "inference_runs": result["inference_runs"],
    }
