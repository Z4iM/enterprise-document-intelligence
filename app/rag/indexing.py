"""Derived, source-bound policy indexes; never changes original files or approved rules."""

import hashlib
import uuid

from sqlalchemy import delete, select

from app.database.models import (
    PolicyChunk,
    PolicySearchIndex,
    ProcessingJob,
    SearchPassage,
    utc_now_naive,
)
from app.jobs.queue import enqueue
from app.rag import semantic
from app.rag.chunking import chunk_text
from app.rag.lexical import ARABIC

MAX_SOURCE_CHARACTERS = 60_000
MAX_PASSAGES = 400


def source_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_digest(chunks):
    return source_hash(
        "\n".join(f"{chunk.id}:{source_hash(chunk.text)}" for chunk in chunks)
    )


def request_index(db, policy_id, actor, *, force=False):
    index = db.get(PolicySearchIndex, policy_id)
    if index is None:
        index = PolicySearchIndex(policy_id=policy_id, state="queued", enabled=True)
        db.add(index)
    elif not force and (not index.enabled or index.state == "ready"):
        return None
    job = enqueue(db, "policy_index", policy_id, actor)
    if job.state in {"running", "queued", "retry_wait"} and job.attempts:
        return job
    index.enabled, index.state = True, "queued"
    if job.state in {"completed", "failed"}:
        job.state, job.attempts, job.error = "queued", 0, None
        job.lease_token, job.lease_until = None, None
        job.available_at, job.actor_id = utc_now_naive(), actor.id
    return job


def remove_index(db, policy_id):
    index = db.get(PolicySearchIndex, policy_id)
    if index is None:
        index = PolicySearchIndex(policy_id=policy_id, state="removed", enabled=False)
        db.add(index)
    index.enabled, index.state, index.passage_count = False, "removed", 0
    index.model_id, index.source_digest, index.updated_at = None, None, utc_now_naive()
    db.execute(delete(SearchPassage).where(SearchPassage.policy_id == policy_id))
    job = db.scalar(
        select(ProcessingJob).where(
            ProcessingJob.kind == "policy_index", ProcessingJob.resource_id == policy_id
        )
    )
    if job:
        # Cancel the claim atomically with removal. A stale worker fails its completion fence.
        job.state, job.error = (
            "failed",
            "Search index removed by an authorized reviewer.",
        )
        job.lease_token, job.lease_until = None, None


def lexical_spans(text):
    for start in range(0, len(text), 340):
        end = min(start + 400, len(text))
        if text[start:end].strip():
            yield start, end


def build_index(db, policy, text, encoder="configured"):
    index = db.get(PolicySearchIndex, policy.id)
    if index is None or not index.enabled:
        return
    chunks = db.scalars(
        select(PolicyChunk)
        .where(PolicyChunk.policy_id == policy.id)
        .order_by(PolicyChunk.chunk_index)
    ).all()
    if not chunks:
        chunks = [
            PolicyChunk(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, f"edi:{policy.id}:{position}")),
                policy_id=policy.id,
                chunk_index=position,
                text=part,
            )
            for position, part in enumerate(chunk_text(text))
        ]
    if not chunks or sum(len(chunk.text) for chunk in chunks) > MAX_SOURCE_CHARACTERS:
        raise ValueError("Policy exceeds the bounded search indexing budget.")
    if [chunk.text for chunk in chunks] != chunk_text(text):
        raise ValueError("Stored policy chunks differ from the parsed original.")
    if encoder == "configured":
        encoder = semantic.configured_encoder()
    spans = getattr(encoder, "spans", lexical_spans)
    records, passages = [], []
    for chunk in chunks:
        for start, end in spans(chunk.text):
            quote = chunk.text[start:end]
            if not quote.strip():
                continue
            records.append((chunk, start, end, source_hash(chunk.text)))
            passages.append(quote)
            if len(records) > MAX_PASSAGES:
                raise ValueError("Policy exceeds the passage indexing budget.")
    # Inference precedes all business writes; original source remains unchanged.
    existing = {
        (
            item.chunk_id,
            item.start,
            item.end,
            item.source_hash,
            item.model_id,
        ): item.embedding
        for item in db.scalars(
            select(SearchPassage).where(SearchPassage.policy_id == policy.id)
        )
    }
    embeddings = [None] * len(passages)
    missing = []
    if encoder:
        for position, (chunk, start, end, digest_chunk) in enumerate(records):
            cached = existing.get(
                (chunk.id, start, end, digest_chunk, encoder.identity)
            )
            try:
                embeddings[position] = (
                    semantic.unit_vector(cached) if cached is not None else None
                )
            except (ValueError, TypeError):
                pass
            if embeddings[position] is None:
                missing.append(position)
        generated = (
            encoder.embed([passages[position] for position in missing])
            if missing
            else []
        )
        if len(generated) != len(missing):
            raise ValueError("Incomplete embedding result.")
        for position, vector in zip(missing, generated):
            embeddings[position] = semantic.unit_vector(vector)
    if len(embeddings) != len(records):
        raise ValueError("Incomplete embedding result.")
    if encoder:
        embeddings = [semantic.unit_vector(vector) for vector in embeddings]
    digest = source_digest(chunks)
    db.execute(delete(SearchPassage).where(SearchPassage.policy_id == policy.id))
    for chunk in chunks:
        if chunk not in db:
            db.add(chunk)
    db.flush()
    for (chunk, start, end, digest_chunk), embedding in zip(records, embeddings):
        quote = chunk.text[start:end]
        language = "ar" if ARABIC.search(quote) else "en"
        db.add(
            SearchPassage(
                id=str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"edi-search:{chunk.id}:{start}:{end}:{digest_chunk}",
                    )
                ),
                policy_id=policy.id,
                chunk_id=chunk.id,
                start=start,
                end=end,
                source_hash=digest_chunk,
                language=language,
                embedding=embedding,
                model_id=encoder.identity if encoder else None,
            )
        )
    policy.extracted_text = text
    index.state, index.source_digest, index.passage_count = (
        "ready",
        digest,
        len(records),
    )
    index.model_id, index.updated_at = (
        encoder.identity if encoder else None,
        utc_now_naive(),
    )
