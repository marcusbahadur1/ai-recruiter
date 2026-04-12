"""RAG knowledge base management routes.

POST   /rag/scrape          — trigger website crawl for this tenant
POST   /rag/documents       — upload a document (PDF/DOCX/TXT)
DELETE /rag/documents/{id}  — delete a knowledge base document (GDPR erasure)
GET    /rag/documents       — list tenant's knowledge base documents
"""

import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.rag_document import RagDocument
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.common import PaginatedResponse
from app.schemas.rag_document import RagDocumentResponse
from app.services import rag_pipeline
from pydantic import BaseModel

router = APIRouter(prefix="/rag", tags=["rag"])

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


# ── Schemas ───────────────────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    url: str  # validated loosely — crawl4ai handles bad URLs gracefully


class ScrapeResponse(BaseModel):
    chunks_stored: int
    url: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/scrape", response_model=ScrapeResponse, status_code=status.HTTP_202_ACCEPTED)
async def scrape_website(
    body: ScrapeRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> ScrapeResponse:
    """Crawl the given URL and store all page chunks in the knowledge base.

    For large sites this may be slow — consider moving to a Celery task for
    production (the Celery beat task ``rag_refresh`` calls this service directly).
    """
    _require_widget_plan(tenant)

    docs = await rag_pipeline.scrape_website(
        db=db,
        tenant_id=tenant.id,
        url=str(body.url),
        tenant=tenant,
    )
    return ScrapeResponse(chunks_stored=len(docs), url=str(body.url))


@router.post("/documents", response_model=list[RagDocumentResponse], status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> list[RagDocumentResponse]:
    """Upload a PDF, DOCX, or TXT file; extract text and store chunks."""
    _require_widget_plan(tenant)

    if file.size and file.size > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 20 MB limit",
        )

    filename = file.filename or "upload.bin"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("pdf", "docx", "txt"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported file type. Upload PDF, DOCX, or TXT.",
        )

    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds 20 MB limit",
        )

    docs = await rag_pipeline.upload_document(
        db=db,
        tenant_id=tenant.id,
        file_content=content,
        filename=filename,
        tenant=tenant,
    )
    return [RagDocumentResponse.model_validate(d) for d in docs]


@router.get("/documents", response_model=PaginatedResponse[RagDocumentResponse])
async def list_documents(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
) -> PaginatedResponse[RagDocumentResponse]:
    """List all RAG documents for this tenant's knowledge base."""
    _require_widget_plan(tenant)

    from sqlalchemy import func

    result = await db.execute(
        select(RagDocument)
        .where(RagDocument.tenant_id == tenant.id)
        .order_by(RagDocument.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    docs = list(result.scalars().all())

    count_result = await db.execute(
        select(func.count())
        .select_from(RagDocument)
        .where(RagDocument.tenant_id == tenant.id)
    )
    total = count_result.scalar_one()

    return PaginatedResponse(
        items=[RagDocumentResponse.model_validate(d) for d in docs],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a knowledge base document (GDPR right to erasure)."""
    _require_widget_plan(tenant)

    result = await db.execute(
        select(RagDocument).where(
            RagDocument.id == document_id,
            RagDocument.tenant_id == tenant.id,  # strict tenant scope
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    await db.delete(doc)
    await db.commit()


# ── Guard ─────────────────────────────────────────────────────────────────────

_WIDGET_PLANS = {"small_firm", "mid_firm", "enterprise"}


def _require_widget_plan(tenant: Tenant) -> None:
    """Raise 403 if the tenant's plan does not include the Chat Widget feature."""
    if tenant.plan not in _WIDGET_PLANS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chat Widget & RAG features require Small Firm plan or above",
        )
