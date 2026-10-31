"""Synthetic usage, trace linkage, privacy, failure isolation and organization boundaries."""

import json
import logging
import uuid
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import select

from app.auth.security import Principal
from app.database.models import ProcessingJob, TelemetrySpan, utc_now_naive
from app.jobs.queue import enqueue
from app.jobs.worker import run_once
from app.observability.tracing import (
    MAX_SPANS,
    SafeJSONFormatter,
    collection,
    generate_content,
    persist,
    reported_usage,
    span,
    trace_id,
)
from tests.test_security import hashed_password, secured, sign_in

__all__ = ["hashed_password", "secured"]
pytestmark = pytest.mark.security


@pytest.fixture(autouse=True)
def recording(monkeypatch):
    monkeypatch.setenv("EDI_TELEMETRY_ENABLED", "true")


def usage(**changes):
    values = {
        "prompt_token_count": 1000,
        "candidates_token_count": 100,
        "thoughts_token_count": 20,
        "cached_content_token_count": 0,
        "tool_use_prompt_token_count": 10,
        "total_token_count": 1130,
    }
    values.update(changes)
    return SimpleNamespace(usage_metadata=SimpleNamespace(**values))


@pytest.fixture
def prices(monkeypatch):
    monkeypatch.setenv("EDI_LLM_PRICING_MODEL", "synthetic-model")
    monkeypatch.setenv("EDI_LLM_INPUT_USD_PER_MILLION", "1")
    monkeypatch.setenv("EDI_LLM_OUTPUT_USD_PER_MILLION", "2")
    monkeypatch.delenv("EDI_LLM_CACHED_INPUT_USD_PER_MILLION", raising=False)


def test_provider_usage_counts_thoughts_tool_prompt_and_cache_without_zero_guessing(
    prices, monkeypatch
):
    measured = reported_usage(usage(), "synthetic-model")
    assert measured["estimated_usd"] == pytest.approx(0.00125)
    assert "estimated_usd" not in reported_usage(
        usage(thoughts_token_count=None), "synthetic-model"
    )
    assert "estimated_usd" not in reported_usage(
        usage(total_token_count=999), "synthetic-model"
    )
    assert "estimated_usd" not in reported_usage(usage(), "wrong-model")
    assert "estimated_usd" not in reported_usage(
        usage(cached_content_token_count=500), "synthetic-model"
    )
    monkeypatch.setenv("EDI_LLM_CACHED_INPUT_USD_PER_MILLION", ".1")
    assert reported_usage(usage(cached_content_token_count=500), "synthetic-model")[
        "estimated_usd"
    ] == pytest.approx(0.0008)
    assert reported_usage(SimpleNamespace(), "synthetic-model") == {}


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "private-invalid-rate"])
def test_bad_price_configuration_is_unknown_not_zero(prices, monkeypatch, value):
    monkeypatch.setenv("EDI_LLM_INPUT_USD_PER_MILLION", value)
    assert "estimated_usd" not in reported_usage(usage(), "synthetic-model")


def test_json_logs_discard_messages_exception_payloads_and_arbitrary_extras():
    marker = "private-password-document-سري"
    record = logging.LogRecord(
        "unsafe-third-party",
        logging.ERROR,
        marker,
        1,
        marker,
        (),
        (ValueError, ValueError(marker), None),
    )
    record.authorization = marker
    value = json.loads(SafeJSONFormatter().format(record))
    assert marker not in json.dumps(value, ensure_ascii=False)
    record.edi_record = {
        "operation": "llm.generate",
        "trace_id": "a" * 32,
        "span_id": "b" * 16,
        "parent_span_id": marker,
        "status": marker,
        "duration_ms": float("nan"),
        "measurements": {
            "prompt_tokens": 12,
            "prompt": marker,
            "estimated_usd": float("inf"),
        },
    }
    value = json.loads(SafeJSONFormatter().format(record))
    assert marker not in json.dumps(value, ensure_ascii=False)
    assert (
        value["measurements"] == {"prompt_tokens": 12}
        and value["parent_span_id"] is None
    )


def test_collector_is_bounded_and_model_failure_is_recorded_without_source():
    client = Mock()
    client.models.generate_content.side_effect = RuntimeError("private-provider-error")
    with collection() as collector:
        with pytest.raises(RuntimeError):
            generate_content(client, model="synthetic", contents="private-source")
        for _ in range(MAX_SPANS + 5):
            with span("http.request"):
                pass
    assert len(collector.records) == MAX_SPANS and collector.dropped == 6
    assert collector.records[0]["status"] == "error"
    assert "private" not in str(collector.records)


def test_http_correlation_is_generated_not_adopted_from_untrusted_headers(secured):
    client, sessions = secured
    sign_in(client, "alice")
    first = client.get(
        "/documents",
        headers={"x-request-id": "a" * 32, "traceparent": "private-forged-trace"},
    )
    second = client.get("/documents")
    reference = first.headers["x-request-id"]
    assert len(reference) == 32 and reference not in {
        "a" * 32,
        second.headers["x-request-id"],
    }
    with sessions() as db:
        row = db.scalar(
            select(TelemetrySpan).where(TelemetrySpan.trace_id == reference)
        )
        assert row.organization_id == "org-a" and row.operation == "http.request"
        assert row.measurements == {"http_status": 200}


