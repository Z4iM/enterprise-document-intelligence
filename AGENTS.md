# EDI engineering rules

- Work in this repository. Follow `EDI_CODEX_MASTER_PROMPT.md` when available and the approved milestone scope. Preserve confirmed handoff files.
- Inspect Git state first. Never overwrite user changes. Use an approved `feat/...` branch; never edit main directly.
- Implement one approved milestone, verify it, report observed results, then stop for review. Commits, pushes, deployment, destructive operations and real Gemini calls require separate authorization.
- Official policy outcomes come only from deterministic evaluation of source-verified, human-approved rules and explicitly reviewed document data. Review of fields is not expense approval.
- Share document eligibility through `app/review/eligibility.py`. Preserve extraction provenance. Untrusted model/tool arguments cannot supply authorization or approval.
- Keep development investigation/workflow/policy-review guards intact. Business routes require sessions, CSRF and organization/ownership/role checks. Local/token guards remain additional restrictions. See docs/SECURITY.md; no production deployment is authorized.
- Never read or expose secrets/private documents. Tests must use synthetic data and isolated databases; no personal API keys or real inference in CI.
- Arabic and English documents are required release targets. Preserve Unicode/source quotations and test both; M3 foundations do not certify Arabic semantic quality. See docs/ARABIC_SUPPORT.md for milestone gates.
- Required gates: `python -m ruff check .`, `python -m pytest -q`, then frontend `npm run lint` (TypeScript) and `npm run build`; finish with `git diff --check` and a diff/security review.
- Use `docs/ROADMAP.md`, `docs/ARCHITECTURE.md` and `docs/DECISIONS.md` for status/design. Report implementation, files, observed tests, security, limitations, demo, next milestone and Git state. Do not claim production readiness.
