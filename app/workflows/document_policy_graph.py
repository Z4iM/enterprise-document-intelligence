
from functools import partial
from typing import Literal, TypedDict

from fastapi import HTTPException
from langgraph.graph import END, START, StateGraph

from app.auth.security import Principal, require_document, require_policy
from app.database.database import SessionLocal
from app.review.eligibility import document_eligibility
from app.validation.approved_rule_repository import (
    PolicyRuleIntegrityError,
    load_approved_rules,
)
from app.validation.evaluation_service import evaluate_verified_rules


class WorkflowState(TypedDict, total=False):
    document_id: str
    policy_id: str

    document_type: str | None
    document_found: bool
    processing_status: str | None
    review_status: str | None
    extraction_method: str | None
    structured_data: dict | None
    policy_evaluation: dict | None
    policy_evidence: list[dict]

    decision: Literal["ready", "needs_review", "blocked"]
    workflow_status: str
    reason: str


def load_document(state: WorkflowState, *, principal: Principal | None = None) -> dict:
    """Load an existing document without changing the database."""

    if principal is None:
        return {"document_found": False}

    document_id = state.get("document_id")

    if not isinstance(document_id, str) or not document_id.strip():
        return {"document_found": False}

    with SessionLocal() as db:
        try:
            document = require_document(db, document_id, principal)
        except HTTPException:
            return {"document_found": False}

        if document is None:
            return {"document_found": False}

        return {
            "document_found": True,
            "document_type": document.document_type,
            "processing_status": document.processing_status,
            "review_status": document.review_status,
            "extraction_method": document.structured_extraction_method,
            "structured_data": document.structured_data,
        }


def quality_gate(state: WorkflowState) -> dict:
    """Prevent unverified document data from reaching policy evaluation."""

    if not state.get("document_found"):
        return {
            "decision": "blocked",
            "reason": "Document not found.",
        }

    decision, reason = document_eligibility(
        processing_status=state.get("processing_status"),
        review_status=state.get("review_status"),
        extraction_method=state.get("extraction_method"),
        structured_data=state.get("structured_data"),
        document_type=state.get("document_type"),
    )
    if decision != "ready":
        return {"decision": decision, "reason": reason}

    if not state.get("policy_id"):
        return {
            "decision": "blocked",
            "reason": "No policy was selected.",
        }

    return {
        "decision": "ready",
        "reason": "Document passed the initial quality gate.",
    }


def route_document(state: WorkflowState) -> str:
    """Choose the next node based on the quality-gate decision."""

    if state["decision"] == "ready":
        return "ready_for_policy"

    return "stop"


def mark_ready(state: WorkflowState) -> dict:
    return {
        "workflow_status": "ready_for_policy_evaluation",
    }


def mark_stopped(state: WorkflowState) -> dict:
    return {
        "workflow_status": state["decision"],
    }


def build_document_quality_graph(*, principal: Principal | None = None):
    """Compile the initial LangGraph document workflow."""

    graph = StateGraph(WorkflowState)

    graph.add_node("load_document", partial(load_document, principal=principal))
    graph.add_node("quality_gate", quality_gate)
    graph.add_node("ready_for_policy", mark_ready)
    graph.add_node("stop", mark_stopped)

    graph.add_edge(START, "load_document")
    graph.add_edge("load_document", "quality_gate")

    graph.add_conditional_edges(
        "quality_gate",
        route_document,
        {
            "ready_for_policy": "ready_for_policy",
            "stop": "stop",
        },
    )

    graph.add_edge("ready_for_policy", END)
    graph.add_edge("stop", END)

    return graph.compile()

def evaluate_approved_policy(state: WorkflowState, *, principal: Principal | None = None) -> dict:
    """
    Evaluate verified, approved policy rules.

    This node is read-only and must only run after
    the document passes the quality gate.
    """

    if principal is None or state.get("decision") != "ready":
        return {
            "workflow_status": "blocked",
            "reason": "Document has not passed the quality gate.",
        }

    policy_id = state.get("policy_id")
    document_data = state.get("structured_data")

    if not isinstance(policy_id, str) or not policy_id.strip():
        return {
            "workflow_status": "blocked",
            "reason": "No valid policy was selected.",
        }

    if not isinstance(document_data, dict) or not document_data:
        return {
            "workflow_status": "needs_review",
            "reason": "Structured document data is unavailable.",
        }

    with SessionLocal() as db:
        try:
            require_document(db, state.get("document_id"), principal)
            policy = require_policy(db, policy_id, principal)
        except HTTPException:
            return {"workflow_status": "blocked", "reason": "Resource access denied."}

        if policy is None:
            return {
                "workflow_status": "blocked",
                "reason": "Selected policy was not found.",
            }

        try:
            rules = load_approved_rules(
                db=db,
                policy_id=policy_id,
            )
        except PolicyRuleIntegrityError:
            return {
                "workflow_status": "needs_review",
                "reason": "Approved policy evidence requires review.",
            }

        evaluation = evaluate_verified_rules(
            document_data=document_data,
            approved_rules=rules,
        )

        evidence = [
            {
                "policy_id": policy_id,
                "rule_id": rule.rule_id,
                "chunk_id": rule.source_chunk_id,
                "source_quote": rule.source_quote,
            }
            for rule in rules
        ]

    return {
        "workflow_status": evaluation["status"],
        "policy_evaluation": evaluation,
        "policy_evidence": evidence,
        "reason": (
            "Only the approved policy rule subset was evaluated. "
            "Full policy compliance is not certified."
        ),
    }

def build_document_policy_graph(checkpointer=None, *, principal: Principal | None = None):
    """
    Build the read-only, evidence-backed policy workflow.

    The original quality-only graph remains available
    for isolated routing tests.
    """

    graph = StateGraph(WorkflowState)

    graph.add_node("load_document", partial(load_document, principal=principal))
    graph.add_node("quality_gate", quality_gate)
    graph.add_node(
        "evaluate_approved_policy",
        partial(evaluate_approved_policy, principal=principal),
    )
    graph.add_node("stop", mark_stopped)

    graph.add_edge(START, "load_document")
    graph.add_edge("load_document", "quality_gate")

    graph.add_conditional_edges(
        "quality_gate",
        route_document,
        {
            "ready_for_policy": "evaluate_approved_policy",
            "stop": "stop",
        },
    )

    graph.add_edge("evaluate_approved_policy", END)
    graph.add_edge("stop", END)

    return graph.compile(checkpointer=checkpointer)
