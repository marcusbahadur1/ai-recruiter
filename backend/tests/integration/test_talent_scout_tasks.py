"""Integration tests for the Talent Scout task pipeline.

Tests call the async ``_*_impl`` functions directly (bypassing Celery),
mock all external APIs per SPEC §18.4, and assert on DB state changes and
audit events emitted.

Mock strategy (SPEC §18.4):
- ScrapingDog / BrightData SERP  → fixture JSON
- BrightData LinkedIn profiles   → fixture JSON
- Claude / OpenAI                → deterministic JSON via unittest.mock
- SendGrid                       → mock client capturing calls
- Apollo / Hunter / Snov         → fixture JSON responses
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.integration.conftest import make_candidate, make_job

# ── Fixtures ───────────────────────────────────────────────────────────────────

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
JOB_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
CANDIDATE_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


@pytest.fixture()
def tenant_id() -> uuid.UUID:
    return TENANT_ID


@pytest.fixture()
def job_id() -> uuid.UUID:
    return JOB_ID


@pytest.fixture()
def candidate_id() -> uuid.UUID:
    return CANDIDATE_ID


@pytest.fixture()
def mock_tenant(tenant_id):
    t = MagicMock()
    t.id = tenant_id
    t.name = "Test Firm"
    t.email_inbox = "jobs-test@airecruiterz.com"
    t.ai_provider = "anthropic"
    t.ai_api_key = None
    t.sendgrid_api_key = None
    t.scrapingdog_api_key = None
    t.brightdata_api_key = None
    t.apollo_api_key = None
    t.hunter_api_key = None
    t.snov_api_key = None
    t.email_discovery_provider = "domain_deduction"
    return t


@pytest.fixture()
def mock_job(tenant_id, job_id):
    return make_job(
        tenant_id,
        id=job_id,
        title="Java Developer",
        title_variations=["Backend Developer"],
        location="Sydney",
        location_variations=["Melbourne"],
        work_type="hybrid",
        minimum_score=6,
        required_skills=["Java", "Spring"],
        tech_stack=["Docker"],
        job_ref="JAVA001",
        hiring_manager_name="Jane Smith",
        outreach_email_prompt=None,
        description="Build great software.",
    )


@pytest.fixture()
def mock_candidate(tenant_id, job_id, candidate_id):
    c = make_candidate(tenant_id, job_id, id=candidate_id)
    c.linkedin_url = "https://www.linkedin.com/in/alice-dev"
    c.status = "discovered"
    c.email = None
    c.email_source = None
    c.company = "Acme Corp"
    c.name = "Alice Example"
    c.title = "Senior Engineer"
    c.brightdata_profile = {}
    c.opted_out = False
    c.outreach_email_sent_at = None
    c.outreach_email_content = None
    return c


def _make_db_mock():
    db = AsyncMock()
    begin_ctx = AsyncMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=None)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    db.begin = MagicMock(return_value=begin_ctx)
    db.flush = AsyncMock()
    # SQLAlchemy sync methods — must NOT be AsyncMock
    db.add = MagicMock()
    db.delete = MagicMock()
    db.refresh = MagicMock()
    return db


def _patch_session(mock_db):
    """Return a patch context for AsyncSessionLocal yielding mock_db."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_db)
    cm.__aexit__ = AsyncMock(return_value=False)
    return patch(
        "app.tasks.talent_scout_tasks.AsyncSessionLocal", return_value=cm
    )


