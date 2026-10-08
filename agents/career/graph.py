from langgraph.graph import END, START, StateGraph

from .nodes import (
    evaluate_roles_node,
    summarize_roles_node,
)
from .state import CareerState


builder = StateGraph(CareerState)

builder.add_node(
    "evaluate",
    evaluate_roles_node,
)

builder.add_node(
    "summarize",
    summarize_roles_node,
)

builder.add_edge(START, "evaluate")

builder.add_edge(
    "evaluate",
    "summarize",
)

builder.add_edge(
    "summarize",
    END,
)

career_graph = builder.compile()
