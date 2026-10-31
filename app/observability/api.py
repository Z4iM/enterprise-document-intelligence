"""Admin-only, organization-scoped operational aggregates and bounded trace inspection."""

import math
import os
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select

from app.auth.security import authorize_request, session_factory
from app.database.models import ProcessingJob, TelemetrySpan, utc_now_naive
from app.observability.tracing import (
    OPERATIONS,
    ORG_ROW_LIMIT,
    STATUSES,
    identifier,
    safe_measurements,
)


def admin(request: Request):
    if request.state.actor.role != "admin":
        raise HTTPException(403, "Administrator permission required.")


router = APIRouter(
    prefix="/operations", dependencies=[Depends(authorize_request), Depends(admin)]
)


def percentile(values, fraction):
    ordered = sorted(values)
    return (
        round(ordered[max(0, math.ceil(len(ordered) * fraction) - 1)], 3)
        if ordered
        else None
    )


def public_span(row):
    return {
        "trace_id": row.trace_id,
        "span_id": row.span_id,
        "parent_span_id": row.parent_span_id,
        "operation": row.operation if row.operation in OPERATIONS else "unknown",
        "status": row.status if row.status in STATUSES else "error",
        "duration_ms": row.duration_ms,
        "measurements": safe_measurements(row.measurements),
        "created_at": row.created_at,
    }


@router.get("/summary")
def summary(request: Request):
    now, organization = utc_now_naive(), request.state.actor.organization_id
    with session_factory(request)() as db:
        rows = db.scalars(
            select(TelemetrySpan)
            .where(
                TelemetrySpan.organization_id == organization,
                TelemetrySpan.created_at >= now - timedelta(hours=24),
            )
            .order_by(TelemetrySpan.created_at.desc(), TelemetrySpan.id.desc())
            .limit(2001)
        ).all()
        truncated, rows = len(rows) > 2000, rows[:2000]
        groups = []
        for operation in sorted(OPERATIONS):
            subset = [row for row in rows if row.operation == operation]
            if subset:
                groups.append(
                    {
                        "operation": operation,
                        "count": len(subset),
                        "errors": sum(row.status == "error" for row in subset),
                        "p50_ms": percentile([row.duration_ms for row in subset], 0.5),
                        "p95_ms": percentile([row.duration_ms for row in subset], 0.95),
                    }
                )
        calls = [row for row in rows if row.operation == "llm.generate"]
        measurements = [safe_measurements(row.measurements) for row in calls]

        def reported_sum(key):
            known = [value[key] for value in measurements if key in value]
            return sum(known) if known else None

        queue = dict(
            db.execute(
                select(ProcessingJob.state, func.count())
                .where(ProcessingJob.organization_id == organization)
                .group_by(ProcessingJob.state)
            ).all()
        )
        expired = db.scalar(
            select(func.count())
            .select_from(ProcessingJob)
            .where(
                ProcessingJob.organization_id == organization,
                ProcessingJob.state == "running",
                ProcessingJob.lease_until < now,
            )
        )
        oldest = db.scalar(
            select(func.min(ProcessingJob.available_at)).where(
                ProcessingJob.organization_id == organization,
                ProcessingJob.state.in_(["queued", "retry_wait"]),
                ProcessingJob.available_at <= now,
            )
        )
        stored = db.scalar(
            select(func.count())
            .select_from(TelemetrySpan)
            .where(TelemetrySpan.organization_id == organization)
        )
        alerts = []
        if queue.get("failed", 0):
            alerts.append("Failed jobs require attention.")
        if expired:
            alerts.append("Expired running leases are eligible for recovery.")
        if any(row.status == "error" for row in calls):
            alerts.append("Model request errors occurred in the sampled window.")
        if stored >= ORG_ROW_LIMIT:
            alerts.append("Telemetry storage cap reached; new spans may be dropped.")
        return {
            "enabled": os.getenv("EDI_TELEMETRY_ENABLED", "true") == "true",
            "window_hours": 24,
            "sample_limit": 2000,
            "sample_count": len(rows),
            "truncated": truncated,
            "best_effort": True,
            "storage_rows": stored,
            "storage_cap_per_organization": ORG_ROW_LIMIT,
            "automatic_deletion": False,
            "queue": queue,
            "expired_leases": expired,
            "oldest_ready_wait_seconds": max(0, (now - oldest).total_seconds())
            if oldest
            else None,
            "operations": groups,
            "llm": {
                "calls": len(calls),
                "usage_reported_calls": sum(
                    "prompt_tokens" in value and "output_tokens" in value
                    for value in measurements
                ),
                "priced_calls": sum("estimated_usd" in value for value in measurements),
                "reported_prompt_tokens": reported_sum("prompt_tokens"),
                "reported_output_tokens": reported_sum("output_tokens"),
                "reported_total_tokens": reported_sum("total_tokens"),
                "estimated_usd_known_calls": reported_sum("estimated_usd"),
                "cost_complete": bool(calls)
                and all("estimated_usd" in value for value in measurements),
                "pricing": "configured_linear_estimate_not_invoice",
            },
            "alerts": alerts,
            "recent_spans": [public_span(row) for row in rows[:40]],
        }


@router.get("/traces/{value}")
def trace(value: str, request: Request):
    if not identifier(value):
        raise HTTPException(404, "Trace not found.")
    with session_factory(request)() as db:
        rows = db.scalars(
            select(TelemetrySpan)
            .where(
                TelemetrySpan.organization_id == request.state.actor.organization_id,
                TelemetrySpan.trace_id == value,
            )
            .order_by(TelemetrySpan.created_at, TelemetrySpan.id)
            .limit(129)
        ).all()
        if not rows:
            raise HTTPException(404, "Trace not found.")
        return {
            "trace_id": value,
            "spans": [public_span(row) for row in rows[:128]],
            "truncated": len(rows) > 128,
        }