# ── discover_candidates ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discover_candidates_creates_candidate_records(
    mock_tenant, mock_job, tenant_id, job_id
):
    """SERP results create Candidate records and emit discovered events."""
    from app.tasks.talent_scout_tasks import _discover_candidates_async

    mock_db = _make_db_mock()

    # DB returns: job, tenant, existing_count=0, empty existing URLs
    db_execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_job)),    # get_job
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),  # get_tenant
        MagicMock(scalar=MagicMock(return_value=0)),                        # existing_count
        MagicMock(all=MagicMock(return_value=[])),                          # existing URLs
    ]
    mock_db.execute = AsyncMock(side_effect=db_execute_results)

    serp_results = [
        {
            "title": "Alice Dev - Java Developer | LinkedIn",
            "snippet": "Great developer.",
            "link": "https://www.linkedin.com/in/alice-dev",
        }
    ]

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.scrapingdog.search_linkedin",
                   new_callable=AsyncMock, return_value=serp_results):
            with patch("app.tasks.talent_scout_tasks.enrich_profile") as mock_enrich:
                with patch("app.tasks.talent_scout_tasks.settings") as mock_settings:
                    mock_settings.scrapingdog_api_key = "test-key"
                    mock_settings.frontend_url = "https://app.airecruiterz.com"
                    mock_settings.plan_limits = {"trial": {"candidates": 20}}
                    await _discover_candidates_async(str(job_id), str(tenant_id))

    # A Candidate was added to the DB (among audit events)
    from app.models.candidate import Candidate
    added_candidates = [
        c for c in [call.args[0] for call in mock_db.add.call_args_list]
        if isinstance(c, Candidate)
    ]
    assert len(added_candidates) == 1
    added_obj = added_candidates[0]
    assert added_obj.name == "Alice Dev"
    assert added_obj.linkedin_url == "https://www.linkedin.com/in/alice-dev"
    assert added_obj.status == "discovered"
    assert added_obj.tenant_id == tenant_id
    assert added_obj.job_id == job_id


@pytest.mark.asyncio
async def test_discover_candidates_deduplicates_by_linkedin_url(
    mock_tenant, mock_job, tenant_id, job_id
):
    """Candidates with existing LinkedIn URLs are skipped."""
    from app.tasks.talent_scout_tasks import _discover_candidates_async

    mock_db = _make_db_mock()
    existing_url = "https://www.linkedin.com/in/alice-dev"

    db_execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_job)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
        MagicMock(scalar=MagicMock(return_value=0)),
        MagicMock(all=MagicMock(return_value=[(existing_url,)])),  # already exists
    ]
    mock_db.execute = AsyncMock(side_effect=db_execute_results)

    serp_results = [
        {
            "title": "Alice Dev - Java Developer | LinkedIn",
            "snippet": "Dev.",
            "link": existing_url,
        }
    ]

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.scrapingdog.search_linkedin",
                   new_callable=AsyncMock, return_value=serp_results):
            with patch("app.tasks.talent_scout_tasks.enrich_profile"):
                with patch("app.tasks.talent_scout_tasks.settings") as mock_settings:
                    mock_settings.scrapingdog_api_key = "test-key"
                    mock_settings.frontend_url = "https://app.airecruiterz.com"
                    mock_settings.plan_limits = {"trial": {"candidates": 20}}
                    await _discover_candidates_async(str(job_id), str(tenant_id))

    from app.models.candidate import Candidate
    added_candidates = [
        c for c in [call.args[0] for call in mock_db.add.call_args_list]
        if isinstance(c, Candidate)
    ]
    assert added_candidates == [], "No Candidate should have been added for a duplicate URL"


@pytest.mark.asyncio
async def test_discover_candidates_skips_non_profile_urls(
    mock_tenant, mock_job, tenant_id, job_id
):
    """SERP results pointing to company pages are ignored."""
    from app.tasks.talent_scout_tasks import _discover_candidates_async

    mock_db = _make_db_mock()
    db_execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_job)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
        MagicMock(scalar=MagicMock(return_value=0)),
        MagicMock(all=MagicMock(return_value=[])),
    ]
    mock_db.execute = AsyncMock(side_effect=db_execute_results)

    serp_results = [
        {
            "title": "Acme Corp | LinkedIn",
            "snippet": "Company page.",
            "link": "https://www.linkedin.com/company/acme",  # company page, not profile
        }
    ]

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.scrapingdog.search_linkedin",
                   new_callable=AsyncMock, return_value=serp_results):
            with patch("app.tasks.talent_scout_tasks.enrich_profile"):
                with patch("app.tasks.talent_scout_tasks.settings") as mock_settings:
                    mock_settings.scrapingdog_api_key = "test-key"
                    mock_settings.frontend_url = "https://app.airecruiterz.com"
                    mock_settings.plan_limits = {"trial": {"candidates": 20}}
                    await _discover_candidates_async(str(job_id), str(tenant_id))

    from app.models.candidate import Candidate
    added_candidates = [
        c for c in [call.args[0] for call in mock_db.add.call_args_list]
        if isinstance(c, Candidate)
    ]
    assert added_candidates == [], "Company page URLs must not create Candidate records"


