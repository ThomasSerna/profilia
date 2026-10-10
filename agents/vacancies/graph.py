from langgraph.graph import END, START, StateGraph

from agents.profile.schemas import ProfileData

from .nodes import ingest_vacancies_node, match_vacancies_node, normalize_vacancies_node
from .schemas import Preferences
from .state import VacancyState


builder = StateGraph(VacancyState)

builder.add_node("ingest", ingest_vacancies_node)
builder.add_node("normalize", normalize_vacancies_node)
builder.add_node("match", match_vacancies_node)

builder.add_edge(START, "ingest")
builder.add_edge("ingest", "normalize")
builder.add_edge("normalize", "match")
builder.add_edge("match", END)

vacancy_graph = builder.compile()


def run_vacancy_agent(profile: ProfileData, preferences: Preferences) -> dict:
    """Ejecuta el agente de vacantes y devuelve las coincidencias ordenadas."""
    result = vacancy_graph.invoke({
        "profile": profile,
        "preferences": preferences,
        "raw_vacancies": [],
        "vacancies": [],
        "skipped": [],
        "matches": [],
    })
    return {"matches": result["matches"], "skipped": result["skipped"]}
