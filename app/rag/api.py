"""Authenticated source retrieval and staff-only derived-index maintenance."""

import re
import threading

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.auth.security import (
    authorize_request,
    require_policy,
    require_reviewer,
    session_factory,
)
from app.database.models import (
    PolicyChunk,
    PolicyDocument,
    PolicySearchIndex,
    ProcessingJob,
    SearchPassage,
    SecurityEvent,
)
from app.rag.indexing import remove_index, request_index, source_hash
from app.rag.search import search_evidence

router = APIRouter(dependencies=[Depends(authorize_request)])
_search_slot = threading.BoundedSemaphore(1)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=500)
    policy_ids: list[str] | None = Field(default=None, max_length=20)
    limit: int = Field(default=5, ge=1, le=10)
    language: str | None = None


@router.post("/evidence/search")
def search(body: SearchRequest, request: Request):
    if not _search_slot.acquire(blocking=False):
        raise HTTPException(429, "Search is busy; retry shortly.")
    try:
        with session_factory(request)() as db:
            return search_evidence(
                db,
                request.state.actor,
                body.query,
                policy_ids=body.policy_ids,
                limit=body.limit,
                language=body.language,
            )
    finally:
        _search_slot.release()


@router.get("/policies/{policy_id}/index")
def status(policy_id: str, request: Request):
    with session_factory(request)() as db:
        require_policy(db, policy_id, request.state.actor)
        index = db.get(PolicySearchIndex, policy_id)
        job = db.scalar(
            select(ProcessingJob).where(
                ProcessingJob.kind == "policy_index",
                ProcessingJob.resource_id == policy_id,
            )
        )
        return {
            "state": index.state if index else "not_indexed",
            "enabled": index.enabled if index else False,
            "mode": "hybrid" if index and index.model_id else "lexical",
            "passage_count": index.passage_count if index else 0,
            "model_id": index.model_id if index else None,
            "job_state": job.state if job else None,
            "attempts": job.attempts if job else 0,
            "error": job.error if job and index and index.enabled else None,
        }


@router.post("/policies/{policy_id}/index")
def reindex(policy_id: str, request: Request, response: Response):
    require_reviewer(request.state.actor)
    with session_factory(request)() as db:
        require_policy(db, policy_id, request.state.actor)
        job = request_index(db, policy_id, request.state.actor, force=True)
        db.add(
            SecurityEvent(
                actor_id=request.state.actor.id,
                organization_id=request.state.actor.organization_id,
                resource_id=policy_id,
                action="policy_index_requested",
            )
        )
        db.commit()
        response.status_code = 202
        return {"state": "queued", "job_id": job.id}


@router.post("/policies/{policy_id}/index/remove")
def remove(policy_id: str, request: Request):
    require_reviewer(request.state.actor)
    with session_factory(request)() as db:
        require_policy(db, policy_id, request.state.actor)
        remove_index(db, policy_id)
        db.add(
            SecurityEvent(
                actor_id=request.state.actor.id,
                organization_id=request.state.actor.organization_id,
                resource_id=policy_id,
                action="policy_index_removed",
            )
        )
        db.commit()
    return {"state": "removed", "original_preserved": True}


@router.get("/evidence/citations/{citation_id}")
def citation(citation_id: str, request: Request):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", citation_id):
        raise HTTPException(404, "Citation not found.")
    with session_factory(request)() as db:
        row = db.execute(
            select(SearchPassage, PolicyChunk, PolicyDocument)
            .join(PolicyChunk, SearchPassage.chunk_id == PolicyChunk.id)
            .join(PolicyDocument, SearchPassage.policy_id == PolicyDocument.id)
            .join(PolicySearchIndex, PolicySearchIndex.policy_id == PolicyDocument.id)
            .where(
                SearchPassage.id == citation_id,
                PolicyDocument.organization_id == request.state.actor.organization_id,
                PolicyChunk.policy_id == PolicyDocument.id,
                PolicySearchIndex.enabled.is_(True),
            )
        ).one_or_none()
        if row is None:
            raise HTTPException(404, "Citation not found.")
        passage, chunk, policy = row
        if passage.source_hash != source_hash(
            chunk.text
        ) or not 0 <= passage.start < passage.end <= len(chunk.text):
            raise HTTPException(409, "Citation source changed; reindex the policy.")
        return {
            "citation_id": passage.id,
            "policy_id": policy.id,
            "filename": policy.original_filename,
            "chunk_id": chunk.id,
            "chunk_index": chunk.chunk_index,
            "start": passage.start,
            "end": passage.end,
            "source_hash": passage.source_hash,
            "quote": chunk.text[passage.start : passage.end],
            "source_verified": True,
            "coverage": "source_only_not_policy_approval",
        }