@pytest.mark.asyncio
async def test_discover_candidates_fans_out_chain(
    mock_tenant, mock_job, tenant_id, job_id
):
    """After discovery, a Celery chain is dispatched for each new candidate."""
    from app.tasks.talent_scout_tasks import _discover_candidates_async

    mock_db = _make_db_mock()
    db_execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_job)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
        MagicMock(scalar=MagicMock(return_value=0)),
        MagicMock(all=MagicMock(return_value=[])),
    ]
    mock_db.execute = AsyncMock(side_effect=db_execute_results)

    serp_result = {
        "title": "Bob Dev - Backend Dev | LinkedIn",
        "snippet": "Dev.",
        "link": "https://www.linkedin.com/in/bob-dev",
    }

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.scrapingdog.search_linkedin",
                   new_callable=AsyncMock, return_value=[serp_result]):
            with patch("app.tasks.talent_scout_tasks.enrich_profile") as mock_enrich:
                with patch("app.tasks.talent_scout_tasks.settings") as mock_settings:
                    mock_settings.scrapingdog_api_key = "test-key"
                    mock_settings.frontend_url = "https://app.airecruiterz.com"
                    mock_settings.plan_limits = {"trial": {"candidates": 20}}
                    await _discover_candidates_async(str(job_id), str(tenant_id))

    mock_enrich.delay.assert_called_once()


# ── enrich_profile ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_enrich_profile_success(mock_candidate, mock_tenant, tenant_id, candidate_id):
    """BrightData profile is stored and status advances to 'profiled'."""
    from app.tasks.talent_scout_tasks import _enrich_profile_async

    mock_candidate.status = "discovered"
    mock_db = _make_db_mock()
    db_execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
    ]
    mock_db.execute = AsyncMock(side_effect=db_execute_results)

    brightdata_profile = {
        "positions": [{"title": "Senior Engineer", "company_name": "Acme"}],
        "location": "Sydney, NSW",
        "years_of_experience": 8,
    }

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.brightdata.get_linkedin_profile",
                   new_callable=AsyncMock, return_value=brightdata_profile):
            with patch("app.tasks.talent_scout_tasks.settings") as mock_settings:
                mock_settings.brightdata_api_key = "bd-test-key"
                await _enrich_profile_async(str(candidate_id), str(tenant_id))

    assert mock_candidate.brightdata_profile == brightdata_profile
    assert mock_candidate.status == "profiled"
    assert mock_candidate.location == "Sydney, NSW"


@pytest.mark.asyncio
async def test_enrich_profile_empty_response(mock_candidate, mock_tenant, tenant_id, candidate_id):
    """Empty BrightData response advances status but keeps brightdata_profile empty."""
    from app.tasks.talent_scout_tasks import _enrich_profile_async

    mock_candidate.status = "discovered"
    mock_db = _make_db_mock()
    db_execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
    ]
    mock_db.execute = AsyncMock(side_effect=db_execute_results)

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.brightdata.get_linkedin_profile",
                   new_callable=AsyncMock, return_value={}):
            with patch("app.tasks.talent_scout_tasks.settings") as mock_settings:
                mock_settings.brightdata_api_key = "bd-test-key"
                await _enrich_profile_async(str(candidate_id), str(tenant_id))

    # Status still advances so the chain can continue
    assert mock_candidate.status == "profiled"
    assert mock_candidate.brightdata_profile == {}


