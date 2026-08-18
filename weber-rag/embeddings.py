from abc import ABC, abstractmethod
import os


class EmbeddingConfigurationError(RuntimeError):
    """Raised when the configured embedding provider cannot be initialized."""

class EmbeddingModel(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]: ...


class OpenAIEmbedding(EmbeddingModel):
    def __init__(self, model: str = "text-embedding-3-small"):
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        if not api_key or api_key.startswith("your_"):
            raise EmbeddingConfigurationError(
                "OPENAI_API_KEY 未配置，无法使用 OpenAI 嵌入模型。"
            )
        self.model = model
        self.client = OpenAI()
        self._dim = 1536

    @property
    def model_name(self) -> str:
        return self.model

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
        import config
        if config.HF_HUB_OFFLINE:
            # Must be set before importing sentence_transformers/huggingface_hub.
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from sentence_transformers import SentenceTransformer

        self._model_name = model_name
        device = config.EMBEDDING_DEVICE or None
        self.model = SentenceTransformer(model_name, device=device)
        self._dim = self.model.get_embedding_dimension() or 512
        self._batch_size = getattr(config, 'EMBEDDING_BATCH_SIZE', 2)

    @property
    def model_name(self) -> str:
        return self._model_name

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
    name = model_name or config.EMBEDDING_MODEL
    if name.startswith("text-embedding"):
        return OpenAIEmbedding(name)
    return BGEM3Embedding(name)
