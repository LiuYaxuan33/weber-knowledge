import os
# Must be set before any huggingface_hub import (inside SentenceTransformer)
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from abc import ABC, abstractmethod
import numpy as np

class EmbeddingModel(ABC):
    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    @abstractmethod
    def embed_query(self, text: str) -> list[float]: ...


class OpenAIEmbedding(EmbeddingModel):
    def __init__(self, model: str = "text-embedding-3-small"):
        from openai import OpenAI
        self.model = model
        self.client = OpenAI()
        self._dim = 1536

    @property
    def dim(self) -> int:
        return self._dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        batch_size = 20
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            resp = self.client.embeddings.create(model=self.model, input=batch)
            embeddings.extend([d.embedding for d in resp.data])
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class BGEM3Embedding(EmbeddingModel):
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        from sentence_transformers import SentenceTransformer
        import config
        device = config.EMBEDDING_DEVICE or None
        self.model = SentenceTransformer(model_name, device=device)
        self._dim = self.model.get_sentence_embedding_dimension() or 512
        self._batch_size = getattr(config, 'EMBEDDING_BATCH_SIZE', 2)

    @property
    def dim(self) -> int:
        return self._dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=True,
            batch_size=self._batch_size
        )
        return embeddings.tolist()

    def embed_query(self, text: str) -> list[float]:
        embedding = self.model.encode(
            [text], normalize_embeddings=True
        )
        return embedding[0].tolist()


def create_embedding_model(model_name: str | None = None) -> EmbeddingModel:
    import config
    import os
    name = model_name or config.EMBEDDING_MODEL
    if name.startswith("text-embedding"):
        if not os.environ.get("OPENAI_API_KEY") or os.environ["OPENAI_API_KEY"].startswith("your_"):
            print("WARNING: No OpenAI API key found. Falling back to local BGE-small-zh.")
            print("  Set OPENAI_API_KEY in .env to use OpenAI embeddings.")
            return BGEM3Embedding("BAAI/bge-small-zh-v1.5")
        return OpenAIEmbedding(name)
    else:
        return BGEM3Embedding(name)