@pytest.mark.asyncio
async def test_enrich_profile_idempotent_skips_profiled(
    mock_candidate, mock_tenant, tenant_id, candidate_id
):
    """Candidate already 'profiled' is not re-processed."""
    from app.tasks.talent_scout_tasks import _enrich_profile_async

    mock_candidate.status = "profiled"
    mock_db = _make_db_mock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate))
    )

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.brightdata.get_linkedin_profile",
                   new_callable=AsyncMock) as mock_bd:
            await _enrich_profile_async(str(candidate_id), str(tenant_id))

    mock_bd.assert_not_called()


# ── score_candidate ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_score_candidate_passed(mock_candidate, mock_job, mock_tenant, tenant_id, candidate_id):
    """Score >= minimum_score sets status to 'passed'."""
    from app.tasks.talent_scout_tasks import _score_candidate_async

    mock_candidate.status = "profiled"
    mock_candidate.brightdata_profile = {"positions": [{"title": "Dev"}]}
    mock_candidate.job_id = mock_job.id

    mock_db = _make_db_mock()
    db_execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_job)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
    ]
    mock_db.execute = AsyncMock(side_effect=db_execute_results)

    import json
    ai_response = {"score": 8, "reasoning": "Strong match.", "strengths": ["Java"], "gaps": []}

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.AIProvider") as MockAI:
            mock_ai_inst = AsyncMock()
            mock_ai_inst.complete = AsyncMock(return_value=json.dumps(ai_response))
            MockAI.return_value = mock_ai_inst
            await _score_candidate_async(str(candidate_id), str(tenant_id))

    assert mock_candidate.suitability_score == 8
    assert mock_candidate.status == "passed"
    assert mock_candidate.score_reasoning == "Strong match."


@pytest.mark.asyncio
async def test_score_candidate_failed_threshold(
    mock_candidate, mock_job, mock_tenant, tenant_id, candidate_id
):
    """Score < minimum_score sets status to 'failed'."""
    from app.tasks.talent_scout_tasks import _score_candidate_async

    mock_candidate.status = "profiled"
    mock_candidate.brightdata_profile = {"positions": []}
    mock_candidate.job_id = mock_job.id
    mock_job.minimum_score = 6

    mock_db = _make_db_mock()
    db_execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_job)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
    ]
    mock_db.execute = AsyncMock(side_effect=db_execute_results)

    import json
    ai_response = {"score": 3, "reasoning": "Not enough experience.", "strengths": [], "gaps": ["Java"]}

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.AIProvider") as MockAI:
            mock_ai_inst = AsyncMock()
            mock_ai_inst.complete = AsyncMock(return_value=json.dumps(ai_response))
            MockAI.return_value = mock_ai_inst
            await _score_candidate_async(str(candidate_id), str(tenant_id))

    assert mock_candidate.suitability_score == 3
    assert mock_candidate.status == "failed"


@pytest.mark.asyncio
async def test_score_candidate_idempotent_skips_passed(
    mock_candidate, mock_tenant, tenant_id, candidate_id
):
    """Candidate already 'passed' is not re-scored."""
    from app.tasks.talent_scout_tasks import _score_candidate_async

    mock_candidate.status = "passed"
    mock_db = _make_db_mock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate))
    )

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.AIProvider") as MockAI:
            await _score_candidate_async(str(candidate_id), str(tenant_id))

    MockAI.assert_not_called()


@pytest.mark.asyncio
async def test_score_candidate_skips_empty_profile(
    mock_candidate, mock_tenant, tenant_id, candidate_id
):
    """Candidates with empty brightdata_profile are skipped without scoring."""
    from app.tasks.talent_scout_tasks import _score_candidate_async

    mock_candidate.status = "profiled"
    mock_candidate.brightdata_profile = {}

    mock_db = _make_db_mock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate))
    )

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.AIProvider") as MockAI:
            await _score_candidate_async(str(candidate_id), str(tenant_id))

    MockAI.assert_not_called()


