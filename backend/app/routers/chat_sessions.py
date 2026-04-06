from fastapi import APIRouter

router = APIRouter(prefix="/chat-sessions", tags=["chat-sessions"])

# TODO: implement routes per SPEC.md Section 13.2
# GET  /chat-sessions/current
# POST /chat-sessions/{id}/message
# POST /chat-sessions/new
