"""Local parent/child spans, reported usage and fail-open bounded persistence."""

import contextvars
import functools
import json
import logging
import math
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

MAX_SPANS = 64
ORG_ROW_LIMIT = 20000
OPERATIONS = frozenset(
    {
        "http.request",
        "job.execute",
        "llm.generate",
        "retrieval.search",
        "tool.inspect_document",
        "tool.get_policy_evidence",
        "tool.evaluate_document_policy",
        "tool.search_policy_sources",
        "workflow.document",
        "workflow.policy",
        "workflow.evaluate",
    }
)
STATUSES = frozenset({"ok", "error", "denied", "fallback", "abstain"})
CURRENT = contextvars.ContextVar("edi_trace", default=None)
PARENT = contextvars.ContextVar("edi_span", default=None)
logger = logging.getLogger("edi.telemetry")


def identifier(value, length=32):
    return (
        isinstance(value, str)
        and re.fullmatch(rf"[a-f0-9]{{{length}}}", value) is not None
    )


def trace_id():
    collector = CURRENT.get()
    return collector.trace_id if collector else None


def bind_organization(value):
    collector = CURRENT.get()
    if collector and collector.organization_id is None:
        collector.organization_id = value


@dataclass
class Collector:
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    organization_id: str | None = None
    records: list = field(default_factory=list)
    dropped: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def append(self, record):
        with self.lock:
            if len(self.records) < MAX_SPANS:
                self.records.append(record)
            else:
                self.dropped += 1


@contextmanager
def collection(*, trusted_trace=None, parent=None, organization_id=None):
    collector = Collector(
        trace_id=trusted_trace if identifier(trusted_trace) else uuid.uuid4().hex,
        organization_id=organization_id,
    )
    token = CURRENT.set(collector)
    parent_token = PARENT.set(parent if identifier(parent, 16) else None)
    try:
        yield collector
    finally:
        PARENT.reset(parent_token)
        CURRENT.reset(token)


@dataclass
class Span:
    operation: str
    status: str = "ok"
    measurements: dict = field(default_factory=dict)


@contextmanager
def span(operation):
    if operation not in OPERATIONS:
        raise ValueError("Unknown trace operation.")
    collector = CURRENT.get()
    started, timestamp = time.perf_counter(), datetime.now(UTC).replace(tzinfo=None)
    parent, span_id = PARENT.get(), uuid.uuid4().hex[:16]
    token = PARENT.set(span_id)
    item = Span(operation)
    try:
        yield item
    except BaseException:
        item.status = "error"
        raise
    finally:
        PARENT.reset(token)
        if collector and os.getenv("EDI_TELEMETRY_ENABLED", "true") == "true":
            record = {
                "id": uuid.uuid4().hex,
                "trace_id": collector.trace_id,
                "span_id": span_id,
                "parent_span_id": parent,
                "operation": operation,
                "status": item.status if item.status in STATUSES else "error",
                "duration_ms": round(max(0, time.perf_counter() - started) * 1000, 3),
                "created_at": timestamp,
                "measurements": safe_measurements(item.measurements),
            }
            collector.append(record)
            logger.info("span", extra={"edi_record": record})


MEASUREMENTS = frozenset(
    {
        "http_status",
        "attempt",
        "queue_wait_ms",
        "candidate_count",
        "result_count",
        "prompt_tokens",
        "output_tokens",
        "thought_tokens",
        "cached_tokens",
        "tool_prompt_tokens",
        "total_tokens",
        "estimated_usd",
    }
)


def safe_measurements(values):
    # No arbitrary labels, payload strings, IDs, errors, prompt or response content.
    if not isinstance(values, dict):
        return {}
    return {
        key: value
        for key, value in values.items()
        if key in MEASUREMENTS
        and type(value) in (int, float)
        and 0 <= value <= 1e12
        and math.isfinite(value)
    }