# ── discover_email ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discover_email_via_apollo(
    mock_candidate, mock_tenant, tenant_id, candidate_id
):
    """Apollo provider finds email and stores it with correct source."""
    from app.tasks.talent_scout_tasks import _discover_email_async
    from app.services.crypto import encrypt

    mock_candidate.email = None
    mock_tenant.email_discovery_provider = "apollo"
    mock_tenant.apollo_api_key = encrypt("apollo-test-key")

    mock_db = _make_db_mock()
    db_execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
    ]
    mock_db.execute = AsyncMock(side_effect=db_execute_results)

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.apollo.find_email",
                   new_callable=AsyncMock, return_value="alice@acme.com"):
            with patch("app.tasks.talent_scout_tasks.settings") as mock_settings:
                mock_settings.scrapingdog_api_key = None
                await _discover_email_async(str(candidate_id), str(tenant_id))

    assert mock_candidate.email == "alice@acme.com"
    assert mock_candidate.email_source == "apollo"


@pytest.mark.asyncio
async def test_discover_email_via_hunter(
    mock_candidate, mock_tenant, tenant_id, candidate_id
):
    """Hunter provider finds email after domain lookup."""
    from app.tasks.talent_scout_tasks import _discover_email_async
    from app.services.crypto import encrypt

    mock_candidate.email = None
    mock_tenant.email_discovery_provider = "hunter"
    mock_tenant.hunter_api_key = encrypt("hunter-test-key")

    mock_db = _make_db_mock()
    db_execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
    ]
    mock_db.execute = AsyncMock(side_effect=db_execute_results)

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks._lookup_company_domain",
                   new_callable=AsyncMock, return_value="acme.com"):
            with patch("app.tasks.talent_scout_tasks.hunter.find_email",
                       new_callable=AsyncMock, return_value="alice@acme.com"):
                with patch("app.tasks.talent_scout_tasks.settings") as mock_settings:
                    mock_settings.scrapingdog_api_key = None
                    await _discover_email_async(str(candidate_id), str(tenant_id))

    assert mock_candidate.email == "alice@acme.com"
    assert mock_candidate.email_source == "hunter"


@pytest.mark.asyncio
async def test_discover_email_fallback_to_deduction(
    mock_candidate, mock_tenant, tenant_id, candidate_id
):
    """EmailDeductionService is used when configured provider returns None."""
    from app.tasks.talent_scout_tasks import _discover_email_async

    mock_candidate.email = None
    mock_tenant.email_discovery_provider = "domain_deduction"
    mock_tenant.apollo_api_key = None

    mock_db = _make_db_mock()
    db_execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
    ]
    mock_db.execute = AsyncMock(side_effect=db_execute_results)

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.EmailDeductionService") as MockDeducer:
            mock_deducer_inst = AsyncMock()
            mock_deducer_inst.find_email = AsyncMock(return_value="alice@acme.com")
            MockDeducer.return_value = mock_deducer_inst
            with patch("app.tasks.talent_scout_tasks.settings") as mock_settings:
                mock_settings.scrapingdog_api_key = None
                await _discover_email_async(str(candidate_id), str(tenant_id))

    assert mock_candidate.email == "alice@acme.com"
    assert mock_candidate.email_source == "deduced"


@pytest.mark.asyncio
async def test_discover_email_not_found_sets_unknown(
    mock_candidate, mock_tenant, tenant_id, candidate_id
):
    """When no email is found, source is set to 'unknown'."""
    from app.tasks.talent_scout_tasks import _discover_email_async

    mock_candidate.email = None
    mock_tenant.email_discovery_provider = "domain_deduction"
    mock_tenant.apollo_api_key = None

    mock_db = _make_db_mock()
    db_execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
    ]
    mock_db.execute = AsyncMock(side_effect=db_execute_results)

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.EmailDeductionService") as MockDeducer:
            mock_deducer_inst = AsyncMock()
            mock_deducer_inst.find_email = AsyncMock(return_value=None)
            MockDeducer.return_value = mock_deducer_inst
            with patch("app.tasks.talent_scout_tasks.settings") as mock_settings:
                mock_settings.scrapingdog_api_key = None
                await _discover_email_async(str(candidate_id), str(tenant_id))

    assert mock_candidate.email is None
    assert mock_candidate.email_source == "unknown"


