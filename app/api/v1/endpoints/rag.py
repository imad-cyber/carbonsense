"""
RAG endpoints — regulatory Q&A, PDF ingestion and CSRD report streaming.

Streaming endpoints use Server-Sent Events (SSE) via sse-starlette.
Stream format:  data: {"chunk": "text here", "done": false}
Final message:  data: {"chunk": "", "done": true}
"""
import json
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.core.config import settings
from app.core.dependencies import require_analyst_or_above, require_any_authenticated
from app.db.database import get_db
from app.ml.csrd_report_generator import report_generator
from app.ml.vector_store_manager import vector_store_manager
from app.models.user import User
from app.schemas.emission import TaskStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=2000)
    company_id: int | None = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    k: int = Field(default=5, ge=1, le=20)


def _require_llm_configured() -> None:
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM not configured — set OPENAI_API_KEY in .env",
        )


def _require_store_ready() -> None:
    if not vector_store_manager.is_ready():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Vector store not initialised — POST /api/v1/rag/ingest/regulatory first"
            ),
        )


def _sse_event(chunk: str, done: bool) -> dict:
    return {"data": json.dumps({"chunk": chunk, "done": done})}


@router.post("/ingest/regulatory")
def ingest_regulatory(_: User = Depends(require_analyst_or_above)):
    """Ingest the built-in CSRD/ESRS regulatory texts into the FAISS store."""
    _require_llm_configured()
    try:
        chunks = vector_store_manager.ingest_regulatory_text()
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG dependencies not installed — pip install -r requirements.txt",
        )
    return {"status": "ingested", "chunks": chunks}


@router.post("/ingest/pdf")
def ingest_pdf(file: UploadFile, _: User = Depends(require_analyst_or_above)):
    """Upload a regulatory PDF and ingest it into the FAISS store."""
    _require_llm_configured()

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only PDF files are supported",
        )

    # PyPDFLoader needs a real file path — write the upload to a temp file
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name

    try:
        chunks = vector_store_manager.ingest_pdf(tmp_path)
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG dependencies not installed — pip install -r requirements.txt",
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {"status": "ingested", "filename": file.filename, "chunks": chunks}


@router.get("/status")
def rag_status(_: User = Depends(require_any_authenticated)):
    """Report whether the RAG pipeline is ready to answer questions."""
    ready = vector_store_manager.is_ready()
    return {
        "ready": ready and bool(settings.OPENAI_API_KEY),
        "document_count": vector_store_manager.document_count(),
        "llm_configured": bool(settings.OPENAI_API_KEY),
    }


@router.post("/chat")
async def rag_chat(
    payload: ChatRequest,
    _: User = Depends(require_any_authenticated),
):
    """
    Ask a question about carbon regulations. Streams the answer via SSE.
    """
    _require_llm_configured()
    _require_store_ready()

    from app.ml.rag_chain import build_qa_chain, stream_rag_response

    chain = build_qa_chain()
    if chain is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Vector store not initialised",
        )

    async def event_generator():
        try:
            async for chunk in stream_rag_response(payload.question, chain):
                yield _sse_event(chunk, done=False)
        except Exception as e:  # LLM/network failures surface as an SSE error chunk
            logger.error(f"RAG chat streaming failed: {e}")
            yield _sse_event(f"[error] {e}", done=False)
        yield _sse_event("", done=True)

    return EventSourceResponse(event_generator())


@router.get("/report/{company_id}/{year}")
async def stream_csrd_report(
    company_id: int,
    year: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_any_authenticated),
):
    """Stream a full ESRS E1 CSRD report for a company/year via SSE."""
    _require_llm_configured()
    _require_store_ready()

    async def event_generator():
        try:
            async for chunk in report_generator.generate_full_report(company_id, year, db):
                yield _sse_event(chunk, done=False)
        except HTTPException as e:
            yield _sse_event(f"[error] {e.detail}", done=False)
        except Exception as e:
            logger.error(f"CSRD report streaming failed: {e}")
            yield _sse_event(f"[error] {e}", done=False)
        yield _sse_event("", done=True)

    return EventSourceResponse(event_generator())


@router.post(
    "/report/{company_id}/{year}/async",
    response_model=TaskStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def queue_csrd_report(
    company_id: int,
    year: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_analyst_or_above),
):
    """Queue CSRD report generation as a Celery task."""
    _require_llm_configured()

    from app.services.company_service import CompanyService
    from app.worker.tasks import generate_csrd_report

    CompanyService.get_by_id(db, company_id)
    task = generate_csrd_report.delay(company_id, year)

    return TaskStatusResponse(
        task_id=task.id,
        status="queued",
        message=f"CSRD report queued for company {company_id}, year {year}. "
                f"Poll /api/v1/tasks/{task.id} for status.",
    )


@router.post("/search")
def search_regulations(
    payload: SearchRequest,
    _: User = Depends(require_any_authenticated),
):
    """Similarity search over the regulatory knowledge base."""
    _require_llm_configured()
    _require_store_ready()

    results = vector_store_manager.search(payload.query, k=payload.k)
    return {"query": payload.query, "results": results}
