"""Queue recovery, lease fencing and scope checks on isolated synthetic data."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.database.models import (
    AuditEvent,
    Document,
    PolicyDocument,
    ProcessingJob,
    User,
    utc_now_naive,
)
from app.jobs import processors
from app.jobs.queue import claim, finish
from app.jobs.worker import run_once
from app.validation import policy_extraction
from tests.test_profile_policy_flows import SyntheticModel
from tests.test_security import hashed_password, secured, sign_in

pytestmark = pytest.mark.security
__all__ = ["hashed_password", "secured"]


@pytest.fixture
def queued(secured, monkeypatch):
    monkeypatch.setenv("EDI_PROCESSING_MODE", "external")
    monkeypatch.setenv("LLM_PROVIDER", "disabled")
    monkeypatch.setattr(
        processors,
        "extract_structured_data",
        lambda **kwargs: (
            {"merchant": "مطعم تجريبي", "total": "$175.00", "expense_category": "meal"},
            "regex_fallback",
            True,
        ),
    )
    return secured


def upload(
    client, text="Receipt\nMerchant: Synthetic Cafe\nTotal: $175.00", policy=False
):
    response = client.post(
        "/policies/upload" if policy else "/documents/upload",
        files={
            "file": (
                "سياسة.txt" if policy else "إيصال.txt",
                text.encode("utf-8"),
                "text/plain",
            )
        },
    )
    assert response.status_code == 202, response.text
    return response.json()


def test_default_queue_persists_original_and_reopens_after_abandoned_claim(queued):
    client, sessions = queued
    sign_in(client)
    content = "إيصال تجريبي\nالمطعم: مطعم النيل\nالإجمالي: ١٧٥٫٥٠ جنيه"
    uploaded = upload(client, content)
    assert uploaded["processing_status"] == "queued"
    identifier, _ = claim(sessions)
    with sessions() as db:
        job = db.get(ProcessingJob, identifier)
        assert job.attempts == 1
        job.lease_until = utc_now_naive() - timedelta(seconds=1)
        db.commit()
    # Simulate reopening after process restart with a new engine/session factory.
    reopened = create_engine(
        sessions.kw["bind"].url, connect_args={"check_same_thread": False}
    )
    try:
        restarted = sessionmaker(bind=reopened, autoflush=False)
        assert run_once(restarted)
        assert not run_once(restarted)
    finally:
        reopened.dispose()
    with sessions() as db:
        doc = db.get(Document, uploaded["document_id"])
        assert doc.extracted_text == content
        assert doc.structured_data["merchant"] == "مطعم تجريبي"
        assert (
            doc.processing_status == "completed" and doc.review_status == "needs_review"
        )
        assert db.get(ProcessingJob, identifier).attempts == 2
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.document_id == doc.id,
                    AuditEvent.event_type == "processing_completed",
                )
            )
            == 1
        )
    assert (
        client.get(f"/documents/{uploaded['document_id']}/processing").json()["state"]
        == "completed"
    )


def test_only_one_concurrent_worker_claims_a_job_and_stale_worker_cannot_commit(queued):
    client, sessions = queued
    sign_in(client)
    uploaded = upload(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(sessions), range(2)))
    assert sum(result is not None for result in results) == 1
    identifier, old_token = next(result for result in results if result)
    with sessions() as db:
        db.get(ProcessingJob, identifier).lease_until = utc_now_naive() - timedelta(
            seconds=1
        )
        db.commit()
    assert run_once(sessions)
    with sessions() as db:
        assert db.get(ProcessingJob, identifier).state == "completed"
    with sessions() as stale:
        job = stale.get(ProcessingJob, identifier)
        stale.get(Document, uploaded["document_id"]).review_status = "approved"
        with pytest.raises(RuntimeError, match="lease"):
            finish(stale, job, old_token)
    with sessions() as db:
        assert db.get(Document, uploaded["document_id"]).review_status == "needs_review"


def test_retries_are_bounded_redacted_and_explicit_retry_reuses_job(queued, caplog):
    client, sessions = queued
    sign_in(client)
    uploaded = upload(client)
    handler = Mock(side_effect=RuntimeError("private-source-and-provider-marker"))
    for attempt in range(3):
        assert run_once(sessions, handler)
        with sessions() as db:
            job = db.get(ProcessingJob, uploaded["job_id"])
            assert job.attempts == attempt + 1
            assert job.state == ("failed" if attempt == 2 else "retry_wait")
            job.available_at = utc_now_naive() - timedelta(seconds=1)
            db.commit()
    assert not run_once(sessions, handler)
    assert "private-source-and-provider-marker" not in caplog.text
    path = f"/documents/{uploaded['document_id']}/processing"
    assert "private-source-and-provider-marker" not in client.get(path).text
    retried = client.post(path + "/retry")
    assert retried.status_code == 200
    assert retried.json()["job_id"] == uploaded["job_id"]
    assert retried.json()["attempts"] == 0
    assert run_once(sessions)
    assert client.get(path).json()["state"] == "completed"


def test_worker_rechecks_disabled_account_before_opening_original(queued, monkeypatch):
    client, sessions = queued
    sign_in(client)
    uploaded = upload(client)
    parser = Mock()
    monkeypatch.setattr(processors, "extract_text_isolated", parser)
    with sessions() as db:
        db.get(User, "alice").active = False
        db.commit()
    assert run_once(sessions)
    parser.assert_not_called()
    with sessions() as db:
        assert db.get(ProcessingJob, uploaded["job_id"]).state == "retry_wait"


def test_abandoned_final_attempt_becomes_failed_and_can_be_retried(queued):
    client, sessions = queued
    sign_in(client)
    uploaded = upload(client)
    identifier, _ = claim(sessions)
    with sessions() as db:
        job = db.get(ProcessingJob, identifier)
        job.attempts = job.max_attempts
        job.lease_until = utc_now_naive() - timedelta(seconds=1)
        db.commit()
    assert claim(sessions) is None
    with sessions() as db:
        assert db.get(ProcessingJob, identifier).state == "failed"
        assert db.get(Document, uploaded["document_id"]).processing_status == "failed"
    assert (
        client.post(
            f"/documents/{uploaded['document_id']}/processing/retry"
        ).status_code
        == 200
    )
    assert run_once(sessions)


def test_retry_cannot_reprocess_completed_legacy_document_without_job(queued):
    client, sessions = queued
    sign_in(client)
    uploaded = upload(client)
    assert run_once(sessions)
    with sessions() as db:
        db.delete(db.get(ProcessingJob, uploaded["job_id"]))
        db.commit()
    path = f"/documents/{uploaded['document_id']}/processing/retry"
    assert client.post(path).status_code == 409
    with sessions() as db:
        assert (
            db.get(Document, uploaded["document_id"]).processing_status == "completed"
        )
        db.get(Document, uploaded["document_id"]).processing_status = "failed"
        db.commit()
    assert client.post(path).status_code == 200
    assert run_once(sessions)


def test_job_status_and_retry_cannot_cross_owner_or_org(queued):
    client, _ = queued
    sign_in(client)
    uploaded = upload(client)
    sign_in(client, "bob")
    path = f"/documents/{uploaded['document_id']}/processing"
    assert client.get(path).status_code == 404
    assert client.post(path + "/retry").status_code == 404
    sign_in(client, "outsider")
    assert client.get(path).status_code == 404


def test_policy_job_extracts_all_candidates_without_approving_and_is_idempotent(
    queued, monkeypatch
):
    client, sessions = queued
    sign_in(client, "reviewer")
    monkeypatch.setattr(policy_extraction, "get_llm_provider", SyntheticModel)
    uploaded = upload(
        client,
        "Meals above $100 require manager approval.\nFor all expenses of $25 or more, receipts are required.",
        policy=True,
    )
    assert run_once(sessions)
    response = client.get(f"/policies/{uploaded['policy_id']}/rules").json()
    assert response["extraction_status"] == "completed"
    assert len(response["rules"]) == 2
    assert {r["approval_status"] for r in response["rules"]} == {"pending"}
    # A deliberate re-extraction is queued, preserves pending candidates and does not duplicate them.
    assert (
        client.post(f"/policies/{uploaded['policy_id']}/rules/extract-all").status_code
        == 200
    )
    assert run_once(sessions)
    assert (
        client.get(f"/policies/{uploaded['policy_id']}/rules").json()["total_rules"]
        == 2
    )
    with sessions() as db:
        assert db.get(PolicyDocument, uploaded["policy_id"]).extracted_text


def test_policy_model_wait_does_not_block_sqlite_account_writes(queued, monkeypatch):
    client, sessions = queued
    sign_in(client, "reviewer")
    entered, release = Event(), Event()

    class WaitingModel(SyntheticModel):
        def generate(self, prompt):
            entered.set()
            assert release.wait(timeout=10)
            return super().generate(prompt)

    monkeypatch.setattr(policy_extraction, "get_llm_provider", WaitingModel)
    uploaded = upload(client, "Meals above $100 require manager approval.", policy=True)
    writer = create_engine(sessions.kw["bind"].url, connect_args={"timeout": 0.2})
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(run_once, sessions)
            try:
                assert entered.wait(timeout=10)
                with sessionmaker(bind=writer)() as db:
                    db.get(User, "reviewer").display_name = "Concurrent account update"
                    db.commit()
                    assert (
                        db.get(PolicyDocument, uploaded["policy_id"]).extracted_text
                        is None
                    )
            finally:
                release.set()
            assert running.result(timeout=10)
        assert (
            client.get(f"/policies/{uploaded['policy_id']}/processing").json()["state"]
            == "completed"
        )
    finally:
        writer.dispose()
