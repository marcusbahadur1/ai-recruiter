"""TalentScoutService — SERP query builder for the Talent Scout pipeline.

Implements SPEC §7.1.1 location rules by work_type.  All public methods emit
the correct audit events per SPEC §15.2.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.audit_trail import AuditTrailService

if TYPE_CHECKING:
    from app.models.job import Job


class TalentScoutService:
    """Builds SERP search queries and emits pipeline audit events.

    Instantiate once per Celery task execution, passing the task's async
    DB session and tenant_id.

    Args:
        db: Async SQLAlchemy session.
        tenant_id: Owning tenant UUID — injected so callers never forget it.
    """

    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID) -> None:
        self._db = db
        self._tenant_id = tenant_id
        self._audit = AuditTrailService(db, tenant_id)

    # ── Query construction (SPEC §7.1.1) ──────────────────────────────────────

    def build_search_queries(self, job: "Job") -> list[str]:
        """Generate all title × location SERP query combinations.

        Query format: ``'"{title}" {location} site:linkedin.com/in/'``

        Location rules by ``job.work_type``:

        - ``onsite`` / ``hybrid``: include nearby cities — uses
          ``job.location`` + ``job.location_variations`` (set at job creation
          to contain commutable cities).
        - ``remote``: include major cities in the same country — uses
          ``job.location`` + ``job.location_variations`` (set at job creation
          to contain country-level cities).
        - ``remote_global``: no location filter — one query per title only.

        Args:
            job: Job record.  ``title_variations``, ``location_variations``,
                 and ``work_type`` must be populated.

        Returns:
            Deduplicated list of search query strings, preserving insertion
            order (title-major, location-minor).
        """
        titles = _build_title_list(job)

        if job.work_type == "remote_global":
            return [f'"{title}" site:linkedin.com/in/' for title in titles]

        locations = _build_location_list(job)
        queries: list[str] = []
        seen: set[str] = set()
        for title in titles:
            for location in locations:
                q = f'"{title}" {location} site:linkedin.com/in/'
                if q not in seen:
                    seen.add(q)
                    queries.append(q)
        return queries

    # ── Audit event emitters (SPEC §15.2) ─────────────────────────────────────

    async def emit_job_started(self, job_id: uuid.UUID, job_title: str) -> None:
        """Emit ``scout.job_started``."""
        await self._audit.emit(
            job_id=job_id,
            event_type="scout.job_started",
            event_category="talent_scout",
            severity="info",
            summary=f"Talent Scout started for job '{job_title}'",
        )

    async def emit_queries_built(
        self,
        job_id: uuid.UUID,
        query_count: int,
        title_count: int,
        location_count: int,
    ) -> None:
        """Emit ``scout.search_query_built``."""
        await self._audit.emit(
            job_id=job_id,
            event_type="scout.search_query_built",
            event_category="talent_scout",
            severity="info",
            summary=(
                f"Built {query_count} queries "
                f"({title_count} titles × {location_count} locations)"
            ),
            detail={
                "query_count": query_count,
                "title_count": title_count,
                "location_count": location_count,
            },
        )

    async def emit_serp_success(
        self,
        job_id: uuid.UUID,
        result_count: int,
        page: int,
        duration_ms: int,
    ) -> None:
        """Emit ``scout.serp_call_success``."""
        await self._audit.emit(
            job_id=job_id,
            event_type="scout.serp_call_success",
            event_category="talent_scout",
            severity="success",
            summary=f"SERP returned {result_count} results (page {page + 1})",
            detail={"result_count": result_count, "page": page + 1},
            duration_ms=duration_ms,
        )

    async def emit_serp_failed(
        self,
        job_id: uuid.UUID,
        error: str,
        duration_ms: int,
    ) -> None:
        """Emit ``scout.serp_call_failed``."""
        await self._audit.emit(
            job_id=job_id,
            event_type="scout.serp_call_failed",
            event_category="talent_scout",
            severity="error",
            summary=f"SERP call failed — {error}",
            detail={"error": error},
            duration_ms=duration_ms,
        )

    async def emit_candidate_discovered(
        self,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
        name: str,
    ) -> None:
        """Emit ``scout.candidate_discovered``."""
        await self._audit.emit(
            job_id=job_id,
            candidate_id=candidate_id,
            event_type="scout.candidate_discovered",
            event_category="talent_scout",
            severity="info",
            summary=f"Discovered: {name}",
        )

    async def emit_candidate_duplicate(
        self, job_id: uuid.UUID, linkedin_url: str
    ) -> None:
        """Emit ``scout.candidate_duplicate_skipped``."""
        await self._audit.emit(
            job_id=job_id,
            event_type="scout.candidate_duplicate_skipped",
            event_category="talent_scout",
            severity="info",
            summary="Skipped duplicate LinkedIn URL",
            detail={"linkedin_url": linkedin_url},
        )

    async def emit_profile_enrichment_started(
        self, job_id: uuid.UUID, candidate_id: uuid.UUID
    ) -> None:
        """Emit ``scout.profile_enrichment_started``."""
        await self._audit.emit(
            job_id=job_id,
            candidate_id=candidate_id,
            event_type="scout.profile_enrichment_started",
            event_category="talent_scout",
            severity="info",
            summary="Requesting BrightData profile",
        )

    async def emit_profile_enrichment_success(
        self,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
        profile: dict,
        duration_ms: int,
    ) -> None:
        """Emit ``scout.profile_enrichment_success``."""
        positions = len(profile.get("positions", []))
        exp_years = profile.get("experience_years") or profile.get("years_of_experience") or 0
        await self._audit.emit(
            job_id=job_id,
            candidate_id=candidate_id,
            event_type="scout.profile_enrichment_success",
            event_category="talent_scout",
            severity="success",
            summary=f"Profile received ({exp_years} yrs exp, {positions} roles)",
            detail={"positions_count": positions, "experience_years": exp_years},
            duration_ms=duration_ms,
        )

    async def emit_profile_enrichment_failed(
        self,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
        error: str,
        duration_ms: int,
    ) -> None:
        """Emit ``scout.profile_enrichment_failed``."""
        await self._audit.emit(
            job_id=job_id,
            candidate_id=candidate_id,
            event_type="scout.profile_enrichment_failed",
            event_category="talent_scout",
            severity="warning",
            summary=f"Empty profile — skipping scoring",
            detail={"error": error},
            duration_ms=duration_ms,
        )

    async def emit_scoring_started(
        self, job_id: uuid.UUID, candidate_id: uuid.UUID
    ) -> None:
        """Emit ``scout.scoring_started``."""
        await self._audit.emit(
            job_id=job_id,
            candidate_id=candidate_id,
            event_type="scout.scoring_started",
            event_category="talent_scout",
            severity="info",
            summary="Scoring candidate against job spec",
        )

    async def emit_scoring_success(
        self,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
        score: int,
        passed: bool,
        duration_ms: int,
    ) -> None:
        """Emit ``scout.scoring_success`` or ``scout.scoring_failed_threshold``."""
        if passed:
            event_type = "scout.scoring_success"
            severity = "success"
            summary = f"Scored {score}/10 — passed threshold"
        else:
            event_type = "scout.scoring_failed_threshold"
            severity = "info"
            summary = f"Scored {score}/10 — below threshold"

        await self._audit.emit(
            job_id=job_id,
            candidate_id=candidate_id,
            event_type=event_type,
            event_category="talent_scout",
            severity=severity,
            summary=summary,
            detail={"score": score, "passed": passed},
            duration_ms=duration_ms,
        )

    async def emit_scoring_error(
        self,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
        error: str,
        duration_ms: int,
    ) -> None:
        """Emit ``scout.scoring_error``."""
        await self._audit.emit(
            job_id=job_id,
            candidate_id=candidate_id,
            event_type="scout.scoring_error",
            event_category="talent_scout",
            severity="error",
            summary=f"AI scoring error — will retry",
            detail={"error": error},
            duration_ms=duration_ms,
        )

    async def emit_email_discovery_started(
        self,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
        provider: str,
    ) -> None:
        """Emit ``scout.email_discovery_started``."""
        await self._audit.emit(
            job_id=job_id,
            candidate_id=candidate_id,
            event_type="scout.email_discovery_started",
            event_category="talent_scout",
            severity="info",
            summary=f"Discovering email via {provider}",
            detail={"provider": provider},
        )

    async def emit_email_found(
        self,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
        source: str,
    ) -> None:
        """Emit the appropriate email-found event for *source*."""
        event_map = {
            "apollo": ("scout.email_found_apollo", "Email found via Apollo (verified)"),
            "hunter": ("scout.email_found_hunter", "Email found via Hunter.io"),
            "snov": ("scout.email_found_snov", "Email found via Snov.io"),
            "deduced": ("scout.email_found_deduced", "Email deduced via SMTP verification"),
        }
        event_type, summary = event_map.get(
            source, ("scout.email_found_apollo", f"Email found via {source}")
        )
        await self._audit.emit(
            job_id=job_id,
            candidate_id=candidate_id,
            event_type=event_type,
            event_category="talent_scout",
            severity="success",
            summary=summary,
            detail={"source": source},
        )

    async def emit_email_not_found(
        self, job_id: uuid.UUID, candidate_id: uuid.UUID
    ) -> None:
        """Emit ``scout.email_not_found``."""
        await self._audit.emit(
            job_id=job_id,
            candidate_id=candidate_id,
            event_type="scout.email_not_found",
            event_category="talent_scout",
            severity="warning",
            summary="No email found — flagged for manual",
        )

    async def emit_outreach_generated(
        self,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
        word_count: int,
    ) -> None:
        """Emit ``scout.outreach_email_generated``."""
        await self._audit.emit(
            job_id=job_id,
            candidate_id=candidate_id,
            event_type="scout.outreach_email_generated",
            event_category="talent_scout",
            severity="info",
            summary=f"Email generated ({word_count} words)",
            detail={"word_count": word_count},
        )

    async def emit_outreach_sent(
        self,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
        duration_ms: int,
    ) -> None:
        """Emit ``scout.outreach_email_sent``."""
        await self._audit.emit(
            job_id=job_id,
            candidate_id=candidate_id,
            event_type="scout.outreach_email_sent",
            event_category="talent_scout",
            severity="success",
            summary="Outreach email sent via SendGrid",
            duration_ms=duration_ms,
        )

    async def emit_outreach_failed(
        self,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID,
        error: str,
        duration_ms: int,
    ) -> None:
        """Emit ``scout.outreach_email_failed``."""
        await self._audit.emit(
            job_id=job_id,
            candidate_id=candidate_id,
            event_type="scout.outreach_email_failed",
            event_category="talent_scout",
            severity="error",
            summary=f"SendGrid delivery failed — {error}",
            detail={"error": error},
            duration_ms=duration_ms,
        )

    async def emit_job_completed(
        self,
        job_id: uuid.UUID,
        discovered: int,
        passed: int,
        emailed: int,
    ) -> None:
        """Emit ``scout.job_completed``."""
        await self._audit.emit(
            job_id=job_id,
            event_type="scout.job_completed",
            event_category="talent_scout",
            severity="success",
            summary=(
                f"Scout complete: {discovered} discovered, "
                f"{passed} passed, {emailed} emailed"
            ),
            detail={
                "discovered": discovered,
                "passed": passed,
                "emailed": emailed,
            },
        )

    async def emit_task_failed_permanent(
        self,
        job_id: uuid.UUID,
        candidate_id: uuid.UUID | None,
        task_name: str,
        error: str,
    ) -> None:
        """Emit ``system.task_failed_permanent``."""
        await self._audit.emit(
            job_id=job_id,
            candidate_id=candidate_id,
            event_type="system.task_failed_permanent",
            event_category="system",
            severity="error",
            summary=f"Task {task_name!r} permanently failed after 3 attempts",
            detail={"task": task_name, "error": error},
        )


# ── Module-level helpers ───────────────────────────────────────────────────────


def _build_title_list(job: "Job") -> list[str]:
    """Return the base title plus all variations, deduplicated."""
    titles: list[str] = [job.title]
    for t in job.title_variations or []:
        if t and t not in titles:
            titles.append(t)
    return titles


def _build_location_list(job: "Job") -> list[str]:
    """Return the base location plus all variations, deduplicated and non-empty."""
    locations: list[str] = []
    if job.location:
        locations.append(job.location)
    for loc in job.location_variations or []:
        if loc and loc not in locations:
            locations.append(loc)
    return locations
