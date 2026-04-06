from fastapi import APIRouter

router = APIRouter(prefix="/candidates", tags=["candidates"])

# TODO: implement routes per SPEC.md Section 13.4
# GET    /candidates  (search + filter)
# GET    /candidates/{id}
# PATCH  /candidates/{id}
# DELETE /candidates/{id}  (GDPR erasure)
# POST   /candidates/{id}/send-outreach
