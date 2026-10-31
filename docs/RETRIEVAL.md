# Authorized policy evidence retrieval (M4)

[NEXUS EDI](../README.md) · [Documentation guide](README.md)

In Policy library, select a policy and **Update search index** for older uploads, then
search in English or Arabic. New uploads enqueue indexing automatically, independently
of AI rule extraction. Employees search organization policies; reviewers/admins reindex
or confirm removal. Removal excludes derived passages and cancels index leases while
preserving originals, chunks, approved rules and audit history.

Results are candidate source passages, never answers, approval or compliance. Existing
investigation tools retain their approved-rule-only contract; specialist integration is
M5. Arabic field extraction and policy interpretation are not certified.

## Setup and migration

Default: explicitly labeled keyword search, no startup/request-time model download.
Install `requirements-runtime.txt` (no PyTorch). Enable the optional public local encoder:

```powershell
python scripts/cache_retrieval_model.py --directory D:/EDI-Storage/models/edi-multilingual-faf4aa42
$env:EDI_RETRIEVAL_MODEL_DIR='D:/EDI-Storage/models/edi-multilingual-faf4aa42'
```

Restart API/worker with the same setting and update existing policy indexes. The setup
requires a new empty directory, no HF token, a fixed revision and a 300 MB download
budget. Observed download: **266,903,238 bytes**. Serving checks the manifest/file hashes,
loads only local files and never executes remote model code. A broken configured model
fails indexing visibly; search falls back with a warning. Different-model vectors are
excluded until reindexed.

Docker has a separate `edi_models` volume on Docker's configured disk. Explicitly prepare:

```text
docker compose exec api python cache_retrieval_model.py --directory /srv/models/retrieval
```

Then set Compose `EDI_RETRIEVAL_MODEL_DIR=/srv/models/retrieval` and recreate services.
Use this container path, not a D: host path. Compact uses the same command. Models are
not baked into images. The verification runner accepts `--model-directory` for a read-only
host mount instead. Both services must see identical verified assets.

Back up existing databases, then run `python -m alembic upgrade head`. Head
`20261030_retrieval` adds two derived tables and extends job kinds without changing
originals, chunk IDs, rules or existing jobs. Downgrade is refused; restore a tested
pre-upgrade backup with compatible code. Verification never migrates real user data.

## Architecture and bounds

- SQL joins organization, policy, chunk and enabled index before loading/ranking sources
  or calculating BM25 statistics. Selected policy IDs are reauthorized. Source-language
  filter accepts `en`/`ar`; mixed script is classified `ar`.
- BM25 uses search-only Unicode, Arabic and digit normalization; quotations are unchanged.
  Quantized multilingual MiniLM produces normalized 384-dimensional vectors. Exact cosine
  and BM25 rankings merge through reciprocal rank fusion (`k=60`). Cosine threshold 0.55
  is a retrieval heuristic, not an answerability proof.
- Existing source chunk IDs remain stable. Semantic windows: 96 tokens, stride 80,
  maximum 400 characters, within the encoder's 128-token budget. Keyword windows:
  400 characters, stride 340. Offsets are chunk-relative Unicode characters, not PDF pages.
- Limits: 60,000 source-chunk characters / 400 passages per policy; 5,000 authorized
  search candidates; query 500 characters; 20 selected policies; 10 returned results.
  Oversized scopes fail explicitly rather than silently dropping sources.
- One active HTTP search per API process bounds simultaneous corpus/model memory;
  additional requests return 429 and can retry. This favors the small host over throughput.
- Derived vectors use JSON in SQLite/PostgreSQL, avoiding another extension/service on
  this small host. Exact scans have a scale ceiling; move to scoped pgvector ANN when
  measured corpus size or latency requires it, retaining authorization before retrieval.
- Reindex reuses unchanged source/span/model vectors. Workers recheck actor, original
  path/hash; reads recheck chunk hash/offsets. Removal cancels the claim in its transaction;
  completion fencing rolls back stale results. Inference precedes business writes.
- Stored chunks must still match the bounded parser's chunking of the original on
  reindex; altered chunks cannot be silently blessed as new original-source evidence.
- Encoder threads=1, batches=8, no GPU, five-second lock acquisition timeout. Active ONNX
  inference has no hard subprocess deadline; lease fencing bounds commits, not CPU time.

API/worker memory limits are each 1 GB; initialization exceeded the prior 768 MB API
limit in a real-model container test. Limits are caps, not memory reservations. Keep
builds, browser checks and real-model runs sequential on an 8 GB development machine.

Endpoints: `POST /evidence/search`, `GET /evidence/citations/{id}`,
`GET|POST /policies/{id}/index`, `POST /policies/{id}/index/remove`. Sessions and
organization scope apply throughout, POSTs require CSRF, maintenance requires staff.
Maintenance audit records contain actor/resource IDs, no source/query text.

## Measured benchmark

Fixed synthetic corpus: 32 source policies; 40 labeled queries, 20 English/20 Arabic,
including eight unanswerable. Each answerable label includes both translated sources;
Recall@5 measures recovery of both, not simply finding one answer.

```text
python evals/retrieval/run.py --model-directory <verified-model-directory> --output docs/benchmarks/retrieval-v1.json
```

Omit the model directory for CI's network-free keyword baseline. The runner creates an
isolated database and disables generation. [Raw results](benchmarks/retrieval-v1.json)
record corpus hash, model/weight revision, per-query results and hardware.

| Method | Recall@5 | MRR@5 | Citation integrity | Unanswerable abstention | Warm p95 |
|---|---:|---:|---:|---:|---:|
| Keyword | 50.0% | 0.8333 | 100% | 87.5% | 16.73 ms |
| Semantic | 79.7% | 0.8750 | 100% | 87.5% | 39.11 ms |
| Hybrid | 87.5% | 0.9635 | 100% | 75.0% | 36.87 ms |

Hybrid English/Arabic Recall@5: **90.6% / 84.4%**; MRR **1.0000 / 0.9271**.
Arabic unanswerable abstention is only **50% (2/4)**. Hybrid relevance precision across
returned citations is **43.75%**. Exact source quotation integrity is not semantic
relevance or answer correctness. Neither hits nor missing results imply permission.
This small synthetic benchmark is not a held-out enterprise accuracy estimate. Latencies
are warm single-user native CPU measurements (nearest-rank p95), not load SLOs; no external inference bill.
Threshold calibration/reranking need separate development and held-out datasets. Broader
Arabic OCR/extraction/policy interpretation and generative answer evaluation remain later gates.
