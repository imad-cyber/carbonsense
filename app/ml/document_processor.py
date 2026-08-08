"""
Document ingestion pipeline for the RAG layer.

Loads regulatory PDFs / raw text, splits them into overlapping chunks
and maintains a FAISS vector index on disk.

LangChain / FAISS imports are done lazily inside functions so the app
can start (and every non-RAG feature keeps working) even when the RAG
dependencies are not installed — graceful degradation.
"""
import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


def load_pdf(file_path: str) -> list:
    """Load a PDF file into LangChain Documents (one per page)."""
    from langchain_community.document_loaders import PyPDFLoader

    loader = PyPDFLoader(file_path)
    documents = loader.load()
    logger.info(f"Loaded {len(documents)} pages from {file_path}")
    return documents


def load_text(text: str, metadata: dict) -> list:
    """Wrap plain text in a LangChain Document for ingestion."""
    from langchain_core.documents import Document

    return [Document(page_content=text, metadata=metadata)]


def split_documents(
    docs: list,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list:
    """
    Split documents into overlapping chunks.

    Overlap matters: without it, a sentence cut in half at a chunk
    boundary is unrecoverable — the retriever would never surface it.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or settings.RAG_CHUNK_SIZE,
        chunk_overlap=chunk_overlap or settings.RAG_CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    logger.info(f"Split {len(docs)} documents into {len(chunks)} chunks")
    return chunks


def get_embeddings():
    """OpenAI embedding model — one function so the choice lives in one place."""
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(model=settings.EMBEDDING_MODEL)


def build_vector_store(documents: list):
    """Build a fresh FAISS index from documents and persist it to disk."""
    from langchain_community.vectorstores import FAISS

    store = FAISS.from_documents(documents, get_embeddings())
    store.save_local(settings.VECTOR_STORE_PATH)
    logger.info(
        f"FAISS store built with {len(documents)} chunks "
        f"→ saved to {settings.VECTOR_STORE_PATH}"
    )
    return store


def load_vector_store():
    """Load the persisted FAISS index. Returns None if it doesn't exist."""
    from langchain_community.vectorstores import FAISS

    index_path = Path(settings.VECTOR_STORE_PATH)
    if not (index_path / "index.faiss").exists():
        logger.warning(f"No FAISS index found at {index_path}")
        return None

    return FAISS.load_local(
        settings.VECTOR_STORE_PATH,
        get_embeddings(),
        # We only ever load indexes this app itself wrote
        allow_dangerous_deserialization=True,
    )


def add_documents_to_store(documents: list):
    """Add new documents to the existing store, or create one if missing."""
    store = load_vector_store()
    if store is None:
        return build_vector_store(documents)

    store.add_documents(documents)
    store.save_local(settings.VECTOR_STORE_PATH)
    logger.info(f"Added {len(documents)} chunks to existing FAISS store")
    return store
