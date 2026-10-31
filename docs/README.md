# NEXUS EDI documentation

Start with the [project README](../README.md) for the product workflow, engineering overview and quick start. These guides provide the implementation detail and evidence behind the showcase.

| Goal | Read |
|---|---|
| Run locally and sign in | [Local setup](LOCAL_SETUP.md), [frontend](../frontend/README.md) |
| Reproduce the demonstration | [Showcase](SHOWCASE.md), [demo script](DEMO_SCRIPT.md), [synthetic fixtures](demo/fixtures) |
| Understand the design | [Architecture](ARCHITECTURE.md), [engineering decisions](DECISIONS.md), [workflow design](langgraph_workflow_design.md) |
| Inspect authorization and data handling | [Security](SECURITY.md), [API contract](../frontend/docs/API_CONTRACT.md) |
| Understand agents and evidence | [Specialists](SPECIALISTS.md), [retrieval](RETRIEVAL.md), [Arabic support](ARABIC_SUPPORT.md) |
| Operate and recover the system | [Persistence](PERSISTENCE.md), [observability](OBSERVABILITY.md) |
| Assess measured results | [Verification log](VERIFICATION.md), [benchmark artifacts](benchmarks) |
| Follow delivery and remaining work | [Roadmap](ROADMAP.md), [changelog](../CHANGELOG.md) |
| Assess the portfolio | [Evidence-supported claims](PORTFOLIO.md), [LinkedIn video post](LINKEDIN_POST.md) |

## Reading the evidence

Verification entries are dated observations, not promises that a command was rerun with every documentation edit. Synthetic/scripted tests establish application behavior; live-provider reasoning, representative OCR quality and deployment readiness require separate evidence.

The showcase target is **November 6, 2026**. Milestones 1–7 are implemented; the M7 review branch was merged as PR #8. Video approval/export and public posting are separate actions. Production hardening and model-quality gates remain explicit in the roadmap.
