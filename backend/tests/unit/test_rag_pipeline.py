"""Unit tests for the RAG pipeline service."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import rag_pipeline


# ── _chunk_text ────────────────────────────────────────────────────────────────


def test_chunk_text_short_returns_single_chunk():
    text = "Hello world. This is a short paragraph."
    chunks = rag_pipeline._chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_text_empty_returns_empty():
    assert rag_pipeline._chunk_text("") == []
    assert rag_pipeline._chunk_text("   \n\n  ") == []


def test_chunk_text_splits_long_text():
    # Create text that is definitely longer than 500*4 = 2000 chars.
    long_paragraph = ("word " * 150).strip()  # ~750 chars
    text = "\n\n".join([long_paragraph] * 5)  # ~3750 chars across 5 paras
    chunks = rag_pipeline._chunk_text(text)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.strip()


def test_chunk_text_respects_paragraph_boundaries():
    para1 = "First paragraph with some text."
    para2 = "Second paragraph with different content."
    text = f"{para1}\n\n{para2}"
    chunks = rag_pipeline._chunk_text(text)
    # Short text: should be in one chunk.
    assert len(chunks) == 1
    assert "First paragraph" in chunks[0]
    assert "Second paragraph" in chunks[0]


# ── _extract_text ──────────────────────────────────────────────────────────────


def test_extract_text_txt():
    content = b"Hello, this is plain text."
    result = rag_pipeline._extract_text(content, "txt", "test.txt")
    assert result == "Hello, this is plain text."


def test_extract_text_txt_utf8():
    content = "Héllo wörld".encode("utf-8")
    result = rag_pipeline._extract_text(content, "txt", "test.txt")
    assert "Héllo" in result


def test_extract_text_unsupported_type_returns_empty():
    result = rag_pipeline._extract_text(b"data", "exe", "bad.exe")
    assert result == ""


def test_extract_pdf_failure_returns_empty():
    """Non-PDF bytes fed to _extract_pdf should return empty without raising."""
    result = rag_pipeline._extract_pdf(b"not a real pdf")
    assert result == ""


def test_extract_docx_failure_returns_empty():
    """Non-DOCX bytes should return empty without raising."""
    result = rag_pipeline._extract_docx(b"not a real docx")
    assert result == ""


# ── _crawl_with_httpx ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_crawl_with_httpx_returns_pages():
    """Mock httpx to return a simple HTML page and verify output."""
    from unittest.mock import AsyncMock, patch, MagicMock

    html = """<html><head></head><body>
        <nav>Navigation</nav>
        <p>Hello world content here</p>
        <footer>Footer</footer>
    </body></html>"""

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/html; charset=utf-8"}
    mock_response.text = html
    # No internal links to follow.

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    async def mock_aenter(self):
        return mock_client

    async def mock_aexit(self, *args):
        pass

    import httpx

    with (
        patch.object(httpx.AsyncClient, "__aenter__", mock_aenter),
        patch.object(httpx.AsyncClient, "__aexit__", mock_aexit),
    ):
        pages = await rag_pipeline._crawl_with_httpx("https://example.com")

    assert len(pages) == 1
    url, text = pages[0]
    assert url == "https://example.com"
    assert "Hello world content here" in text
    # Navigation and footer stripped.
    assert "Navigation" not in text
    assert "Footer" not in text


# ── scrape_website ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scrape_website_stores_chunks():
    db = AsyncMock()
    begin_ctx = AsyncMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=None)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    db.begin = MagicMock(return_value=begin_ctx)
    db.flush = AsyncMock()
    db.add = MagicMock()

    tenant_id = uuid.uuid4()
    page_text = "This is page content. " * 20  # enough to chunk
    mock_embedding = [0.0] * 1536

    with (
        patch.object(
            rag_pipeline,
            "_crawl",
            AsyncMock(return_value=[("https://ex.com", page_text)]),
        ),
        patch(
            "app.services.rag_pipeline.generate_embedding",
            AsyncMock(return_value=mock_embedding),
        ),
    ):
        docs = await rag_pipeline.scrape_website(db, tenant_id, "https://ex.com")

    assert len(docs) >= 1
    assert all(d.tenant_id == tenant_id for d in docs)
    assert all(d.source_type == "website_scrape" for d in docs)
    assert all(d.source_url == "https://ex.com" for d in docs)


@pytest.mark.asyncio
async def test_scrape_website_skips_empty_pages():
    db = AsyncMock()
    begin_ctx = AsyncMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=None)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    db.begin = MagicMock(return_value=begin_ctx)

    tenant_id = uuid.uuid4()

    with patch.object(
        rag_pipeline, "_crawl", AsyncMock(return_value=[("https://ex.com", "   ")])
    ):
        docs = await rag_pipeline.scrape_website(db, tenant_id, "https://ex.com")

    assert docs == []


# ── upload_document ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_document_txt():
    db = AsyncMock()
    begin_ctx = AsyncMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=None)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    db.begin = MagicMock(return_value=begin_ctx)
    db.flush = AsyncMock()
    db.add = MagicMock()

    tenant_id = uuid.uuid4()
    content = b"This is a plain text document. " * 10
    mock_embedding = [0.0] * 1536

    with patch(
        "app.services.rag_pipeline.generate_embedding",
        AsyncMock(return_value=mock_embedding),
    ):
        docs = await rag_pipeline.upload_document(db, tenant_id, content, "readme.txt")

    assert len(docs) >= 1
    assert all(d.source_type == "manual_upload" for d in docs)
    assert all(d.filename == "readme.txt" for d in docs)


@pytest.mark.asyncio
async def test_upload_document_empty_file_returns_empty():
    db = AsyncMock()
    tenant_id = uuid.uuid4()
    docs = await rag_pipeline.upload_document(db, tenant_id, b"", "empty.txt")
    assert docs == []


@pytest.mark.asyncio
async def test_upload_document_unsupported_type_returns_empty():
    db = AsyncMock()
    tenant_id = uuid.uuid4()
    docs = await rag_pipeline.upload_document(db, tenant_id, b"data", "archive.zip")
    assert docs == []


# ── query ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_query_returns_top_k_chunks():
    db = AsyncMock()
    tenant_id = uuid.uuid4()
    mock_embedding = [0.1] * 1536
    mock_rows = [("chunk one",), ("chunk two",), ("chunk three",)]

    execute_result = MagicMock()
    execute_result.fetchall = MagicMock(return_value=mock_rows)
    db.execute = AsyncMock(return_value=execute_result)

    with patch(
        "app.services.rag_pipeline.generate_embedding",
        AsyncMock(return_value=mock_embedding),
    ):
        results = await rag_pipeline.query(db, tenant_id, "test question", top_k=3)

    assert results == ["chunk one", "chunk two", "chunk three"]


@pytest.mark.asyncio
async def test_query_passes_tenant_id_in_sql():
    """Verify the SQL query includes the tenant_id parameter."""
    db = AsyncMock()
    tenant_id = uuid.uuid4()
    mock_embedding = [0.0] * 1536

    execute_result = MagicMock()
    execute_result.fetchall = MagicMock(return_value=[])
    db.execute = AsyncMock(return_value=execute_result)

    with patch(
        "app.services.rag_pipeline.generate_embedding",
        AsyncMock(return_value=mock_embedding),
    ):
        await rag_pipeline.query(db, tenant_id, "question")

    # Verify execute was called with tenant_id in params.
    call_kwargs = db.execute.call_args
    params = call_kwargs[0][1]  # second positional arg is the dict
    assert str(tenant_id) == params["tenant_id"]
