from fastapi import APIRouter

router = APIRouter(prefix="/super-admin", tags=["super-admin"])

# TODO: implement routes per SPEC.md Section 13.1 (super_admin only)
# GET  /super-admin/tenants
# POST /super-admin/impersonate/{tenant_id}
