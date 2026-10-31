# Required English/Arabic document support

[NEXUS EDI](../README.md) · [Documentation guide](README.md)

Arabic documents, including scans and mixed Arabic/English content, are part of the
showcase acceptance criteria. This is a product requirement, not an inferred capability
from Gemini. The interface can remain English; document content must read correctly.

## Milestone 3 foundations

- Preserve UTF-8 originals, Arabic filenames, source text, user names and JSON fields
  through SQLite/PostgreSQL, backup import and worker recovery.
- Exercise actual bounded TXT/DOCX parsers on synthetic Arabic text; enforce OCR
  `eng+ara`, install both packs in the backend image and fail explicitly if a required
  pack is absent. OCR language configuration is passed to parser children without secrets.
- Render source/evidence/corrections with automatic text direction. This does not translate
  the whole interface or establish OCR/model accuracy.
- Keep Arabic originals unchanged. Do not normalize away Arabic letters or alter quoted
  evidence to make a rule pass verification.

## Milestone acceptance criteria

| Milestone | Measurable acceptance |
|---|---|
| 4 — retrieval | At least 30 labeled queries, including 15 Arabic queries; Arabic/English/mixed-script source fixtures; report Recall@5, MRR, citation support and abstention separately by language. Test tenant isolation and Arabic evidence fidelity. |
| 5 — extraction/agents | At least 20 Arabic and 20 English synthetic documents across receipts/invoices/policies, including native and scanned input. Normalize Arabic-Indic/Eastern Arabic-Indic digits, decimal/thousands separators, currencies and dates conservatively. Evaluate field accuracy and abstention; test source-verified Arabic policy comparisons, roles, actions and categories before allowing authoritative outcomes. |
| 6 — evaluation | Report native extraction, OCR CER/WER, field extraction, rule/decision correctness, citation faithfulness, latency and cost by language. Require deterministic golden cases to pass; record model/version and dataset limitations. A real-model benchmark is opt-in and needs explicit quota/data approval. |
| 7 — showcase | A reproducible Arabic receipt/policy investigation with reviewed fields, verified approved Arabic rules and correct RTL quotations; visually inspect mixed-script/numeral evidence on desktop and mobile. |

## Current limits

M4 adds measured bilingual retrieval: 20 Arabic queries, exact Unicode quotations and
84.4% Arabic hybrid Recall@5. Unanswerable Arabic abstention is only 50% (2/4). This is
candidate retrieval, not semantic-policy certification. See [results](RETRIEVAL.md).

M5 adds Arabic classification/labeled fallback fields, both Arabic digit sets,
conservative dates/separators/currencies, and a narrow source-verified monetary-rule
grammar covering categories, actions and manager/director roles. Negation, exceptions,
currency/role mismatch and ambiguous wording fail closed. Original quotations stay intact.

The 40-template bilingual corpus (20/language) passes supported native golden cases;
eight actual scans expose important limits: Arabic scanned field exact accuracy **50%**,
false abstention **43.75%**, OCR CER/WER **0.4103/0.4033** on four Arabic scans, and 0/1
scanned Arabic policy verification. This does **not** establish reliable general Arabic
OCR. The actual browser journey proves Arabic upload → source-verified policy approval →
field correction → evidence attestation → resume with generation mocked, not live model
quality. See [method/results](SPECIALISTS.md) and raw benchmark JSON.

Native Arabic PDF/table coverage, realistic held-out scans and real-model quality remain
unverified. Unsupported inputs stay review-gated; never bypass source verification.
TXT intake requires UTF-8, not arbitrary encodings. Real-model evaluation needs approval.

M6 reran the fixed corpus after parser/security changes: native goldens still pass and
scanned-field quality remains 75% English / 50% Arabic. The measured report includes
per-language OCR/field/policy/timing results; scripted specialist reports include
per-language calls/control timings. Real-provider token/cost quality is **unmeasured**.
The release command separates passing regression checks from the deliberately unmet
held-out/live-model quality gate. See [M6 OCR](benchmarks/bilingual-m6.json),
[release checks](OBSERVABILITY.md#reproduce-evaluations-and-scans) and
[verification](VERIFICATION.md). M6 does not certify accurate general Arabic extraction.
