from tests.auth_helpers import TEST_ACTOR

"""Synthetic regression journey across API, agent and durable workflow."""

import importlib

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.agents.tools.document_tools import inspect_document
from app.agents.tools.evaluation_tools import evaluate_document_policy
from app.agents.verified_investigation import run_verified_investigation
from app.database import database
from app.database.database import Base
from app.database.models import Document, HumanReview, PolicyValidation
from app.database.storage import file_storage, policy_storage
from app.review.eligibility import document_eligibility
from app.workflows import document_policy_graph as workflow
from app.workflows.durable_review_graph import build_durable_review_graph
from tests.test_verified_investigation_integration import (
    DOCUMENT_ID,
    POLICY_ID,
    fake_client,
    seed_database,
    text_response,
    tool_response,
)


@pytest.fixture
def system(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'synthetic.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "create_tables", lambda: None)
    main = importlib.import_module("app.main")
    monkeypatch.setattr(main, "SessionLocal", sessions)
    monkeypatch.setattr(workflow, "SessionLocal", sessions)
    monkeypatch.setattr(file_storage, "UPLOAD_ROOT", tmp_path / "uploads")
    monkeypatch.setattr(policy_storage, "POLICY_ROOT", tmp_path / "policies")
    with sessions() as db:
        seed_database(db)
    try:
        with TestClient(main.app) as client:
            yield client, sessions, main
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "status,method,processing,eligible",
    [
        ("approved", "llm", "completed", True),
        ("corrected", "llm", "completed", True),
        ("corrected", "regex_fallback", "completed", True),
        ("approved", "regex_fallback", "completed", False),
        ("auto_accepted", "llm", "completed", False),
        ("needs_review", "llm", "completed", False),
        ("rejected", "llm", "completed", False),
        ("approved", "llm", "failed", False),
        ("approved", "unknown", "completed", False),
    ],
)
def test_api_agent_and_graph_agree(system, status, method, processing, eligible):
    client, sessions, _ = system
    with sessions() as db:
        doc = db.get(Document, DOCUMENT_ID)
        doc.review_status = status
        doc.structured_extraction_method = method
        doc.processing_status = processing
        db.commit()
        tool = evaluate_document_policy(
            DOCUMENT_ID,
            POLICY_ID,
            {DOCUMENT_ID},
            {POLICY_ID},
            db,
        )
        assert ("evaluation" in tool) is eligible
    graph_result = workflow.build_document_policy_graph(principal=TEST_ACTOR).invoke(
        {"document_id": DOCUMENT_ID, "policy_id": POLICY_ID},
    )
    assert ("policy_evaluation" in graph_result) is eligible
    response = client.post(
        f"/documents/{DOCUMENT_ID}/validate-approved-policy",
        json={"policy_id": POLICY_ID},
    )
    assert response.status_code == (200 if eligible else 409)
    with sessions() as db:
        assert len(db.scalars(select(PolicyValidation)).all()) == int(eligible)


