"""
Embedding service — configurable provider.

EMBEDDING_PROVIDER=local  → SentenceTransformers (all-MiniLM-L6-v2, 384-dim) — default
EMBEDDING_PROVIDER=openai → langchain-openai OpenAIEmbeddings (requires OPENAI_API_KEY)

The SAME model is always used for both document ingestion and query embedding.
No hash/fake embeddings — only real model inference.
"""
from typing import List
from app.core.config import settings
from app.core.logging import logger


class EmbeddingService:
    def __init__(self):
        self.provider = settings.EMBEDDING_PROVIDER.lower()
        self.dimension = settings.EMBEDDING_DIMENSION
        self._client = None

        if self.provider == "local":
            self._init_local()
        elif self.provider == "openai":
            self._init_openai()
        else:
            logger.warning(
                f"Unknown EMBEDDING_PROVIDER='{self.provider}'. "
                "Defaulting to local SentenceTransformers."
            )
            self.provider = "local"
            self._init_local()

    # ------------------------------------------------------------------
    # Provider initialisation
    # ------------------------------------------------------------------

    def _init_local(self) -> None:
        """Load a local SentenceTransformers model (downloads on first use)."""
        model_name = settings.LOCAL_EMBEDDING_MODEL
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading local embedding model: {model_name}")
            self._client = SentenceTransformer(model_name)
            # Validate actual output dimension
            test_emb = self._client.encode(["test"])
            actual_dim = len(test_emb[0])
            if actual_dim != self.dimension:
                logger.warning(
                    f"Model '{model_name}' produces {actual_dim}-dim embeddings "
                    f"but EMBEDDING_DIMENSION={self.dimension}. "
                    f"Updating dimension to {actual_dim}."
                )
                self.dimension = actual_dim
            logger.info(
                f"Local embedding model ready: '{model_name}' — {self.dimension}-dim"
            )
        except ImportError:
            raise RuntimeError(
                "sentence-transformers is required for EMBEDDING_PROVIDER=local. "
                "Run: pip install sentence-transformers"
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialise local embedding model '{model_name}': {e}"
            )

    def _init_openai(self) -> None:
        """Initialise OpenAI embedding client (requires OPENAI_API_KEY)."""
        if not settings.OPENAI_API_KEY:
            raise RuntimeError(
                "EMBEDDING_PROVIDER=openai requires OPENAI_API_KEY to be set."
            )
        try:
            from langchain_openai import OpenAIEmbeddings
            self._client = OpenAIEmbeddings(
                model=settings.EMBEDDING_MODEL,
                openai_api_key=settings.OPENAI_API_KEY
            )
            logger.info(
                f"OpenAI embedding client ready: model='{settings.EMBEDDING_MODEL}'"
            )
        except ImportError:
            raise RuntimeError(
                "langchain-openai is required for EMBEDDING_PROVIDER=openai. "
                "Run: pip install langchain-openai"
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to initialise OpenAI embedding client: {e}"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query string."""
        if self.provider == "local":
            embedding = self._client.encode([text], convert_to_numpy=True)
            return embedding[0].tolist()
        else:
            # OpenAI provider
            return self._client.embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of document chunks."""
        if not texts:
            return []
        if self.provider == "local":
            embeddings = self._client.encode(texts, convert_to_numpy=True)
            return [emb.tolist() for emb in embeddings]
        else:
            # OpenAI provider
            return self._client.embed_documents(texts)


# Module-level singleton — shared across the application
embedding_service = EmbeddingService()
