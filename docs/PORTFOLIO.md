# Evidence-supported portfolio material

## Project description

Enterprise Document Intelligence is a bilingual AI-assisted document review and expense-
policy investigation portfolio project. It separates model suggestions from authority:
official outcomes use reviewed document fields and source-verified, human-approved rules.
The existing investigator and two restricted specialists work with durable LangGraph
review checkpoints; a deterministic coordinator controls progression and final evaluation.

## CV bullets — adapt to your actual contribution

- Built an end-to-end document review application using FastAPI, Next.js, SQLAlchemy,
  PostgreSQL and Docker, with sessions, CSRF, role/ownership checks, durable processing
  jobs and human-review workflow recovery.
- Implemented scoped bilingual hybrid retrieval and source-preserving citations;
  measured **87.5% Recall@5 on a fixed 40-query synthetic development benchmark**.
- Integrated bounded document/policy specialists with disjoint tools, review checkpoints,
  source-verified rules and deterministic policy outcomes; added content-free traces,
  queue diagnostics and explicit regression versus product-quality release gates.
- Maintained automated backend, PostgreSQL, browser and container verification, including
  tenant isolation, stale-worker fencing, prompt-injection handling and restart/resume.

Use dated test counts from [VERIFICATION.md](VERIFICATION.md) if useful; a test count is
not an accuracy or security certification. Do not describe a portfolio feature as a
deployed service, customer adoption or an achieved business saving without that evidence.

## Interview evidence map

| Claim | Inspect | Explain |
|---|---|---|
| AI cannot approve expenses | `app/validation/`, `app/review/eligibility.py`, source-integrity tests | Why generation, field review, rule approval and expense approval are different |
| Cooperating specialists | `app/specialists/`, `docs/SPECIALISTS.md` | Why disjoint tools and typed handoffs help control; quality superiority remains unmeasured |
| Durable execution | `app/jobs/`, checkpoints, container recovery runner | Lease expiry, idempotence, stale-worker fencing, at-least-once inference trade-off |
| Authorized retrieval | `app/rag/`, retrieval benchmark and isolation tests | Keyword versus hybrid recall, candidate filtering, quotation integrity and abstention weaknesses |
| Operational evidence | `app/observability/`, `docs/OBSERVABILITY.md` | Why bounded SQL spans suit this host; missing usage stays unknown; telemetry is not billing/audit truth |
| Reproducible setup | `scripts/prepare_showcase.py`, `docs/SHOWCASE.md` | What a public-source fresh-environment rehearsal proves and what it does not |

## Claims to avoid

Do not claim production readiness, general Arabic OCR accuracy, universally correct policy
interpretation, superior multi-agent reasoning, a held-out quality score, zero vulnerabilities,
measured customer savings or a completed public deployment. Arabic scan-field accuracy is
**50% on four development scans**; unanswerable Arabic retrieval abstention is **50% (2/4)**.
Model-generated results still require source and human review gates.

## Draft LinkedIn project announcement

> I built Enterprise Document Intelligence, an AI-assisted document review and policy
> investigation portfolio project supporting English and Arabic workflows.
>
> The engineering focus is on traceable decisions: source-verified rules, explicit human
> review, restricted specialist tools, durable processing/recovery and organization-scoped
> access. FastAPI, Next.js, LangGraph, PostgreSQL and Docker connect the full lifecycle.
>
> I evaluated retrieval on a fixed synthetic bilingual corpus and documented the results,
> including weaker Arabic scan extraction and abstention. Automated tests cover normal
> operation, authorization failures and restart/resume behavior.
>
> I’ll share a short application walkthrough and repository with the setup instructions,
> architecture decisions and measured limitations.

Replace the final sentence with verified release/demo links only when they exist and you
choose to publish. This is draft copy, not a posted announcement or authorization to post.
