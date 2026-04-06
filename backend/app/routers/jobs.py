from fastapi import APIRouter

router = APIRouter(prefix="/jobs", tags=["jobs"])

# TODO: implement routes per SPEC.md Section 13.3
# GET    /jobs
# POST   /jobs
# GET    /jobs/{id}
# PATCH  /jobs/{id}
# POST   /jobs/{id}/trigger-scout
# GET    /jobs/{id}/evaluation-report  (SSE)