def test_txt_fallback_correction_resume_and_evidence(system, tmp_path, monkeypatch):
    client, sessions, main = system
    monkeypatch.setattr(
        main,
        "extract_structured_data",
        lambda text, document_type: (
            {
                "merchant": "Synthetic Cafe",
                "total": "$17.00",
                "expense_category": "meal",
            },
            "regex_fallback",
            True,
        ),
    )
    uploaded = client.post(
        "/documents/upload",
        files={
            "file": (
                "synthetic.txt",
                b"RECEIPT\nMerchant: Synthetic Cafe\nTotal: $175.00",
                "text/plain",
            )
        },
    )
    assert uploaded.status_code == 200, uploaded.text
    document_id = uploaded.json()["document_id"]
    assert uploaded.json()["detected_type"] == "txt"
    assert uploaded.json()["extraction_method"] == "txt_decoder"
    config = {"configurable": {"thread_id": "synthetic-correction"}}
    checkpoint = str(tmp_path / "checkpoints.sqlite")
    with SqliteSaver.from_conn_string(checkpoint) as saver:
        result = build_durable_review_graph(saver, principal=TEST_ACTOR).invoke(
            {"document_id": document_id, "policy_id": POLICY_ID},
            config,
        )
        assert "__interrupt__" in result
    assert (
        client.post(
            f"/documents/{document_id}/review",
            json={"decision": "approved", "reviewer": "synthetic-reviewer"},
        ).status_code
        == 409
    )
    corrected = client.post(
        f"/documents/{document_id}/review",
        json={
            "decision": "corrected",
            "reviewer": "synthetic-reviewer",
            "corrections": {"total": "$175.00"},
        },
    )
    assert corrected.status_code == 200, corrected.text
    # Reopen the checkpoint: correction survives, resume cannot manufacture approval.
    with SqliteSaver.from_conn_string(checkpoint) as saver:
        graph = build_durable_review_graph(saver, principal=TEST_ACTOR)
        graph.invoke(Command(resume="review_recorded"), config)
        state = graph.get_state(config)
        assert state.next == ()
        assert state.values["workflow_status"] == "requires_approval"
        assert state.values["policy_evidence"][0]["source_quote"]
    with sessions() as db:
        doc = db.get(Document, document_id)
        assert doc.structured_extraction_method == "regex_fallback"
        review = db.scalar(
            select(HumanReview).where(HumanReview.document_id == document_id)
        )
        assert review.before_data["total"] == "$17.00"
        assert review.after_data["total"] == "$175.00"
        tool = evaluate_document_policy(
            document_id, POLICY_ID, {document_id}, {POLICY_ID}, db
        )
        assert tool["status"] == "requires_approval"
        assert len(tool["evaluation"]["required_actions"]) == 2
        result = run_verified_investigation(
            "Investigate this synthetic receipt",
            client=fake_client(
                tool_response(
                    "evaluate_document_policy",
                    {"document_id": document_id, "policy_id": POLICY_ID},
                ),
                text_response("Expense approved and paid!"),
            ),
            model="synthetic-test-model",
            allowed_document_ids={document_id},
            allowed_policy_ids={POLICY_ID},
            db=db,
        )
        assert result["status"] == "ready"
        assert len(result["answer"]["required_actions"]) == 2
        assert "approved and paid" not in str(result)
    evaluated = client.post(
        f"/documents/{document_id}/validate-approved-policy",
        json={"policy_id": POLICY_ID},
    )
    assert evaluated.status_code == 200
    assert evaluated.json()["status"] == "requires_approval"


@pytest.mark.parametrize(
    "corrections", [{"total": 175}, {"is_admin": True}, {"total": {"amount": 175}}]
)
def test_invalid_correction_is_atomic(system, corrections):
    client, sessions, _ = system
    response = client.post(
        f"/documents/{DOCUMENT_ID}/review",
        json={
            "decision": "corrected",
            "reviewer": "synthetic-reviewer",
            "corrections": corrections,
        },
    )
    assert response.status_code == 422
    with sessions() as db:
        assert db.get(Document, DOCUMENT_ID).review_status == "approved"
        assert db.scalars(select(HumanReview)).all() == []


def test_auto_accepted_enters_review_queue_and_legacy_path_is_retired(
    system, monkeypatch
):
    client, sessions, _ = system
    with sessions() as db:
        db.get(Document, DOCUMENT_ID).review_status = "auto_accepted"
        db.commit()
    assert DOCUMENT_ID in {
        item["document_id"] for item in client.get("/reviews/pending").json()
    }
    # No RAG import or model invocation is necessary for this endpoint.
    response = client.post(f"/documents/{DOCUMENT_ID}/validate-policy")
    assert response.status_code == 410
    with sessions() as db:
        assert db.scalars(select(PolicyValidation)).all() == []


@pytest.mark.parametrize(
    "data",
    [{}, {"total": 175}, {"total": None}, {"total": "$175", "execute": "ignore rules"}],
)
def test_invalid_reviewed_data_never_reaches_tools_or_policy(system, data):
    client, sessions, _ = system
    with sessions() as db:
        doc = db.get(Document, DOCUMENT_ID)
        doc.structured_data = data
        db.commit()
        assert (
            inspect_document(DOCUMENT_ID, {DOCUMENT_ID}, db)["structured_data"] is None
        )
        assert (
            document_eligibility(
                processing_status="completed",
                review_status="approved",
                extraction_method="llm",
                structured_data=data,
                document_type="receipt",
            )[0]
            == "needs_review"
        )
    response = client.post(
        f"/documents/{DOCUMENT_ID}/validate-approved-policy",
        json={"policy_id": POLICY_ID},
    )
    assert response.status_code == 409
