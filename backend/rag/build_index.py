"""
build_index.py — SentinelX AI Phase 2 / RAG Layer
===================================================
One-time script that reads all markdown files from rag/mitre_kb/,
embeds them with sentence-transformers/all-MiniLM-L6-v2 (local, no API key),
and persists the ChromaDB vector index to rag/chroma_db/.

IMPORTANT: Run this BEFORE starting the FastAPI server.

Usage (from the SentinelX-AI/ project root):
    python backend/rag/build_index.py

NOTE: Uses chromadb's native SentenceTransformerEmbeddingFunction instead of
langchain_huggingface to avoid TF/transformers version conflicts on this machine.
"""

import logging
import shutil
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_RAG_DIR = Path(__file__).parent
KB_DIR = _RAG_DIR / "mitre_kb"
CHROMA_DIR = _RAG_DIR / "chroma_db"
COLLECTION_NAME = "mitre_kb"


def build_index() -> None:
    """
    Build the ChromaDB vector index from all documents in rag/mitre_kb/.

    Process:
        1. Discover all .md and .txt files in mitre_kb/.
        2. Load each file as a LangChain Document with metadata.
        3. Initialise the all-MiniLM-L6-v2 embedding model (local CPU).
        4. Delete any existing index at chroma_db/ (clean rebuild).
        5. Embed all documents and persist the ChromaDB collection.

    Raises:
        FileNotFoundError: If mitre_kb/ is empty or does not exist.
        ImportError:       If required packages are not installed.
    """
    # ── Discover documents ────────────────────────────────────────────────────
    doc_files = sorted(list(KB_DIR.glob("*.md")) + list(KB_DIR.glob("*.txt")))
    if not doc_files:
        raise FileNotFoundError(
            f"No .md or .txt files found in {KB_DIR}. "
            "Ensure rag/mitre_kb/ contains the MITRE knowledge base files."
        )
    logger.info(f"Discovered {len(doc_files)} documents in {KB_DIR}")

    # ── Load documents ────────────────────────────────────────────────────────
    from langchain_core.documents import Document

    documents: list[Document] = []
    for path in doc_files:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            logger.warning(f"  Skipping empty file: {path.name}")
            continue
        # Extract technique_id from filename prefix (e.g. "T1059_..." → "T1059")
        stem = path.stem
        technique_id = stem.split("_")[0] if "_" in stem else stem
        documents.append(
            Document(
                page_content=text,
                metadata={"filename": path.name, "technique_id": technique_id},
            )
        )
        logger.info(f"  Loaded [{technique_id}] {path.name} ({len(text)} chars)")

    logger.info(f"Total documents to index: {len(documents)}")

    # ── Load embedding model ──────────────────────────────────────────────────
    logger.info("Loading embedding model: sentence-transformers/all-MiniLM-L6-v2 ...")
    logger.info("(First run downloads ~90 MB; subsequent runs use local cache.)")

    # Use chromadb's native embedding function to avoid langchain_huggingface /
    # transformers TF-Keras version conflicts in the current environment.
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    from langchain_core.embeddings import Embeddings as LCEmbeddings

    # Thin wrapper so langchain_chroma's Chroma.from_documents() can consume it
    class _STEmbeddings(LCEmbeddings):
        """Wraps chromadb's SentenceTransformerEmbeddingFunction for LangChain."""

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
    logger.info("Embedding model loaded.")

    # ── Clean rebuild ─────────────────────────────────────────────────────────
    if CHROMA_DIR.exists():
        logger.info(f"Removing existing index at {CHROMA_DIR} ...")
        shutil.rmtree(CHROMA_DIR)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    # ── Build and persist ChromaDB collection ─────────────────────────────────
    logger.info("Embedding documents and building ChromaDB collection ...")
    from langchain_chroma import Chroma

    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=str(CHROMA_DIR),
    )

    indexed_count = vectorstore._collection.count()
    logger.info("=" * 60)
    logger.info(f"  Index built: {indexed_count} documents indexed")
    logger.info(f"  Persisted at: {CHROMA_DIR.resolve()}")
    logger.info("  You can now start the FastAPI server:")
    logger.info("    uvicorn backend.main:app --reload")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        build_index()
    except FileNotFoundError as exc:
        logger.error(f"Build failed — file not found: {exc}")
        sys.exit(1)
    except ImportError as exc:
        logger.error(
            f"Missing dependency: {exc}\n"
            "Install requirements: pip install -r backend/requirements.txt"
        )
        sys.exit(1)
    except Exception as exc:
        logger.error(f"Unexpected error during index build: {exc}", exc_info=True)
        sys.exit(1)
