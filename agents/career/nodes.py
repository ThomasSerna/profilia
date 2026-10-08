from .kev_assessment import assess_roles_with_kev
from .llm import build_recommendation_key, generate_recommendation
from .state import CareerState


def evaluate_roles_node(state: CareerState):
    skill_results, assessments, inference_runs = assess_roles_with_kev(
        state["profile"],
        state["raw_text"],
        state["roles"],
        state["skill_results"],
        state["clarifications"],
    )
    return {
        "skill_results": skill_results,
        "assessments": assessments,
        "inference_runs": inference_runs,
    }


def summarize_roles_node(state: CareerState):
    assessments = []
    inference_runs = list(state["inference_runs"])
    for role, assessment in zip(state["roles"], state["assessments"], strict=True):
        key = build_recommendation_key(
            state["profile"], role, assessment, state["clarifications"]
        )
        assessment = assessment.model_copy(update={"recommendation_key": key})
        cached = state["cached_assessments"].get(role.name)
        if cached is not None and cached.recommendation_key == key:
            assessment = assessment.model_copy(update={
                "recommendation": cached.recommendation,
                "recommendation_status": cached.recommendation_status,
                "recommendation_source": cached.recommendation_source,
            })

        needs_recommendation = (
            assessment.group == "medium"
            and state["generate_recommendations"]
            and (
                assessment.recommendation_status == "not_requested"
                or (assessment.recommendation_status == "pending" and state["retry_recommendation"])
            )
        )
        if needs_recommendation:
            assessment, run = generate_recommendation(
                state["profile"], role, assessment, state["clarifications"]
            )
            inference_runs.append(run)
        assessments.append(assessment)

    return {
        "assessments": assessments,
        "inference_runs": inference_runs,
    }
