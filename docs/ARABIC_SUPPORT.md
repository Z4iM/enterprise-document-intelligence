# Required English/Arabic document support

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

## Remaining acceptance by milestone

| Milestone | Measurable acceptance |
|---|---|
| 4 — retrieval | At least 30 labeled queries, including 15 Arabic queries; Arabic/English/mixed-script source fixtures; report Recall@5, MRR, citation support and abstention separately by language. Test tenant isolation and Arabic evidence fidelity. |
| 5 — extraction/agents | At least 20 Arabic and 20 English synthetic documents across receipts/invoices/policies, including native and scanned input. Normalize Arabic-Indic/Eastern Arabic-Indic digits, decimal/thousands separators, currencies and dates conservatively. Evaluate field accuracy and abstention; test source-verified Arabic policy comparisons, roles, actions and categories before allowing authoritative outcomes. |
| 6 — evaluation | Report native extraction, OCR CER/WER, field extraction, rule/decision correctness, citation faithfulness, latency and cost by language. Require deterministic golden cases to pass; record model/version and dataset limitations. A real-model benchmark is opt-in and needs explicit quota/data approval. |
| 7 — showcase | A reproducible Arabic receipt/policy investigation with reviewed fields, verified approved Arabic rules and correct RTL quotations; visually inspect mixed-script/numeral evidence on desktop and mobile. |

## Current limits

The existing keyword classifier, regex fallback and policy source verifier primarily
recognize English wording and currency patterns. Arabic text can be preserved now, but
Arabic field/rule interpretation is **not yet accepted end to end**. Unsupported source
language/wording must remain review-gated; never bypass verification or claim compliance.
Mocked OCR checks prove configuration/timeout behavior, not Arabic recognition quality.
Native Arabic PDF/table coverage and real scanned-document OCR still need their own
fixtures and measured results. TXT intake currently requires UTF-8, not arbitrary encodings.
