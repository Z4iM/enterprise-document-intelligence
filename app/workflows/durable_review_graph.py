
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.workflows.document_policy_graph import (
    WorkflowState,
    evaluate_approved_policy,
    load_document,
    mark_stopped,
    quality_gate,
)


def wait_for_human_review(state: WorkflowState) -> dict:
    """
    Pause workflow until an external review is recorded.

    A resume signal is NOT proof of approval.
    The graph must reload the actual database record.
    """

    interrupt(
        {
            "type": "document_review_required",
            "document_id": state["document_id"],
            "reason": state.get("reason"),
            "message": (
                "Review the document through the EDI "
                "human-review API before resuming."
            ),
        }
    )

    return {
        "reason": (
            "Resume requested. Reloading document "
            "to verify its actual review status."
        ),
    }


def route_after_quality(
    state: WorkflowState,
) -> Literal["evaluate", "review", "stop"]:

    decision = state.get("decision")

    if decision == "ready":
        return "evaluate"

    if decision == "needs_review":
        return "review"

    return "stop"


def build_durable_review_graph(checkpointer):
    """
    Build a checkpointed workflow with human review.

    The checkpointer is required for durable interrupts.
    """

    graph = StateGraph(WorkflowState)

    graph.add_node("load_document", load_document)
    graph.add_node("quality_gate", quality_gate)
    graph.add_node(
        "wait_for_human_review",
        wait_for_human_review,
    )
    graph.add_node(
        "evaluate_approved_policy",
        evaluate_approved_policy,
    )
    graph.add_node("stop", mark_stopped)

    graph.add_edge(START, "load_document")
    graph.add_edge("load_document", "quality_gate")

    graph.add_conditional_edges(
        "quality_gate",
        route_after_quality,
        {
            "evaluate": "evaluate_approved_policy",
            "review": "wait_for_human_review",
            "stop": "stop",
        },
    )

    # After resuming, always fetch the latest DB record.
    graph.add_edge(
        "wait_for_human_review",
        "load_document",
    )

    graph.add_edge("evaluate_approved_policy", END)
    graph.add_edge("stop", END)

    return graph.compile(checkpointer=checkpointer)
