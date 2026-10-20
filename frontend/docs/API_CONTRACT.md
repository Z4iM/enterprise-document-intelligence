# Frontend ⇄ FastAPI API contract (verified against GitHub main)

Frontend routes use `/api/bridge/<path>` and an allowlisted Next.js server proxy. All API calls are same-origin from the browser.

| Feature | Method | FastAPI endpoint | Frontend implementation |
| --- | --- | --- | --- |
| Connection status | GET | `/health` | header every 30 seconds |
| Documents list | GET | `/documents` | dashboard/list |
| Document details | GET | `/documents/{id}` | detail |
| Audit events | GET | `/documents/{id}/audit` | detail tab |
| Original file | GET | `/documents/{id}/original` | download |
| Prior reviews | GET | `/documents/{id}/reviews` | detail tab |
| Pending reviews | GET | `/reviews/pending` | review queue |
| Document ingestion | POST multipart | `/documents/upload` | upload form field name `file` |
| Review save | POST JSON | `/documents/{id}/review` | `decision` = `approved`/`corrected`/`rejected`; `reviewer`, optional `corrections`, `notes` |
| Upload policy | POST multipart | `/policies/upload` | file field name `file` |
| Policy evaluation | POST JSON | `/documents/{id}/validate-approved-policy` | `{ "policy_id": "..." }` |
| List candidate/approved rules | GET | `/policies/{id}/rules` | Optional only; **missing on remote main** |

Not sent through the frontend: rule candidate extraction, rule approval token, legacy LLM-only policy validation, document deletion. Review approval endpoint requires proper identity and RBAC before it can be added safely.

## Functional acceptance checklist

- [ ] Backend `/health` responds (FastAPI 8000).
- [ ] Frontend header shows `API Connected`.
- [ ] Dashboard lists same documents as FastAPI Swagger.
- [ ] Upload a **synthetic** DOCX receipt and see its actual extracted fields.
- [ ] Duplicate upload returns link to existing document (HTTP 409 case).
- [ ] Document details show the extraction fields and original file.
- [ ] Pending review queue shows documents with `needs_review`.
- [ ] Submit synthetic review; queue shrinks, and audit entry appears.
- [ ] Policy upload succeeds; local bookmark saves the ID.
- [ ] Evaluate with *existing* approved policy ID; see status, required actions and evidence.
- [ ] Policy rules page handles 404 gracefully on older backend.
- [ ] Workflows page explicitly notes orchestration is not implemented.
- [ ] `npm run lint` and `npm run build` pass on workstation.

**Note:** Avoid uploading confidential files. The backend has no auth or tenant isolation.
