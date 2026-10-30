"""Reproducible synthetic retrieval metrics, with an explicit offline local encoder."""

import argparse
import hashlib
import json
import math
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path


def metrics(observations):
    positive = [row for row in observations if row["answerable"]]
    negative = [row for row in observations if not row["answerable"]]
    latency = sorted(row["latency_ms"] for row in observations)
    citations = sum(row["citations"] for row in observations)
    return {
        "queries": len(observations),
        "answerable": len(positive),
        "unanswerable": len(negative),
        "recall_at_5": round(statistics.mean(row["recall"] for row in positive), 4),
        "mrr_at_5": round(
            statistics.mean(row["reciprocal_rank"] for row in positive), 4
        ),
        "citation_integrity": round(
            sum(row["verified_citations"] for row in observations) / citations, 4
        )
        if citations
        else None,
        "citation_relevance_precision_at_5": round(
            sum(row["relevant_citations"] for row in observations) / citations, 4
        )
        if citations
        else None,
        "unanswerable_abstention_rate": round(
            sum(row["abstained"] for row in negative) / len(negative), 4
        )
        if negative
        else None,
        "answerable_false_abstention_rate": round(
            sum(row["abstained"] for row in positive) / len(positive), 4
        ),
        "warm_latency_p50_ms": round(statistics.median(latency), 2),
        "warm_latency_p95_ms": round(
            latency[max(0, math.ceil(len(latency) * 0.95) - 1)], 2
        ),
    }


def evaluate(engine, corpus, encoder):
    from sqlalchemy.orm import sessionmaker

    from app.auth.security import Principal
    from app.database.database import Base
    from app.database.models import PolicyDocument, PolicySearchIndex
    from app.rag.indexing import build_index
    from app.rag.search import search_evidence

    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False)
    started = time.perf_counter()
    with sessions() as db:
        for document in corpus["documents"]:
            policy = PolicyDocument(
                id=document["id"],
                organization_id="synthetic-evaluation",
                owner_id="synthetic-evaluator",
                original_filename=document["id"] + ".txt",
                stored_file_path="synthetic-evaluation-only",
                file_hash=hashlib.sha256(document["text"].encode()).hexdigest(),
                extracted_text=document["text"],
            )
            db.add(policy)
            db.flush()
            db.add(PolicySearchIndex(policy_id=policy.id))
            db.flush()
            build_index(db, policy, document["text"], encoder=encoder)
        db.commit()
    index_ms = round((time.perf_counter() - started) * 1000, 2)
    actor = Principal("synthetic-evaluator", "synthetic-evaluation", "employee")
    sources = {document["id"]: document for document in corpus["documents"]}
    reports = {}
    for method in ["lexical", "semantic", "hybrid"] if encoder else ["lexical"]:
        observations = []
        with sessions() as db:
            for query in corpus["queries"]:
                relevant = {
                    document["id"]
                    for document in corpus["documents"]
                    if query["topic"] and document["topic"] == query["topic"]
                }
                result = search_evidence(
                    db, actor, query["query"], method=method, encoder=encoder
                )
                hits = result["results"]
                found = {hit["policy_id"] for hit in hits} & relevant
                first = next(
                    (
                        position
                        for position, hit in enumerate(hits, 1)
                        if hit["policy_id"] in relevant
                    ),
                    None,
                )
                supported = sum(
                    hit["quote"] in sources[hit["policy_id"]]["text"]
                    and hit["source_verified"]
                    for hit in hits
                )
                observations.append(
                    {
                        "query_id": query["id"],
                        "language": query["language"],
                        "answerable": bool(relevant),
                        "recall": len(found) / len(relevant) if relevant else 0,
                        "reciprocal_rank": 1 / first if first else 0,
                        "citations": len(hits),
                        "verified_citations": supported,
                        "relevant_citations": sum(
                            hit["policy_id"] in relevant for hit in hits
                        ),
                        "abstained": not hits,
                        "latency_ms": result["latency_ms"],
                        "retrieved_policy_ids": [hit["policy_id"] for hit in hits],
                    }
                )
        reports[method] = {
            "overall": metrics(observations),
            "by_language": {
                language: metrics(
                    [row for row in observations if row["language"] == language]
                )
                for language in ("en", "ar")
            },
            "per_query": observations,
        }
    return {"index_ms": index_ms, "methods": reports}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-directory")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    corpus_path = Path(__file__).with_name("corpus.json")
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="edi-retrieval-eval-") as temporary:
        os.environ.update(
            PYTHON_DOTENV_DISABLED="1",
            EDI_DATABASE_URL=f"sqlite:///{Path(temporary).as_posix()}/evaluation.db",
            EDI_DATA_ROOT=temporary,
            LLM_PROVIDER="disabled",
        )
        os.environ.pop("GEMINI_API_KEY", None)
        from sqlalchemy import create_engine

        from app.rag.semantic import LocalEncoder

        encoder = LocalEncoder(args.model_directory) if args.model_directory else None
        engine = create_engine(os.environ["EDI_DATABASE_URL"])
        try:
            report = evaluate(engine, corpus, encoder)
        finally:
            engine.dispose()
    report.update(
        corpus=corpus["version"],
        corpus_sha256=hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        documents=len(corpus["documents"]),
        queries=len(corpus["queries"]),
        model_id=encoder.identity if encoder else None,
        environment={
            "os": platform.system(),
            "python": platform.python_version(),
            "logical_cpus": os.cpu_count(),
            "encoder_threads": 1,
        },
        scope="Synthetic retrieval only; exact-source citation integrity is not answer correctness. No generative model/network inference. Timings exclude model load and include SQL/ranking; not a load test.",
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {method: values["overall"] for method, values in report["methods"].items()},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