@pytest.mark.asyncio
async def test_discover_email_idempotent_skips_existing(
    mock_candidate, mock_tenant, tenant_id, candidate_id
):
    """Candidate with existing email is not re-processed."""
    from app.tasks.talent_scout_tasks import _discover_email_async

    mock_candidate.email = "existing@acme.com"
    mock_db = _make_db_mock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate))
    )

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.apollo.find_email",
                   new_callable=AsyncMock) as mock_apollo:
            await _discover_email_async(str(candidate_id), str(tenant_id))

    mock_apollo.assert_not_called()


# ── send_outreach ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_send_outreach_success(
    mock_candidate, mock_job, mock_tenant, tenant_id, candidate_id
):
    """Passed candidate with email gets outreach email generated and sent."""
    from app.tasks.talent_scout_tasks import _send_outreach_async

    mock_candidate.status = "passed"
    mock_candidate.email = "alice@acme.com"
    mock_candidate.opted_out = False
    mock_candidate.outreach_email_sent_at = None
    mock_candidate.brightdata_profile = {"positions": [{"title": "Dev"}]}
    mock_candidate.job_id = mock_job.id

    mock_db = _make_db_mock()
    db_execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_job)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
    ]
    mock_db.execute = AsyncMock(side_effect=db_execute_results)

    ai_email = {
        "subject": "Exciting Java Developer opportunity",
        "body": "Hi Alice, I found your profile and think you'd be a great fit...",
    }

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.AIProvider") as MockAI:
            mock_ai_inst = AsyncMock()
            mock_ai_inst.complete_json = AsyncMock(return_value=ai_email)
            MockAI.return_value = mock_ai_inst
            with patch("app.tasks.talent_scout_tasks.send_email",
                       new_callable=AsyncMock, return_value=True):
                with patch("app.tasks.talent_scout_tasks.settings") as mock_settings:
                    mock_settings.frontend_url = "https://app.airecruiterz.com"
                    await _send_outreach_async(str(candidate_id), str(tenant_id))

    assert mock_candidate.status == "emailed"
    assert mock_candidate.outreach_email_sent_at is not None
    assert mock_candidate.outreach_email_content is not None


@pytest.mark.asyncio
async def test_send_outreach_skips_opted_out(
    mock_candidate, mock_tenant, tenant_id, candidate_id
):
    """Opted-out candidates are never emailed (GDPR)."""
    from app.tasks.talent_scout_tasks import _send_outreach_async

    mock_candidate.status = "passed"
    mock_candidate.email = "alice@acme.com"
    mock_candidate.opted_out = True

    mock_db = _make_db_mock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate))
    )

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.AIProvider") as MockAI:
            await _send_outreach_async(str(candidate_id), str(tenant_id))

    MockAI.assert_not_called()


@pytest.mark.asyncio
async def test_send_outreach_skips_failed_candidates(
    mock_candidate, mock_tenant, tenant_id, candidate_id
):
    """Candidates that failed scoring are not emailed."""
    from app.tasks.talent_scout_tasks import _send_outreach_async

    mock_candidate.status = "failed"
    mock_candidate.email = "alice@acme.com"
    mock_candidate.opted_out = False

    mock_db = _make_db_mock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate))
    )

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.AIProvider") as MockAI:
            await _send_outreach_async(str(candidate_id), str(tenant_id))

    MockAI.assert_not_called()


@pytest.mark.asyncio
async def test_send_outreach_skips_no_email(
    mock_candidate, mock_tenant, tenant_id, candidate_id
):
    """Candidates without a discovered email address are not emailed."""
    from app.tasks.talent_scout_tasks import _send_outreach_async

    mock_candidate.status = "passed"
    mock_candidate.email = None
    mock_candidate.opted_out = False

    mock_db = _make_db_mock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate))
    )

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.AIProvider") as MockAI:
            await _send_outreach_async(str(candidate_id), str(tenant_id))

    MockAI.assert_not_called()


