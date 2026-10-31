"""Checkpointed specialist coordination; authority is freshly reloaded at every boundary."""

import hashlib
import json
import time
from typing import TypedDict

from fastapi import HTTPException
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from sqlalchemy import select

from app.agents.tools.document_tools import inspect_document
from app.agents.tools.evaluation_tools import evaluate_document_policy
from app.agents.tools.policy_tools import get_policy_evidence
from app.auth.security import Principal, require_document, require_policy
from app.database.models import HumanReview, User
from app.observability.tracing import traced
from app.rag.search import search_evidence
from app.review.documentation import documentation_checklist
from app.review.eligibility import document_eligibility
from app.specialists import agents
from app.validation.approved_rule_repository import load_approved_rules


class SpecialistState(TypedDict, total=False):
    document_id: str
    policy_id: str
    question: str
    status: str
    reason: str
    document_agent: dict
    policy_agent: dict
    evaluation: dict
    documentation: dict
    trace: list[dict]
    model_calls: int
    document_fingerprint: str
    document_review_id: int | None
    review_requested_at: int | None
    source_candidates: list[dict]
    policy_fingerprint: str
    document_context: dict


def policy_fingerprint(db, policy_id):
    return hashlib.sha256(
        json.dumps(
            [
                rule.model_dump(mode="json")
                for rule in load_approved_rules(db, policy_id)
            ],
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def current_scope(db, actor_id, document_id, policy_id):
    user = db.get(User, actor_id)
    if user is None or not user.active:
        raise HTTPException(404, "Workflow resources unavailable.")
    actor = Principal(user.id, user.organization_id, user.role)
    document = require_document(db, document_id, actor)
    require_policy(db, policy_id, actor)
    return actor, document


def document_fingerprint(document):
    values = {
        "data": document.structured_data,
        "hash": document.file_hash,
        "type": document.document_type,
        "review": document.review_status,
        "method": document.structured_extraction_method,
        "processing": document.processing_status,
    }
    return hashlib.sha256(
        json.dumps(values, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def build_graph(checkpointer, *, sessions, actor_id, deadline, client_factory=None):
    factory = client_factory or agents.client_factory

    def checked(state):
        db = sessions()
        try:
            actor, document = current_scope(
                db, actor_id, state["document_id"], state["policy_id"]
            )
            return db, actor, document
        except Exception:
            db.close()
            raise

    def event(state, node, status):
        trace = state.get("trace", [])
        if len(trace) >= 64:
            raise ValueError("Workflow transition budget exceeded.")
        return trace + [{"node": node, "status": status}]

    def dispatch(state, name, args):
        db, actor, _ = checked(state)
        with db:
            if name == "inspect_document":
                return inspect_document(args["document_id"], {state["document_id"]}, db)
            if name == "get_policy_evidence":
                return get_policy_evidence(args["policy_id"], {state["policy_id"]}, db)
            if name == "search_policy_sources":
                result = search_evidence(
                    db, actor, args["query"], policy_ids=[state["policy_id"]], limit=3
                )
                # Source candidates never replace the complete approved-rule evaluation.
                return result
        raise ValueError("Unknown specialist tool.")

    def run_agent(state, role):
        calls = state.get("model_calls", 0)
        client = factory() if calls < 8 and time.monotonic() < deadline else None
        try:
            result = agents.specialist(
                role,
                state["question"],
                state["document_id"],
                state["policy_id"],
                lambda name, args: dispatch(state, name, args),
                deadline=deadline,
                client=client,
                remaining_calls=min(3, 8 - calls),
                document_context=state.get("document_context")
                if role == "policy"
                else None,
            )
        finally:
            if client is not None:
                client.close()
        if calls >= 8:
            result["mode"], result["reason"] = (
                "budget_exhausted",
                "Model-call budget exhausted; canonical evaluation is independent.",
            )
        return result

    @traced("workflow.document")
    def document_node(state):
        db, _, document = checked(state)
        with db:
            decision, reason = document_eligibility(
                processing_status=document.processing_status,
                review_status=document.review_status,
                extraction_method=document.structured_extraction_method,
                structured_data=document.structured_data,
                document_type=document.document_type,
            )
            revision = db.scalar(
                select(HumanReview.id)
                .where(HumanReview.document_id == document.id)
                .order_by(HumanReview.id.desc())
                .limit(1)
            )
            digest = document_fingerprint(document)
            fields = (
                document.structured_data
                if isinstance(document.structured_data, dict)
                else {}
            )
            context = {
                "document_type": document.document_type,
                **{key: fields.get(key) for key in ("expense_category", "total")},
            }
            if len(json.dumps(context, ensure_ascii=False)) > 2048:
                return {
                    "status": "blocked",
                    "reason": "Reviewed context exceeds the specialist input budget.",
                    "trace": event(state, "document_specialist", "context_budget"),
                }
            if decision != "ready":
                status = (
                    "waiting_for_document_review"
                    if decision == "needs_review"
                    else "blocked"
                )
                return {
                    "status": status,
                    "reason": reason,
                    "document_review_id": revision,
                    "trace": event(state, "document_specialist", status),
                }
        result = run_agent(state, "document")
        # A model can request review but cannot clear a canonical quality failure.
        requested = result["mode"] == "gemini" and result["decision"] != "ready"
        acknowledged = (
            revision is not None
            and state.get("review_requested_at") is not None
            and revision != state.get("review_requested_at")
        )
        status = (
            "waiting_for_document_review"
            if requested and not acknowledged
            else "document_ready"
        )
        if result["mode"] in {
            "blocked_tool",
            "invalid_response",
            "tool_limit",
            "deadline",
        }:
            status = "blocked"
        return {
            "document_agent": result,
            "model_calls": state.get("model_calls", 0) + result["calls"],
            "status": status,
            "document_review_id": revision,
            "document_fingerprint": digest,
            "document_context": context,
            "reason": "Review reviewed fields again before resuming."
            if requested
            else "Canonical document eligibility checked.",
            "trace": event(state, "document_specialist", status),
        }

    @traced("workflow.policy")
    def policy_node(state):
        db, _, _ = checked(state)
        with db:
            canonical = get_policy_evidence(
                state["policy_id"], {state["policy_id"]}, db
            )
        result = run_agent(state, "policy")
        status = (
            "waiting_for_policy_review"
            if canonical["status"] != "ready"
            or (result["mode"] == "gemini" and result["decision"] != "ready")
            else "policy_ready"
        )
        if result["mode"] in {
            "blocked_tool",
            "invalid_response",
            "tool_limit",
            "deadline",
        }:
            status = "blocked"
        return {
            "policy_agent": result,
            "model_calls": state.get("model_calls", 0) + result["calls"],
            "status": status,
            "reason": "Verified approved policy evidence must be available; research cannot approve it.",
            "trace": event(state, "policy_specialist", status),
        }

    @traced("workflow.evaluate")
    def evaluate_node(state):
        db, actor, document = checked(state)
        with db:
            if document_fingerprint(document) != state.get("document_fingerprint"):
                return {
                    "status": "waiting_for_document_review",
                    "evaluation": {},
                    "reason": "Document changed during investigation; review current evidence.",
                    "trace": event(state, "deterministic_evaluator", "source_changed"),
                }
            result = evaluate_document_policy(
                document.id, state["policy_id"], {document.id}, {state["policy_id"]}, db
            )
            if "evaluation" not in result:
                return {
                    "status": "waiting_for_policy_review",
                    "evaluation": {},
                    "reason": "Current canonical evidence is not ready.",
                    "trace": event(state, "deterministic_evaluator", "needs_review"),
                }
            if len(json.dumps(result, ensure_ascii=False, default=str)) > 60000:
                return {
                    "status": "blocked",
                    "reason": "Approved result exceeds workflow output budget; inspect the policy manually.",
                    "trace": event(state, "deterministic_evaluator", "budget_exceeded"),
                }
            checklist = documentation_checklist(
                db, actor, document.id, state["policy_id"]
            )
            policy_digest = policy_fingerprint(db, state["policy_id"])
        unresolved = any(
            item["status"] != "reviewed_satisfied" for item in checklist["requirements"]
        )
        status = "waiting_for_documentation" if unresolved else "completed"
        if result["status"] == "needs_review":
            status = (
                "waiting_for_document_review"
                if result["evaluation"].get("applicable_rules", 0)
                else "waiting_for_policy_review"
            )
        return {
            "evaluation": result,
            "policy_fingerprint": policy_digest,
            "documentation": checklist,
            "status": status,
            "reason": "Evaluation covers approved rules only; no expense approval is granted.",
            "trace": event(state, "deterministic_evaluator", status),
        }

    def pause(state):
        db, _, _ = checked(state)
        db.close()
        interrupt(
            {
                "type": state["status"],
                "document_id": state["document_id"],
                "policy_id": state["policy_id"],
                "message": state.get("reason"),
                "documentation": state.get("documentation", {}),
            }
        )
        # Only the external review APIs can change canonical decisions.
        return {
            "review_requested_at": state.get("document_review_id") or 0,
            "trace": event(state, "human_review", "resume_requested"),
        }

    graph = StateGraph(SpecialistState)
    graph.add_node("document_specialist", document_node)
    graph.add_node("policy_specialist", policy_node)
    graph.add_node("deterministic_evaluator", evaluate_node)
    graph.add_node("human_review", pause)
    graph.add_edge(START, "document_specialist")
    graph.add_conditional_edges(
        "document_specialist",
        lambda state: (
            "human_review"
            if state["status"].startswith("waiting_")
            else END
            if state["status"] == "blocked"
            else "policy_specialist"
        ),
    )
    graph.add_conditional_edges(
        "policy_specialist",
        lambda state: (
            "human_review"
            if state["status"].startswith("waiting_")
            else END
            if state["status"] == "blocked"
            else "deterministic_evaluator"
        ),
    )
    graph.add_conditional_edges(
        "deterministic_evaluator",
        lambda state: "human_review" if state["status"].startswith("waiting_") else END,
    )
    graph.add_edge("human_review", "document_specialist")
    return graph.compile(checkpointer=checkpointer)
