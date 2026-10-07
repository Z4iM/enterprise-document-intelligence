from pathlib import Path
import json

import faiss
import numpy as np


VECTOR_DIR = Path("data/vector_store")

INDEX_PATH = VECTOR_DIR / "policies.index"
METADATA_PATH = VECTOR_DIR / "policy_chunks.json"


class PolicyVectorStore:

    def __init__(
        self,
        embedding_dimension: int = 384
    ):
        VECTOR_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        self.embedding_dimension = embedding_dimension

        self.index = faiss.IndexFlatIP(
            embedding_dimension
        )

        self.metadata = []

        self.load()


    def add(
        self,
        embeddings,
        chunk_records: list[dict]
    ):
        embeddings = np.asarray(
            embeddings,
            dtype="float32"
        )

        self.index.add(embeddings)

        self.metadata.extend(chunk_records)

        self.save()


    def search(
        self,
        query_embedding,
        top_k: int = 3
    ) -> list[dict]:

        if self.index.ntotal == 0:
            return []

        query_embedding = np.asarray(
            [query_embedding],
            dtype="float32"
        )

        scores, indices = self.index.search(
            query_embedding,
            top_k
        )

        results = []

        for score, index in zip(
            scores[0],
            indices[0]
        ):
            if index == -1:
                continue

            metadata = self.metadata[index].copy()

            metadata["similarity_score"] = float(
                score
            )

            results.append(metadata)

        return results


    def save(self):
        faiss.write_index(
            self.index,
            str(INDEX_PATH)
        )

        with open(
            METADATA_PATH,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                self.metadata,
                file,
                indent=2
            )


    def load(self):

        if INDEX_PATH.exists():
            self.index = faiss.read_index(
                str(INDEX_PATH)
            )

        if METADATA_PATH.exists():
            with open(
                METADATA_PATH,
                "r",
                encoding="utf-8"
            ) as file:
                self.metadata = json.load(file)

    def reset(self):

        self.index = faiss.IndexFlatIP(
            self.embedding_dimension
    )

        self.metadata = []

        self.save()