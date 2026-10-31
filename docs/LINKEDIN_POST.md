# LinkedIn video post

I built NEXUS EDI — Enterprise Document Intelligence to explore a practical AI engineering question:

How do you turn a document into a policy requirement that someone can inspect and trust?

In this walkthrough, a receipt moves through extraction, human review and policy evaluation. The result explains which requirement applies and points back to the original policy quotation.

The engineering behind that flow includes:

- Automatic whole-policy rule proposals, source verification and explicit reviewer approval.
- A bounded investigation agent and document/policy specialists coordinated through LangGraph.
- Human-review checkpoints that pause and resume, with deterministic final evaluation.
- English/Arabic document workflows, scoped evidence search and original-source citations.
- Role and ownership checks, durable background jobs, PostgreSQL persistence and Docker recovery checks.
- Operational traces, queue diagnostics and reproducible evaluation/test evidence.

The central boundary: a model suggestion is not an approval. Reviewing extracted fields does not approve an expense, and an old rule approval cannot override failed source verification.

Building this taught me as much about authorization, failure recovery and evaluation as it did about model integration. Broader Arabic OCR quality and live-model performance remain documented improvement areas.

Code, architecture, setup and measured limitations:
https://github.com/Z4iM/enterprise-document-intelligence

I’d welcome feedback from engineers working on document AI, reliable agents and MLOps.

Demo notes: the video uses synthetic documents and scripted model responses. Application authorization, review, source verification and deterministic evaluation run through the real code; a seeded historical approval demonstrates revalidation blocking. Footage is edited and narration is AI-generated.

Music: “Cipher” by Kevin MacLeod (incompetech.com), CC BY 4.0: https://creativecommons.org/licenses/by/4.0/. Track: https://incompetech.com/music/royalty-free/index.html?Search=Search&isrc=USUAN1100844

#AIEngineering #DocumentAI #MLOps #LangGraph #Python

---

Publication note: draft copy for the reviewed video; no LinkedIn post or video upload has been performed. Keep the filming disclosure and music attribution with the public video. Benchmark details belong in the linked repository rather than unsupported headline claims.