@pytest.mark.asyncio
async def test_send_outreach_idempotent_skips_already_sent(
    mock_candidate, mock_tenant, tenant_id, candidate_id
):
    """Candidate who already received outreach is not emailed again."""
    from app.tasks.talent_scout_tasks import _send_outreach_async

    mock_candidate.status = "passed"
    mock_candidate.email = "alice@acme.com"
    mock_candidate.opted_out = False
    mock_candidate.outreach_email_sent_at = datetime.now(timezone.utc)

    mock_db = _make_db_mock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate))
    )

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.AIProvider") as MockAI:
            await _send_outreach_async(str(candidate_id), str(tenant_id))

    MockAI.assert_not_called()


@pytest.mark.asyncio
async def test_send_outreach_includes_unsubscribe_link(
    mock_candidate, mock_job, mock_tenant, tenant_id, candidate_id
):
    """Generated email HTML must contain the GDPR unsubscribe link."""
    from app.tasks.talent_scout_tasks import _send_outreach_async

    mock_candidate.status = "passed"
    mock_candidate.email = "alice@acme.com"
    mock_candidate.opted_out = False
    mock_candidate.outreach_email_sent_at = None
    mock_candidate.brightdata_profile = {}
    mock_candidate.job_id = mock_job.id

    mock_db = _make_db_mock()
    db_execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_job)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
    ]
    mock_db.execute = AsyncMock(side_effect=db_execute_results)

    captured_calls: list[dict] = []

    async def capture_send_email(to, subject, html_body, tenant):
        captured_calls.append({"to": to, "subject": subject, "html_body": html_body})
        return True

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.AIProvider") as MockAI:
            mock_ai_inst = AsyncMock()
            mock_ai_inst.complete_json = AsyncMock(
                return_value={"subject": "Test", "body": "Hello Alice, we are excited to reach out about this opportunity."}
            )
            MockAI.return_value = mock_ai_inst
            with patch("app.tasks.talent_scout_tasks.send_email", side_effect=capture_send_email):
                with patch("app.tasks.talent_scout_tasks.settings") as mock_settings:
                    mock_settings.frontend_url = "https://app.airecruiterz.com"
                    await _send_outreach_async(str(candidate_id), str(tenant_id))

    assert captured_calls, "send_email was not called"
    html = captured_calls[0]["html_body"]
    assert "unsubscribe" in html.lower()
    assert str(candidate_id) in html


@pytest.mark.asyncio
async def test_send_outreach_sendgrid_failure_does_not_update_status(
    mock_candidate, mock_job, mock_tenant, tenant_id, candidate_id
):
    """If SendGrid rejects the email, status remains 'passed' (not 'emailed')."""
    from app.tasks.talent_scout_tasks import _send_outreach_async

    mock_candidate.status = "passed"
    mock_candidate.email = "alice@acme.com"
    mock_candidate.opted_out = False
    mock_candidate.outreach_email_sent_at = None
    mock_candidate.brightdata_profile = {}
    mock_candidate.job_id = mock_job.id

    mock_db = _make_db_mock()
    db_execute_results = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_candidate)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_job)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
    ]
    mock_db.execute = AsyncMock(side_effect=db_execute_results)

    with _patch_session(mock_db):
        with patch("app.tasks.talent_scout_tasks.AIProvider") as MockAI:
            mock_ai_inst = AsyncMock()
            mock_ai_inst.complete_json = AsyncMock(
                return_value={"subject": "Test", "body": "Hello Alice, we are excited to reach out about this opportunity."}
            )
            MockAI.return_value = mock_ai_inst
            with patch("app.tasks.talent_scout_tasks.send_email",
                       new_callable=AsyncMock, return_value=False):
                with patch("app.tasks.talent_scout_tasks.settings") as mock_settings:
                    mock_settings.frontend_url = "https://app.airecruiterz.com"
                    await _send_outreach_async(str(candidate_id), str(tenant_id))

    # Status should NOT have been changed to 'emailed'
    assert mock_candidate.status == "passed"
    assert mock_candidate.outreach_email_sent_at is None
