from langgraph.graph import StateGraph, START, END

from .nodes import extract_pdf_node, extract_profile_node
from .state import ProfileState


builder = StateGraph(ProfileState)

builder.add_node("extract_pdf", extract_pdf_node)
builder.add_node("extract_profile", extract_profile_node)

builder.add_edge(START, "extract_pdf")
builder.add_edge("extract_pdf", "extract_profile")
builder.add_edge("extract_profile", END)

profile_graph = builder.compile()