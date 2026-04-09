"""Team member management routes.

GET    /team          — list team members for this tenant
POST   /team/invite   — invite a new team member by email
DELETE /team/{member_id} — remove a team member
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.team_member import TeamMember
from app.models.tenant import Tenant
from app.routers.auth import get_current_tenant
from app.schemas.common import PaginatedResponse
from app.schemas.team_member import TeamInviteRequest, TeamMemberResponse
from app.services.sendgrid_email import send_email

router = APIRouter(prefix="/team", tags=["team"])


@router.get("", response_model=PaginatedResponse[TeamMemberResponse])
async def list_team_members(
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TeamMemberResponse]:
    """List all team members for this tenant."""
    result = await db.execute(
        select(TeamMember)
        .where(TeamMember.tenant_id == tenant.id, TeamMember.status != "removed")
        .order_by(TeamMember.invited_at.desc())
    )
    members = list(result.scalars().all())
    return PaginatedResponse(
        items=[TeamMemberResponse.model_validate(m) for m in members],
        total=len(members),
        limit=100,
        offset=0,
    )


@router.post("/invite", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_team_member(
    body: TeamInviteRequest,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> TeamMemberResponse:
    """Invite a new team member. Creates a record and sends an invitation email."""
    # Check for existing active invite with same email
    existing = await db.execute(
        select(TeamMember).where(
            TeamMember.tenant_id == tenant.id,
            TeamMember.email == body.email,
            TeamMember.status != "removed",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A team member with this email already exists",
        )

    member = TeamMember(
        tenant_id=tenant.id,
        email=body.email,
        name=body.name,
        role=body.role,
        status="invited",
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)

    # Send invitation email (best-effort — don't fail if email fails)
    from app.config import settings as app_settings

    html_body = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
      <h2>You've been invited to join {tenant.name}</h2>
      <p>You've been invited as a <strong>{body.role.replace('_', ' ').title()}</strong>
         on the AI Recruiter platform.</p>
      <p>
        <a href="{app_settings.frontend_url}/signup"
           style="background:#5865f2;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;display:inline-block;">
          Accept Invitation
        </a>
      </p>
      <p style="color:#888;font-size:13px;">
        Sign up with this email address ({body.email}) to join the team.
      </p>
    </div>
    """
    await send_email(
        to=body.email,
        subject=f"You've been invited to join {tenant.name} on AI Recruiter",
        html_body=html_body,
        tenant=tenant,
    )

    return TeamMemberResponse.model_validate(member)


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    member_id: uuid.UUID,
    tenant: Tenant = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a team member."""
    result = await db.execute(
        select(TeamMember).where(
            TeamMember.id == member_id,
            TeamMember.tenant_id == tenant.id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found")

    await db.delete(member)
    await db.commit()