@pytest.mark.parametrize(
    "who,expected", [(None, 401), ("alice", 403), ("reviewer", 403), ("admin", 200)]
)
def test_operations_requires_real_admin_and_never_returns_foreign_traces(
    secured, who, expected
):
    client, sessions = secured
    foreign = uuid.uuid4().hex
    with sessions() as db:
        db.add(
            TelemetrySpan(
                id=uuid.uuid4().hex,
                organization_id="org-b",
                trace_id=foreign,
                span_id="b" * 16,
                operation="llm.generate",
                status="error",
                duration_ms=99999,
                measurements={"prompt_tokens": 999999},
                created_at=utc_now_naive(),
            )
        )
        db.commit()
    if who:
        sign_in(client, who)
    response = client.get("/operations/summary")
    assert response.status_code == expected
    if who == "admin":
        data = response.json()
        assert (
            data["llm"]["calls"] == 0 and data["llm"]["reported_prompt_tokens"] is None
        )
        assert data["llm"]["estimated_usd_known_calls"] is None
        assert (
            foreign not in response.text
            and client.get(f"/operations/traces/{foreign}").status_code == 404
        )


def test_worker_attempt_joins_request_and_keeps_usage_unknown_without_metadata(secured):
    _, sessions = secured
    actor = Principal("alice", "org-a", "employee")
    with (
        collection(organization_id="org-a") as intake,
        span("http.request"),
        sessions() as db,
    ):
        job = enqueue(db, "document", "alice-doc", actor)
        identifier, parent = job.id, job.parent_span_id
        db.commit()

    def handler(db, job):
        assert trace_id() == intake.trace_id
        client = Mock()
        client.models.generate_content.return_value = SimpleNamespace()
        generate_content(client, model="synthetic", contents="never-log-this")

    assert run_once(sessions, handler)
    with sessions() as db:
        assert db.get(ProcessingJob, identifier).state == "completed"
        rows = db.scalars(
            select(TelemetrySpan).where(TelemetrySpan.trace_id == intake.trace_id)
        ).all()
        root = next(row for row in rows if row.operation == "job.execute")
        call = next(row for row in rows if row.operation == "llm.generate")
        assert root.parent_span_id == parent and call.parent_span_id == root.span_id
        assert call.measurements == {} and "never-log-this" not in str(
            [row.measurements for row in rows]
        )


def test_telemetry_failure_does_not_raise_or_store_document_content():
    with (
        collection(organization_id="synthetic") as collector,
        span("http.request") as item,
    ):
        item.measurements = {"document": "private-source", "http_status": 200}
    persist(collector, Mock(side_effect=RuntimeError("private-database-url")))
    assert collector.records[0]["measurements"] == {"http_status": 200}


def test_disabled_recording_keeps_business_responses_and_generated_reference(
    secured, monkeypatch
):
    client, sessions = secured
    sign_in(client, "alice")
    monkeypatch.setenv("EDI_TELEMETRY_ENABLED", "false")
    response = client.get("/documents")
    assert response.status_code == 200 and len(response.headers["x-request-id"]) == 32
    with sessions() as db:
        assert (
            db.scalar(
                select(TelemetrySpan).where(
                    TelemetrySpan.trace_id == response.headers["x-request-id"]
                )
            )
            is None
        )


def test_unhandled_errors_return_generic_correlated_response_without_private_exception():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.observability.middleware import TelemetryMiddleware

    application = FastAPI()
    application.add_middleware(TelemetryMiddleware)

    @application.get("/synthetic")
    def failure():
        raise RuntimeError("private-source-password")

    with TestClient(application) as client:
        response = client.get("/synthetic")
    assert response.status_code == 500 and "private" not in response.text
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_reclaimed_lease_is_not_dispatched_under_replacement_worker_token(
    secured, monkeypatch
):
    from app.jobs import worker
    from app.jobs.queue import claim

    _, sessions = secured
    with sessions() as db:
        job = enqueue(
            db,
            "specialist",
            "synthetic-reclaim",
            Principal("alice", "org-a", "employee"),
        )
        identifier = job.id
        db.commit()
    _, stale_token = claim(sessions)
    with sessions() as db:
        db.get(ProcessingJob, identifier).lease_token = "replacement-token"
        db.commit()
    monkeypatch.setattr(worker, "claim", lambda _: (identifier, stale_token))
    handler = Mock(
        side_effect=AssertionError(
            "Stale claim cannot enter processing/checkpoint thread"
        )
    )
    assert worker.run_once(sessions, handler)
    handler.assert_not_called()
    with sessions() as db:
        assert db.get(ProcessingJob, identifier).lease_token == "replacement-token"
