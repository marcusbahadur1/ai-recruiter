from fastapi import APIRouter

router = APIRouter(prefix="/rag", tags=["rag"])

# TODO: implement routes per SPEC.md Section 13.6
# POST   /rag/scrape
# POST   /rag/documents
# DELETE /rag/documents/{id}
# GET    /widget/{slug}/chat  (public, rate-limited)
