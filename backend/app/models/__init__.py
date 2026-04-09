# Import all models so that SQLAlchemy's mapper registry and Alembic's
# autogenerate can discover every table through Base.metadata.
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.chat_session import ChatSession
from app.models.job import Job
from app.models.job_audit_event import JobAuditEvent
from app.models.promo_code import PromoCode
from app.models.rag_document import RagDocument
from app.models.team_member import TeamMember
from app.models.tenant import Tenant

__all__ = [
    "Application",
    "Candidate",
    "ChatSession",
    "Job",
    "JobAuditEvent",
    "PromoCode",
    "RagDocument",
    "TeamMember",
    "Tenant",
]
