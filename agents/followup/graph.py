from datetime import datetime, timezone

from langgraph.graph import END, START, StateGraph

from agents.profile.schemas import ProfileData

from .nodes import monitor_node, notify_node, plan_reminders_node, review_status_node
from .schemas import StatusChange, TrackedApplication
from .state import FollowupState


builder = StateGraph(FollowupState)

builder.add_node("monitor", monitor_node)
builder.add_node("review", review_status_node)
builder.add_node("plan", plan_reminders_node)
builder.add_node("notify", notify_node)

builder.add_edge(START, "monitor")
builder.add_edge("monitor", "review")
builder.add_edge("review", "plan")
builder.add_edge("plan", "notify")
builder.add_edge("notify", END)

followup_graph = builder.compile()


def run_followup_agent(applications: list[TrackedApplication], changes: list[StatusChange] | None = None,
                       profile: ProfileData | None = None, now: datetime | None = None) -> dict:
    """Hace seguimiento a las postulaciones enviadas (evento POSTULACIÓN ENVIADA).

    No cambia estados: recibe los cambios que registró el usuario (evento ESTADO CAMBIADO) y
    prepara su notificación, además del próximo paso y los recordatorios de cada postulación
    activa. No escribe en la base de datos: la vista persiste el resultado. `profile` solo se
    usa para redactar datos de contacto antes de llamar al LLM.
    """
    result = followup_graph.invoke({
        "applications": list(applications),
        "changes": list(changes or []),
        "profile": profile or ProfileData(),
        "now": now or datetime.now(timezone.utc),
        "plans": [],
        "notifications": [],
        "events": [],
        "inference_runs": [],
    })
    return {
        "plans": result["plans"],
        "notifications": result["notifications"],
        "events": result["events"],
        "inference_runs": result["inference_runs"],
    }
