from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingService:

    def __init__(self):
        self.model = SentenceTransformer(MODEL_NAME)

    def embed_texts(
        self,
        texts: list[str]
    ):
        return self.model.encode(
            texts,
            normalize_embeddings=True
        )

    def embed_query(
        self,
        query: str
    ):
        return self.model.encode(
            [query],
            normalize_embeddings=True
        )[0]