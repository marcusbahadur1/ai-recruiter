"""Integration tests for RAG routes and widget chat."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest



# ── RAG routes ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rag_scrape_requires_widget_plan(client, mock_tenant):
    """Tenants on individual plan should get 403."""
    mock_tenant.plan = "individual"  # below small_firm threshold

    resp = await client.post("/api/v1/rag/scrape", json={"url": "https://example.com"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_rag_scrape_small_firm_plan_accepted(client, mock_db, mock_tenant):
    mock_tenant.plan = "small_firm"

    with patch("app.services.rag_pipeline.scrape_website", AsyncMock(return_value=[])):
        resp = await client.post("/api/v1/rag/scrape", json={"url": "https://example.com"})

    assert resp.status_code == 202
    assert resp.json()["chunks_stored"] == 0


@pytest.mark.asyncio
async def test_rag_scrape_returns_chunk_count(client, mock_db, mock_tenant):
    mock_tenant.plan = "enterprise"

    fake_docs = [MagicMock() for _ in range(3)]
    with patch("app.services.rag_pipeline.scrape_website", AsyncMock(return_value=fake_docs)):
        resp = await client.post("/api/v1/rag/scrape", json={"url": "https://firm.com"})

    assert resp.status_code == 202
    assert resp.json()["chunks_stored"] == 3


@pytest.mark.asyncio
async def test_rag_upload_unsupported_type(client, mock_tenant):
    mock_tenant.plan = "small_firm"

    resp = await client.post(
        "/api/v1/rag/documents",
        files={"file": ("archive.zip", b"data", "application/zip")},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_rag_upload_txt_accepted(client, mock_db, mock_tenant):
    mock_tenant.plan = "small_firm"

    from datetime import datetime, timezone
    fake_doc = MagicMock()
    fake_doc.id = uuid.uuid4()
    fake_doc.tenant_id = mock_tenant.id
    fake_doc.source_type = "manual_upload"
    fake_doc.source_url = None
    fake_doc.filename = "test.txt"
    fake_doc.content_text = "Hello world"
    fake_doc.created_at = datetime.now(timezone.utc)

    with patch("app.services.rag_pipeline.upload_document", AsyncMock(return_value=[fake_doc])):
        resp = await client.post(
            "/api/v1/rag/documents",
            files={"file": ("test.txt", b"Hello world content", "text/plain")},
        )

    assert resp.status_code == 201
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_rag_delete_document_not_found(client, mock_db, mock_tenant):
    mock_tenant.plan = "small_firm"

    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=execute_result)

    resp = await client.delete(f"/api/v1/rag/documents/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_rag_delete_document_success(client, mock_db, mock_tenant):
    mock_tenant.plan = "small_firm"

    doc_id = uuid.uuid4()
    fake_doc = MagicMock()
    fake_doc.id = doc_id

    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=fake_doc)
    mock_db.execute = AsyncMock(return_value=execute_result)
    mock_db.delete = AsyncMock()

    resp = await client.delete(f"/api/v1/rag/documents/{doc_id}")
    assert resp.status_code == 204


# ── Widget chat ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_widget_chat_unknown_slug(client, mock_db):
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=execute_result)

    resp = await client.post("/api/v1/widget/nonexistent/chat", json={"message": "Hello"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_widget_chat_plan_too_low(client, mock_db, mock_tenant):
    """Widget not available below small_firm."""
    tenant = MagicMock()
    tenant.slug = "low-plan"
    tenant.is_active = True
    tenant.plan = "individual"

    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=tenant)
    mock_db.execute = AsyncMock(return_value=execute_result)

    resp = await client.post("/api/v1/widget/low-plan/chat", json={"message": "Hello"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_widget_chat_returns_reply(client, mock_db, mock_tenant):
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    tenant.slug = "test-firm"
    tenant.is_active = True
    tenant.plan = "small_firm"
    tenant.name = "Test Firm"
    tenant.ai_provider = "anthropic"
    tenant.ai_api_key = None

    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=tenant)
    mock_db.execute = AsyncMock(return_value=execute_result)

    with patch("app.services.rag_pipeline.query", AsyncMock(return_value=["Chunk about the firm"])), \
         patch("app.services.ai_provider.AIProvider.complete", AsyncMock(return_value="We help companies hire.")):
        resp = await client.post("/api/v1/widget/test-firm/chat", json={
            "message": "What does your firm do?",
            "conversation_history": [],
        })

    assert resp.status_code == 200
    data = resp.json()
    assert "reply" in data
    assert "tenant_name" in data
    assert data["tenant_name"] == "Test Firm"


@pytest.mark.asyncio
async def test_widget_chat_with_history(client, mock_db):
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    tenant.slug = "test-firm"
    tenant.is_active = True
    tenant.plan = "enterprise"
    tenant.name = "Test Firm"
    tenant.ai_provider = "anthropic"
    tenant.ai_api_key = None

    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=tenant)
    mock_db.execute = AsyncMock(return_value=execute_result)

    history = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello! How can I help?"},
    ]

    with patch("app.services.rag_pipeline.query", AsyncMock(return_value=[])), \
         patch("app.services.ai_provider.AIProvider.complete", AsyncMock(return_value="Sure, we're hiring.")):
        resp = await client.post("/api/v1/widget/test-firm/chat", json={
            "message": "Do you have any jobs?",
            "conversation_history": history,
        })

    assert resp.status_code == 200
    assert resp.json()["reply"] == "Sure, we're hiring."
