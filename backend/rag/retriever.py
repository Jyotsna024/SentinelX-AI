"""
retriever.py — SentinelX AI Phase 2 / RAG Layer
=================================================
Loads the pre-built ChromaDB vector index and exposes a LangChain
VectorStoreRetriever for similarity search.

The retriever MUST be loaded at startup by calling load_retriever() from
main.py's lifespan handler. If the ChromaDB index does not exist at
rag/chroma_db/, startup fails with a clear error and instructions for
running build_index.py.

The module-level singleton is used across all requests so the embedding
model is loaded only once.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_RAG_DIR = Path(__file__).parent
CHROMA_DIR = _RAG_DIR / "chroma_db"
COLLECTION_NAME = "mitre_kb"

# ── Module-level singleton ─────────────────────────────────────────────────────
_retriever = None  # type: Optional[object]


def load_retriever() -> None:
    """
    Load the ChromaDB index and initialise the LangChain retriever singleton.

    Must be called once at FastAPI startup (via lifespan handler in main.py).
    Subsequent calls are no-ops (idempotent).

    Uses sentence-transformers/all-MiniLM-L6-v2 for local CPU-based embeddings.
    No API key is required for the retriever or embeddings.

    Raises:
        FileNotFoundError: If rag/chroma_db/ does not exist or is empty,
            with clear instructions to run build_index.py first.
        ImportError:       If required packages are not installed.
    """
    global _retriever

    if _retriever is not None:
        logger.debug("load_retriever() called again — already loaded, skipping.")
        return

    # ── Validate that the index was pre-built ─────────────────────────────────
    if not CHROMA_DIR.exists() or not any(CHROMA_DIR.iterdir()):
        raise FileNotFoundError(
            f"ChromaDB index not found at: {CHROMA_DIR.resolve()}\n\n"
            "The vector index must be built before starting the server.\n"
            "Run the following command from the SentinelX-AI/ project root:\n\n"
            "    python backend/rag/build_index.py\n\n"
            "This only needs to be done once (or when mitre_kb/ files change)."
        )

    logger.info(f"Loading ChromaDB collection '{COLLECTION_NAME}' from {CHROMA_DIR} ...")

    from langchain_chroma import Chroma
    from langchain_core.embeddings import Embeddings as LCEmbeddings
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    class _STEmbeddings(LCEmbeddings):
        """Wraps chromadb's SentenceTransformerEmbeddingFunction for LangChain.
        Avoids importing langchain_huggingface which triggers TF/transformers
        version conflicts in environments with mismatched keras/tokenizers."""

        def __init__(self, model_name: str) -> None:
            self._fn = SentenceTransformerEmbeddingFunction(
                model_name=model_name,
                normalize_embeddings=True,
            )

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return self._fn(texts)

        def embed_query(self, text: str) -> list[float]:
            return self._fn([text])[0]

    embeddings = _STEmbeddings("sentence-transformers/all-MiniLM-L6-v2")

    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(CHROMA_DIR),
    )

    doc_count = vectorstore._collection.count()
    logger.info(f"ChromaDB collection loaded: {doc_count} documents indexed.")

    _retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 5},
    )

    logger.info("RAG retriever ready (top-k=5 similarity search).")


def get_retriever():
    """
    Return the loaded LangChain VectorStoreRetriever.

    Returns:
        The singleton VectorStoreRetriever instance.

    Raises:
        RuntimeError: If load_retriever() has not been called at startup.
    """
    if _retriever is None:
        raise RuntimeError(
            "RAG retriever is not loaded. "
            "load_retriever() must be called at application startup."
        )
    return _retriever
