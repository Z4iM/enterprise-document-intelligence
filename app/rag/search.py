"""Authorization before retrieval/ranking; source quotations are revalidated on every read."""

import math
import time

from fastapi import HTTPException
from sqlalchemy import select

from app.auth.security import require_policy
from app.database.models import (
    PolicyChunk,
    PolicyDocument,
    PolicySearchIndex,
    SearchPassage,
)
from app.observability.tracing import traced
from app.rag import semantic
from app.rag.indexing import source_hash
from app.rag.lexical import bm25, tokens

MAX_CANDIDATES = 5000
SEMANTIC_THRESHOLD = 0.55


@traced("retrieval.search")
def search_evidence(
    db,
    actor,
    query,
    *,
    policy_ids=None,
    limit=5,
    language=None,
    method="hybrid",
    encoder="configured",
):
    started = time.perf_counter()
    if (
        not 1 <= len(query.strip()) <= 500
        or not 1 <= limit <= 10
        or method not in {"hybrid", "lexical", "semantic"}
    ):
        raise HTTPException(422, "Invalid search request.")
    if policy_ids:
        if len(policy_ids) > 20:
            raise HTTPException(422, "Select at most 20 policies.")
        for identifier in policy_ids:
            require_policy(db, identifier, actor)
    statement = (
        select(SearchPassage, PolicyChunk, PolicyDocument)
        .join(PolicyChunk, SearchPassage.chunk_id == PolicyChunk.id)
        .join(PolicyDocument, SearchPassage.policy_id == PolicyDocument.id)
        .join(PolicySearchIndex, PolicySearchIndex.policy_id == PolicyDocument.id)
        .where(
            PolicyDocument.organization_id == actor.organization_id,
            PolicyChunk.policy_id == PolicyDocument.id,
            PolicySearchIndex.enabled.is_(True),
        )
    )
    if policy_ids:
        statement = statement.where(PolicyDocument.id.in_(policy_ids))
    if language:
        if language not in {"ar", "en"}:
            raise HTTPException(422, "Invalid source language.")
        statement = statement.where(SearchPassage.language == language)
    rows = db.execute(
        statement.order_by(SearchPassage.id).limit(MAX_CANDIDATES + 1)
    ).all()
    if len(rows) > MAX_CANDIDATES:
        raise HTTPException(
            409, "Search scope exceeds the bounded corpus; select fewer policies."
        )
    eligible, stale = [], 0
    for passage, chunk, policy in rows:
        if passage.source_hash != source_hash(
            chunk.text
        ) or not 0 <= passage.start < passage.end <= len(chunk.text):
            stale += 1
            continue
        eligible.append((passage, chunk, policy))
    texts = [chunk.text[passage.start : passage.end] for passage, chunk, _ in eligible]
    lexical = bm25(query, texts)
    vectors, warning = {}, None
    semantic_evaluated = False
    if method != "lexical" and eligible and tokens(query):
        try:
            if encoder == "configured":
                encoder = semantic.configured_encoder()
            if encoder:
                candidates = [
                    (position, row[0])
                    for position, row in enumerate(eligible)
                    if row[0].model_id == encoder.identity
                    and row[0].embedding is not None
                ]
                if candidates:
                    query_vector = semantic.unit_vector(encoder.embed([query])[0])
                    for position, passage in candidates:
                        try:
                            vector = semantic.unit_vector(passage.embedding)
                            score = sum(a * b for a, b in zip(vector, query_vector))
                            semantic_evaluated = True
                            if math.isfinite(score) and score >= SEMANTIC_THRESHOLD:
                                vectors[position] = score
                        except (ValueError, TypeError):
                            continue
                if len(candidates) < len(eligible):
                    warning = "Some passages need semantic reindexing."
            else:
                warning = "Semantic model is not configured; keyword retrieval only."
        except semantic.EmbeddingUnavailable:
            warning = "Semantic model is unavailable; keyword retrieval only."
            encoder = None
    else:
        encoder = None
    if method == "semantic" and (not semantic_evaluated or warning):
        raise HTTPException(
            503, "Semantic retrieval requires a verified model and current embeddings."
        )
    rankings = []
    if method != "semantic":
        rankings.append(
            sorted(
                (i for i, score in enumerate(lexical) if score > 0),
                key=lambda i: (-lexical[i], eligible[i][0].id),
            )
        )
    if method != "lexical":
        rankings.append(sorted(vectors, key=lambda i: (-vectors[i], eligible[i][0].id)))
    scores = {}
    for ranking in rankings:
        for rank, position in enumerate(ranking, 1):
            scores[position] = scores.get(position, 0.0) + 1 / (60 + rank)
    results, seen = [], set()
    for position in sorted(scores, key=lambda i: (-scores[i], eligible[i][0].id)):
        passage, chunk, policy = eligible[position]
        quote = chunk.text[passage.start : passage.end]
        # Deduplicate repeated source text, but do not merge different policies/tenants.
        key = (policy.id, quote)
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "citation_id": passage.id,
                "policy_id": policy.id,
                "filename": policy.original_filename,
                "chunk_id": chunk.id,
                "chunk_index": chunk.chunk_index,
                "start": passage.start,
                "end": passage.end,
                "source_hash": passage.source_hash,
                "quote": quote,
                "language": passage.language,
                "score": scores[position],
                "lexical_score": lexical[position],
                "semantic_score": vectors.get(position),
                "source_verified": True,
                "original_url": f"/policies/{policy.id}/original",
            }
        )
        if len(results) == limit:
            break
    return {
        "status": "evidence_found" if results else "no_evidence",
        "results": results,
        "mode": "hybrid"
        if semantic_evaluated and method == "hybrid"
        else method
        if method != "hybrid"
        else "lexical",
        "warning": warning,
        "stale_passages_excluded": stale,
        "candidate_count": len(eligible),
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        "coverage": "retrieved_source_only_not_policy_approval",
    }
