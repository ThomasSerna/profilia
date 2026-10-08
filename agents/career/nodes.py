from typing import Literal

from .kev_assessment import assess_role_with_kev
from .state import CareerState
from .summary import add_assessment_summary


def choose_entry(state: CareerState) -> Literal["evaluate", "summarize"]:
    return (
        "summarize"
        if state["reused"]
        else "evaluate"
    )


def evaluate_roles_node(state: CareerState):
    assessments = [
        assess_role_with_kev(
            state["profile"],
            state["raw_text"],
            role,
        )
        for role in state["roles"]
    ]

    return {"assessments": assessments}


def summarize_roles_node(state: CareerState):
    return {
        "assessments": [
            add_assessment_summary(assessment)
            for assessment in state["assessments"]
        ]
    }