def traced(operation):
    def decorate(function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            with span(operation) as item:
                result = function(*args, **kwargs)
                if operation == "retrieval.search" and isinstance(result, dict):
                    item.measurements = {
                        "candidate_count": result.get("candidate_count"),
                        "result_count": len(result.get("results", [])),
                    }
                if isinstance(result, dict):
                    status = result.get("status", "")
                    if status in {"access_denied", "invalid_arguments", "unknown_tool"}:
                        item.status = "denied"
                    elif isinstance(status, str) and (
                        status.startswith("waiting_")
                        or status in {"needs_review", "no_evidence"}
                    ):
                        item.status = "abstain"
                    elif status == "blocked":
                        item.status = "error"
                return result

        return wrapped

    return decorate


def rate(name):
    try:
        value = Decimal(os.getenv(name, ""))
        return value if value.is_finite() and 0 <= value <= 10000 else None
    except InvalidOperation:
        return None


def reported_usage(response, model):
    metadata = getattr(response, "usage_metadata", None)
    fields = {
        "prompt_tokens": "prompt_token_count",
        "output_tokens": "candidates_token_count",
        "thought_tokens": "thoughts_token_count",
        "cached_tokens": "cached_content_token_count",
        "tool_prompt_tokens": "tool_use_prompt_token_count",
        "total_tokens": "total_token_count",
    }
    values = {
        key: getattr(metadata, attribute, None) for key, attribute in fields.items()
    }
    values = {
        key: value
        for key, value in values.items()
        if type(value) is int and 0 <= value <= 1_000_000_000
    }
    # Missing counters are unknown, never silently zero. No pricing/model assumptions.
    required = {
        "prompt_tokens",
        "output_tokens",
        "thought_tokens",
        "cached_tokens",
        "tool_prompt_tokens",
    }
    if (
        "total_tokens" in values
        and required <= values.keys()
        and values["total_tokens"]
        != sum(
            values[key]
            for key in (
                "prompt_tokens",
                "output_tokens",
                "thought_tokens",
                "tool_prompt_tokens",
            )
        )
    ):
        return values
    if model != os.getenv("EDI_LLM_PRICING_MODEL") or not required <= values.keys():
        return values
    incoming, outgoing, cached = (
        rate(name)
        for name in (
            "EDI_LLM_INPUT_USD_PER_MILLION",
            "EDI_LLM_OUTPUT_USD_PER_MILLION",
            "EDI_LLM_CACHED_INPUT_USD_PER_MILLION",
        )
    )
    if (
        incoming is None
        or outgoing is None
        or values["cached_tokens"] > values["prompt_tokens"]
        or (values["cached_tokens"] and cached is None)
    ):
        return values
    estimate = (
        (
            values["prompt_tokens"]
            - values["cached_tokens"]
            + values["tool_prompt_tokens"]
        )
        * incoming
        + values["cached_tokens"] * (cached or Decimal(0))
        + (values["output_tokens"] + values["thought_tokens"]) * outgoing
    ) / 1_000_000
    values["estimated_usd"] = float(estimate)
    return values


def generate_content(client, **kwargs):
    with span("llm.generate") as item:
        response = client.models.generate_content(**kwargs)
        item.measurements = reported_usage(response, kwargs.get("model"))
        return response


def persist(collector, sessions):
    if (
        not collector.organization_id
        or os.getenv("EDI_TELEMETRY_ENABLED", "true") != "true"
    ):
        return
    try:
        from sqlalchemy import func, select

        from app.database.models import TelemetrySpan

        with sessions() as db:
            count = db.scalar(
                select(func.count())
                .select_from(TelemetrySpan)
                .where(TelemetrySpan.organization_id == collector.organization_id)
            )
            for record in collector.records[: max(0, ORG_ROW_LIMIT - count)]:
                db.add(
                    TelemetrySpan(**record, organization_id=collector.organization_id)
                )
            db.commit()
    except Exception:  # noqa: BLE001 - observability must not break business outcomes.
        logger.warning(
            "telemetry_unavailable", extra={"edi_event": "telemetry_unavailable"}
        )


class SafeJSONFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname
            if record.levelname in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
            else "INFO",
            "event": "runtime_log",
        }
        if getattr(record, "edi_event", None) == "telemetry_unavailable":
            payload["event"] = "telemetry_unavailable"
        value = getattr(record, "edi_record", None)
        if (
            isinstance(value, dict)
            and isinstance(value.get("operation"), str)
            and value.get("operation") in OPERATIONS
            and identifier(value.get("trace_id"))
            and identifier(value.get("span_id"), 16)
        ):
            payload.update(
                {key: value[key] for key in ("trace_id", "span_id", "operation")}
            )
            payload["parent_span_id"] = (
                value.get("parent_span_id")
                if identifier(value.get("parent_span_id"), 16)
                else None
            )
            payload["status"] = (
                value.get("status")
                if isinstance(value.get("status"), str)
                and value.get("status") in STATUSES
                else "error"
            )
            duration = value.get("duration_ms")
            payload["duration_ms"] = (
                duration
                if type(duration) in (int, float)
                and math.isfinite(duration)
                and duration >= 0
                else 0
            )
            payload["event"], payload["measurements"] = (
                "span",
                safe_measurements(value.get("measurements", {})),
            )
        # Intentionally discard getMessage(), args, exc_info and arbitrary extras.
        failure = getattr(record, "edi_failure_type", None)
        if isinstance(failure, str) and failure in {
            "ValueError",
            "RuntimeError",
            "TimeoutError",
            "OSError",
            "ConnectionError",
            "ValidationError",
            "JSONDecodeError",
        }:
            payload["failure_type"] = failure
        if "trace_id" not in payload and identifier(trace_id()):
            payload["trace_id"] = trace_id()
        return json.dumps(payload, ensure_ascii=True, allow_nan=False)


def configure_logging():
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    formatter = SafeJSONFormatter()
    for handler in root.handlers:
        handler.setFormatter(formatter)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        target = logging.getLogger(name)
        for handler in target.handlers:
            handler.setFormatter(formatter)
    logger.setLevel(logging.INFO)
