from fastapi import APIRouter

router = APIRouter(prefix="/applications", tags=["applications"])

# TODO: implement routes per SPEC.md Section 13.5
# GET  /applications?job_id={id}
# GET  /applications/{id}
# POST /applications/{id}/trigger-test
# GET  /test/{id}/{token}              (public)
# POST /test/{id}/message              (public)
# GET  /actions/invite-interview/{id}/{token}  (public)
