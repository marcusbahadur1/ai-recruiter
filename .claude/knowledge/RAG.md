# RAG Domain

Website scraping, document upload, pgvector retrieval, widget integration.

---

## Purpose

Tenants can upload their company knowledge base (website pages, PDFs, etc.). This context is used to:
1. Improve resume screening (inject relevant job/company context into screening prompt)
2. Power the public chat widget (answer candidate questions about the company)

---

## Data Flow

```
Source → scrape/extract → chunk (~500 tokens, 100-char overlap) → embed (OpenAI) → store in rag_documents
Query → embed question → pgvector cosine search → return top-k chunks
```

---

## Scraping

- Primary: `crawl4ai.AsyncCrawler` with 30s timeout — handles JS-rendered pages
- Fallback: `httpx GET + BeautifulSoup` — static HTML only
- Follows internal links up to 20 pages per domain
- Each chunk stored as separate `RagDocument` row

---

## Embedding Model

- `OpenAI text-embedding-3-small` (1536 dimensions)
- Sync client used in Celery context (`generate_embedding()`)
- Async client used in API context (`generate_embedding_async()`)
- **Never switch Celery to async** — see DECISIONS.md D7

---

## pgvector Query

```sql
SELECT content_text
FROM rag_documents
WHERE tenant_id = :tenant_id
ORDER BY embedding <=> :query_embedding
LIMIT 5
```

- `<=>` is cosine distance operator (lower = more similar)
- No minimum similarity threshold — see FRAGILE_ZONES.md F6

---

## Multi-tenant Isolation

- Every `RagDocument` has `tenant_id`
- All queries filter by `tenant_id` — tenants never see each other's knowledge base
- No cross-tenant RAG queries possible (not even for super admin)

---

## Document Types Supported

- PDF: `pdfplumber` (primary) or `PyPDF2` (fallback)
- DOCX: `python-docx`
- TXT: plain read
- Web pages: crawl4ai / httpx

---

## API Endpoints

- `POST /rag/scrape {url}` — crawl and index a website
- `POST /rag/upload` (multipart) — upload a document file
- `POST /rag/query {question}` — retrieve relevant chunks
- `GET /rag/documents` — list all indexed documents for tenant

---

## Widget Integration

- Public chat widget calls `POST /rag/query` to fetch context before answering
- Widget endpoint is at `/api/v1/widget/chat` (no auth — public)
- Widget JS file: `frontend/public/widget/widget.js` — plain JS, no bundler

---

## Known Gaps

- No re-indexing on source website change (manual re-scrape required)
- Scheduled `rag_refresh` task (Sunday 02:00 AEST) re-scrapes tenant websites automatically, but only if URL was stored with document
- No document deletion from pgvector (only logical delete)
