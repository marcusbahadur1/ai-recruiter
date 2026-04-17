"""Unit tests for TalentScoutService.build_search_queries.

Tests verify:
- Location rules by work_type (SPEC §7.1.1)
- Title × location Cartesian product
- Deduplication of queries and inputs
- remote_global omits location
- Audit emitters call AuditTrailService.emit with correct args
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.talent_scout import (
    TalentScoutService,
    _build_location_list,
    _build_title_list,
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def make_job(**kwargs) -> MagicMock:
    j = MagicMock()
    j.id = uuid.uuid4()
    j.title = kwargs.get("title", "Java Developer")
    j.title_variations = kwargs.get("title_variations", [])
    j.location = kwargs.get("location", "Sydney")
    j.location_variations = kwargs.get("location_variations", [])
    j.work_type = kwargs.get("work_type", "hybrid")
    return j


def make_service() -> tuple[TalentScoutService, AsyncMock]:
    db = AsyncMock()
    begin_ctx = AsyncMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=None)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    db.begin = MagicMock(return_value=begin_ctx)
    db.flush = AsyncMock()
    tenant_id = uuid.uuid4()
    service = TalentScoutService(db, tenant_id)
    return service, db


# ── _build_title_list ──────────────────────────────────────────────────────────


def test_build_title_list_no_variations():
    job = make_job(title="Accountant", title_variations=[])
    assert _build_title_list(job) == ["Accountant"]


def test_build_title_list_with_variations():
    job = make_job(
        title="Accountant",
        title_variations=["Finance Manager", "Management Accountant", "CPA"],
    )
    result = _build_title_list(job)
    assert result == ["Accountant", "Finance Manager", "Management Accountant", "CPA"]


def test_build_title_list_deduplicates():
    job = make_job(
        title="Java Developer", title_variations=["Java Developer", "Backend Dev"]
    )
    result = _build_title_list(job)
    assert result.count("Java Developer") == 1
    assert "Backend Dev" in result


def test_build_title_list_skips_empty():
    job = make_job(title="Dev", title_variations=["", None, "Backend"])
    result = _build_title_list(job)
    assert "" not in result
    assert None not in result
    assert "Backend" in result


# ── _build_location_list ───────────────────────────────────────────────────────


def test_build_location_list_no_variations():
    job = make_job(location="Melbourne", location_variations=[])
    assert _build_location_list(job) == ["Melbourne"]


def test_build_location_list_with_variations():
    job = make_job(
        location="Sydney",
        location_variations=["Melbourne", "Brisbane"],
    )
    result = _build_location_list(job)
    assert result == ["Sydney", "Melbourne", "Brisbane"]


def test_build_location_list_deduplicates():
    job = make_job(location="Sydney", location_variations=["Sydney", "Melbourne"])
    result = _build_location_list(job)
    assert result.count("Sydney") == 1


def test_build_location_list_skips_empty():
    job = make_job(location="Sydney", location_variations=["", None])
    result = _build_location_list(job)
    assert "" not in result
    assert None not in result


# ── build_search_queries — work_type: onsite ───────────────────────────────────


def test_build_queries_onsite_single_title_single_location():
    service, _ = make_service()
    job = make_job(
        title="Java Developer",
        title_variations=[],
        location="Sydney",
        location_variations=[],
        work_type="onsite",
    )
    queries = service.build_search_queries(job)
    assert queries == ['"Java Developer" Sydney site:linkedin.com/in/']


def test_build_queries_onsite_title_variations_expand():
    service, _ = make_service()
    job = make_job(
        title="Accountant",
        title_variations=["Finance Manager", "CPA"],
        location="Sydney",
        location_variations=[],
        work_type="onsite",
    )
    queries = service.build_search_queries(job)
    assert len(queries) == 3
    assert '"Accountant" Sydney site:linkedin.com/in/' in queries
    assert '"Finance Manager" Sydney site:linkedin.com/in/' in queries
    assert '"CPA" Sydney site:linkedin.com/in/' in queries


def test_build_queries_onsite_location_variations_expand():
    service, _ = make_service()
    job = make_job(
        title="Java Developer",
        title_variations=[],
        location="Sydney",
        location_variations=["Parramatta", "North Sydney"],
        work_type="onsite",
    )
    queries = service.build_search_queries(job)
    assert len(queries) == 3
    assert '"Java Developer" Sydney site:linkedin.com/in/' in queries
    assert '"Java Developer" Parramatta site:linkedin.com/in/' in queries
    assert '"Java Developer" North Sydney site:linkedin.com/in/' in queries


def test_build_queries_onsite_full_cartesian_product():
    service, _ = make_service()
    job = make_job(
        title="Developer",
        title_variations=["Engineer"],
        location="Sydney",
        location_variations=["Melbourne"],
        work_type="onsite",
    )
    queries = service.build_search_queries(job)
    assert len(queries) == 4  # 2 titles × 2 locations
    assert '"Developer" Sydney site:linkedin.com/in/' in queries
    assert '"Developer" Melbourne site:linkedin.com/in/' in queries
    assert '"Engineer" Sydney site:linkedin.com/in/' in queries
    assert '"Engineer" Melbourne site:linkedin.com/in/' in queries


def test_build_queries_onsite_deduplicates_queries():
    service, _ = make_service()
    job = make_job(
        title="Dev",
        title_variations=["Dev"],  # duplicate title
        location="Sydney",
        location_variations=[],
        work_type="onsite",
    )
    queries = service.build_search_queries(job)
    assert queries.count('"Dev" Sydney site:linkedin.com/in/') == 1


# ── build_search_queries — work_type: hybrid ──────────────────────────────────


def test_build_queries_hybrid_same_as_onsite():
    """hybrid uses location_variations (nearby cities) same as onsite."""
    service, _ = make_service()
    job = make_job(
        title="Designer",
        title_variations=[],
        location="Brisbane",
        location_variations=["Gold Coast"],
        work_type="hybrid",
    )
    queries = service.build_search_queries(job)
    assert len(queries) == 2
    assert '"Designer" Brisbane site:linkedin.com/in/' in queries
    assert '"Designer" Gold Coast site:linkedin.com/in/' in queries


# ── build_search_queries — work_type: remote ──────────────────────────────────


def test_build_queries_remote_uses_location_variations():
    """remote uses major cities in the same country — stored in location_variations."""
    service, _ = make_service()
    job = make_job(
        title="Python Developer",
        title_variations=[],
        location="Australia",
        location_variations=["Sydney", "Melbourne", "Brisbane"],
        work_type="remote",
    )
    queries = service.build_search_queries(job)
    assert len(queries) == 4  # base + 3 variations
    assert '"Python Developer" Australia site:linkedin.com/in/' in queries
    assert '"Python Developer" Sydney site:linkedin.com/in/' in queries


# ── build_search_queries — work_type: remote_global ───────────────────────────


def test_build_queries_remote_global_no_location():
    """remote_global omits location filter entirely — one query per title."""
    service, _ = make_service()
    job = make_job(
        title="Backend Engineer",
        title_variations=["Software Engineer", "Python Dev"],
        location="Global",
        location_variations=["USA", "UK"],  # ignored for remote_global
        work_type="remote_global",
    )
    queries = service.build_search_queries(job)
    assert len(queries) == 3  # 3 titles, no location factor
    assert '"Backend Engineer" site:linkedin.com/in/' in queries
    assert '"Software Engineer" site:linkedin.com/in/' in queries
    assert '"Python Dev" site:linkedin.com/in/' in queries
    # Location must not appear in any query
    for q in queries:
        assert "Global" not in q
        assert "USA" not in q


def test_build_queries_remote_global_single_title():
    service, _ = make_service()
    job = make_job(
        title="DevOps Engineer",
        title_variations=[],
        location="Worldwide",
        location_variations=[],
        work_type="remote_global",
    )
    queries = service.build_search_queries(job)
    assert queries == ['"DevOps Engineer" site:linkedin.com/in/']


# ── Audit emitters ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_emit_job_started_calls_audit():
    service, db = make_service()
    job_id = uuid.uuid4()

    with patch.object(service._audit, "emit", new_callable=AsyncMock) as mock_emit:
        await service.emit_job_started(job_id, "Java Developer")
        mock_emit.assert_called_once()
        call_kwargs = mock_emit.call_args.kwargs
        assert call_kwargs["event_type"] == "scout.job_started"
        assert call_kwargs["event_category"] == "talent_scout"
        assert call_kwargs["severity"] == "info"
        assert "Java Developer" in call_kwargs["summary"]


@pytest.mark.asyncio
async def test_emit_queries_built_calls_audit():
    service, _ = make_service()
    job_id = uuid.uuid4()

    with patch.object(service._audit, "emit", new_callable=AsyncMock) as mock_emit:
        await service.emit_queries_built(job_id, 6, 3, 2)
        mock_emit.assert_called_once()
        call_kwargs = mock_emit.call_args.kwargs
        assert call_kwargs["event_type"] == "scout.search_query_built"
        assert call_kwargs["detail"]["query_count"] == 6
        assert call_kwargs["detail"]["title_count"] == 3
        assert call_kwargs["detail"]["location_count"] == 2


@pytest.mark.asyncio
async def test_emit_scoring_success_passed():
    service, _ = make_service()
    job_id = uuid.uuid4()
    candidate_id = uuid.uuid4()

    with patch.object(service._audit, "emit", new_callable=AsyncMock) as mock_emit:
        await service.emit_scoring_success(job_id, candidate_id, 8, True, 500)
        call_kwargs = mock_emit.call_args.kwargs
        assert call_kwargs["event_type"] == "scout.scoring_success"
        assert call_kwargs["severity"] == "success"
        assert "8/10" in call_kwargs["summary"]
        assert "passed" in call_kwargs["summary"]


@pytest.mark.asyncio
async def test_emit_scoring_success_failed_threshold():
    service, _ = make_service()
    job_id = uuid.uuid4()
    candidate_id = uuid.uuid4()

    with patch.object(service._audit, "emit", new_callable=AsyncMock) as mock_emit:
        await service.emit_scoring_success(job_id, candidate_id, 4, False, 500)
        call_kwargs = mock_emit.call_args.kwargs
        assert call_kwargs["event_type"] == "scout.scoring_failed_threshold"
        assert call_kwargs["severity"] == "info"
        assert "4/10" in call_kwargs["summary"]


@pytest.mark.asyncio
async def test_emit_email_found_apollo():
    service, _ = make_service()
    job_id = uuid.uuid4()
    candidate_id = uuid.uuid4()

    with patch.object(service._audit, "emit", new_callable=AsyncMock) as mock_emit:
        await service.emit_email_found(job_id, candidate_id, "apollo")
        call_kwargs = mock_emit.call_args.kwargs
        assert call_kwargs["event_type"] == "scout.email_found_apollo"
        assert call_kwargs["severity"] == "success"


@pytest.mark.asyncio
async def test_emit_email_found_deduced():
    service, _ = make_service()
    job_id = uuid.uuid4()
    candidate_id = uuid.uuid4()

    with patch.object(service._audit, "emit", new_callable=AsyncMock) as mock_emit:
        await service.emit_email_found(job_id, candidate_id, "deduced")
        call_kwargs = mock_emit.call_args.kwargs
        assert call_kwargs["event_type"] == "scout.email_found_deduced"


@pytest.mark.asyncio
async def test_emit_task_failed_permanent():
    service, _ = make_service()
    job_id = uuid.uuid4()
    candidate_id = uuid.uuid4()

    with patch.object(service._audit, "emit", new_callable=AsyncMock) as mock_emit:
        await service.emit_task_failed_permanent(
            job_id, candidate_id, "enrich_profile", "Connection refused"
        )
        call_kwargs = mock_emit.call_args.kwargs
        assert call_kwargs["event_type"] == "system.task_failed_permanent"
        assert call_kwargs["event_category"] == "system"
        assert call_kwargs["severity"] == "error"
        assert call_kwargs["detail"]["task"] == "enrich_profile"
        assert "Connection refused" in call_kwargs["detail"]["error"]


# ── Parsing helpers (tested via the module import) ─────────────────────────────


def test_parse_linkedin_result_dash_format():
    from app.tasks.talent_scout_tasks import _parse_linkedin_result

    name, title = _parse_linkedin_result("Divesh Premdeep - Java Developer | LinkedIn")
    assert name == "Divesh Premdeep"
    assert title == "Java Developer"


def test_parse_linkedin_result_pipe_format():
    from app.tasks.talent_scout_tasks import _parse_linkedin_result

    name, title = _parse_linkedin_result(
        "Jane Doe | Senior Engineer at Acme | LinkedIn"
    )
    assert name == "Jane Doe"
    assert "Senior Engineer" in title


def test_parse_linkedin_result_name_only():
    from app.tasks.talent_scout_tasks import _parse_linkedin_result

    name, title = _parse_linkedin_result("John Smith | LinkedIn")
    assert name == "John Smith"
    assert title == ""


def test_is_linkedin_profile_url():
    from app.tasks.talent_scout_tasks import _is_linkedin_profile_url

    assert _is_linkedin_profile_url("https://www.linkedin.com/in/john-doe")
    assert not _is_linkedin_profile_url("https://www.linkedin.com/company/acme")
    assert not _is_linkedin_profile_url("")
    assert not _is_linkedin_profile_url("https://example.com")
