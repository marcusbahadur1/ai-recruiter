"""Integration tests for the Resume Screener task pipeline.

Tests call the async ``_*_impl`` functions directly, mock all external
services, and assert on DB state changes and audit events.

Mock strategy:
- IMAP         → pre-loaded test emails via a sync mock
- AI provider  → deterministic JSON via unittest.mock
- SendGrid     → mock capturing calls
- Embeddings   → returns a fixed 1536-dim vector
"""

import uuid
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.integration.conftest import make_application, make_db_mock, make_job

TENANT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
JOB_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
APPLICATION_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


# ── Shared fixtures ────────────────────────────────────────────────────────────


@pytest.fixture()
def tenant_id():
    return TENANT_ID


@pytest.fixture()
def job_id():
    return JOB_ID


@pytest.fixture()
def application_id():
    return APPLICATION_ID


@pytest.fixture()
def mock_tenant(tenant_id):
    t = MagicMock()
    t.id = tenant_id
    t.name = "Test Firm"
    t.slug = "test-firm"
    t.is_active = True
    t.ai_provider = "anthropic"
    t.ai_api_key = None
    t.sendgrid_api_key = None
    t.email_inbox = "jobs-test@airecruiterz.com"
    t.email_inbox_host = None
    t.email_inbox_user = None
    t.email_inbox_password = None
    t.email_inbox_port = None
    t.credits_remaining = 10
    t.plan = "individual"
    return t


@pytest.fixture()
def mock_job(tenant_id, job_id):
    return make_job(
        tenant_id,
        id=job_id,
        title="Python Developer",
        job_type="Software Engineer",
        job_ref="PYDEV001",
        required_skills=["Python", "FastAPI"],
        experience_years=3,
        minimum_score=6,
        evaluation_prompt=None,
        hiring_manager_email="hm@firm.com",
        hiring_manager_name="Jane HM",
        interview_questions_count=3,
        custom_interview_questions=None,
    )


@pytest.fixture()
def mock_application(tenant_id, job_id, application_id):
    a = make_application(
        tenant_id,
        job_id,
        id=application_id,
        screening_status="pending",
        test_status="not_started",
        resume_text="5 years of Python FastAPI experience.",
        resume_embedding=[0.1] * 1536,
    )
    return a


@pytest.fixture()
def mock_db():
    from tests.integration.conftest import make_db_mock

    return make_db_mock()


def _make_db_with_returns(*return_values):
    """DB mock that returns different scalars per execute() call."""
    db = MagicMock()
    begin_ctx = AsyncMock()
    begin_ctx.__aenter__ = AsyncMock(return_value=None)
    begin_ctx.__aexit__ = AsyncMock(return_value=False)
    db.begin = MagicMock(return_value=begin_ctx)
    db.flush = AsyncMock(return_value=None)
    db.commit = AsyncMock(return_value=None)
    db.rollback = AsyncMock(return_value=None)
    db.add = MagicMock()

    call_count = 0

    async def execute_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        m = MagicMock()
        if call_count <= len(return_values):
            m.scalar_one_or_none.return_value = return_values[call_count - 1]
            m.scalars.return_value.all.return_value = (
                return_values[call_count - 1]
                if isinstance(return_values[call_count - 1], list)
                else []
            )
        else:
            m.scalar_one_or_none.return_value = None
        return m

    db.execute = execute_side_effect
    return db


# ── Test: _screen_resume_impl ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_screen_resume_passes_and_queues_invite(
    mock_tenant, mock_job, mock_application, tenant_id, application_id
):
    """Application with score ≥ minimum_score transitions to passed and triggers invite_to_test."""
    mock_application.screening_status = "pending"
    mock_application.resume_embedding = [0.9] * 1536

    ai_result = {
        "score": 8,
        "reasoning": "Strong Python background.",
        "strengths": ["Python", "FastAPI"],
        "gaps": [],
        "recommended_action": "pass",
    }

    with (
        patch("app.tasks.screener_tasks.AsyncSessionLocal") as MockSession,
        patch("app.tasks.screener_tasks.AIProvider") as MockAI,
        patch(
            "app.tasks.screener_tasks.generate_embedding",
            new_callable=AsyncMock,
            return_value=[0.85] * 1536,
        ),
        patch(
            "app.tasks.screener_tasks.send_email",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch("app.tasks.screener_tasks.invite_to_test") as MockInviteTask,
    ):
        db = _make_db_with_returns(mock_application, mock_job, mock_tenant)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=db)
        ctx.__aexit__ = AsyncMock(return_value=False)
        MockSession.return_value = ctx

        mock_ai_instance = AsyncMock()
        mock_ai_instance.complete_json = AsyncMock(return_value=ai_result)
        MockAI.return_value = mock_ai_instance

        from app.tasks.screener_tasks import _screen_resume_impl

        await _screen_resume_impl(application_id, tenant_id)

    assert mock_application.screening_score == 8
    assert mock_application.resume_score == 8
    assert mock_application.screening_status == "passed"
    assert mock_application.status == "screened_passed"
    MockInviteTask.delay.assert_called_once_with(str(application_id), str(tenant_id))


@pytest.mark.asyncio
async def test_screen_resume_fails_and_sends_rejection(
    mock_tenant, mock_job, mock_application, tenant_id, application_id
):
    """Application with score < minimum_score transitions to failed and queues rejection task."""
    mock_application.screening_status = "pending"
    mock_application.resume_embedding = [0.1] * 1536

    ai_result = {
        "score": 3,
        "reasoning": "Insufficient experience.",
        "strengths": [],
        "gaps": ["Python"],
        "recommended_action": "fail",
    }

    with (
        patch("app.tasks.screener_tasks.AsyncSessionLocal") as MockSession,
        patch("app.tasks.screener_tasks.AIProvider") as MockAI,
        patch(
            "app.tasks.screener_tasks.generate_embedding",
            new_callable=AsyncMock,
            return_value=[0.1] * 1536,
        ),
        patch(
            "app.tasks.screener_tasks.send_email",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch("app.tasks.screener_tasks.invite_to_test") as MockInvite,
        patch("app.tasks.screener_tasks.send_rejection_email") as MockReject,
    ):
        db = _make_db_with_returns(mock_application, mock_job, mock_tenant)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=db)
        ctx.__aexit__ = AsyncMock(return_value=False)
        MockSession.return_value = ctx

        mock_ai_instance = AsyncMock()
        mock_ai_instance.complete_json = AsyncMock(return_value=ai_result)
        MockAI.return_value = mock_ai_instance

        from app.tasks.screener_tasks import _screen_resume_impl

        await _screen_resume_impl(application_id, tenant_id)

    assert mock_application.screening_score == 3
    assert mock_application.screening_status == "failed"
    assert mock_application.status == "screened_failed"
    MockInvite.delay.assert_not_called()
    MockReject.delay.assert_called_once_with(str(application_id), str(tenant_id))


@pytest.mark.asyncio
async def test_screen_resume_skips_non_pending(
    mock_tenant, mock_job, mock_application, tenant_id, application_id
):
    """screen_resume is idempotent — skips if not in 'pending' status."""
    mock_application.screening_status = "passed"

    with (
        patch("app.tasks.screener_tasks.AsyncSessionLocal") as MockSession,
        patch("app.tasks.screener_tasks.AIProvider") as MockAI,
    ):
        db = _make_db_with_returns(mock_application)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=db)
        ctx.__aexit__ = AsyncMock(return_value=False)
        MockSession.return_value = ctx

        from app.tasks.screener_tasks import _screen_resume_impl

        await _screen_resume_impl(application_id, tenant_id)

    MockAI.assert_not_called()


# ── Test: _invite_to_test_impl ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invite_to_test_generates_questions_and_sends_email(
    mock_tenant, mock_job, mock_application, tenant_id, application_id
):
    """invite_to_test generates questions, creates TestSession, updates app, sends email."""
    mock_application.test_status = "not_started"
    mock_application.screening_status = "passed"

    with (
        patch("app.tasks.screener_tasks.AsyncSessionLocal") as MockSession,
        patch("app.tasks.screener_tasks.AIProvider") as MockAI,
        patch(
            "app.tasks.screener_tasks.send_email",
            new_callable=AsyncMock,
            return_value=True,
        ) as MockEmail,
    ):
        db = _make_db_with_returns(mock_application, mock_job, mock_tenant)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=db)
        ctx.__aexit__ = AsyncMock(return_value=False)
        MockSession.return_value = ctx

        mock_ai_instance = AsyncMock()
        mock_ai_instance.complete = AsyncMock(return_value='["Q1?", "Q2?", "Q3?"]')
        MockAI.return_value = mock_ai_instance

        from app.tasks.screener_tasks import _invite_to_test_impl

        await _invite_to_test_impl(application_id, tenant_id)

    assert mock_application.test_status == "invited"
    assert mock_application.status == "test_invited"
    assert mock_application.interview_invite_token is not None
    assert mock_application.interview_invite_expires_at is not None
    assert isinstance(mock_application.test_answers, dict)
    assert len(mock_application.test_answers["questions"]) == 3
    MockEmail.assert_called_once()
    db.add.assert_called()  # TestSession was added to db


@pytest.mark.asyncio
async def test_invite_to_test_skips_if_already_invited(
    mock_tenant, mock_job, mock_application, tenant_id, application_id
):
    """invite_to_test is idempotent — skips if test_status != 'not_started'."""
    mock_application.test_status = "invited"

    with (
        patch("app.tasks.screener_tasks.AsyncSessionLocal") as MockSession,
        patch(
            "app.tasks.screener_tasks.send_email", new_callable=AsyncMock
        ) as MockEmail,
    ):
        db = _make_db_with_returns(mock_application)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=db)
        ctx.__aexit__ = AsyncMock(return_value=False)
        MockSession.return_value = ctx

        from app.tasks.screener_tasks import _invite_to_test_impl

        await _invite_to_test_impl(application_id, tenant_id)

    MockEmail.assert_not_called()


# ── Test: _score_test_impl ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_score_test_passes_and_notifies_hm(
    mock_tenant, mock_job, mock_application, tenant_id, application_id
):
    """score_test: passed result queues notify_hiring_manager, sets test_status='passed'."""
    mock_application.test_status = "completed"
    mock_application.test_score = None  # not yet scored
    mock_application.screening_score = 7
    mock_application.test_answers = {
        "questions": ["Q1?"],
        "current_question_idx": 1,
        "answers": [{"question_index": 0, "answer": "I know Python well."}],
        "full_conversation": [],
    }

    ai_result = {
        "overall_score": 8,
        "overall_summary": "Good Python knowledge demonstrated.",
        "recommended_action": "pass",
        "strengths": ["Python"],
        "gaps": [],
        "questions": [
            {
                "question": "Q1?",
                "candidate_answer": "I know Python well.",
                "assessment": "Strong",
                "rating": "strong",
                "score": 8,
            }
        ],
    }

    with (
        patch("app.tasks.screener_tasks.AsyncSessionLocal") as MockSession,
        patch("app.tasks.screener_tasks.AIProvider") as MockAI,
        patch("app.tasks.screener_tasks.notify_hiring_manager") as MockHMTask,
        patch("app.tasks.screener_tasks.send_rejection_email") as MockReject,
    ):
        # score_test loads: application, job, tenant, then TestSession (returns None for fallback)
        db = _make_db_with_returns(mock_application, mock_job, mock_tenant, None)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=db)
        ctx.__aexit__ = AsyncMock(return_value=False)
        MockSession.return_value = ctx

        mock_ai_instance = AsyncMock()
        mock_ai_instance.complete_json = AsyncMock(return_value=ai_result)
        MockAI.return_value = mock_ai_instance

        from app.tasks.screener_tasks import _score_test_impl

        await _score_test_impl(application_id, tenant_id)

    assert mock_application.test_score == 8
    assert mock_application.test_status == "passed"
    assert mock_application.status == "test_passed"
    MockHMTask.delay.assert_called_once_with(str(application_id), str(tenant_id))
    MockReject.delay.assert_not_called()


@pytest.mark.asyncio
async def test_score_test_fails_and_rejects_candidate(
    mock_tenant, mock_job, mock_application, tenant_id, application_id
):
    """score_test: failed result queues send_rejection_email, sets test_status='failed'."""
    mock_application.test_status = "completed"
    mock_application.test_score = None
    mock_application.test_answers = {
        "questions": ["Q1?"],
        "current_question_idx": 1,
        "answers": [{"question_index": 0, "answer": "I don't know."}],
        "full_conversation": [],
    }

    ai_result = {
        "overall_score": 2,
        "overall_summary": "Very weak answers.",
        "recommended_action": "fail",
        "strengths": [],
        "gaps": ["Python"],
        "questions": [],
    }

    with (
        patch("app.tasks.screener_tasks.AsyncSessionLocal") as MockSession,
        patch("app.tasks.screener_tasks.AIProvider") as MockAI,
        patch("app.tasks.screener_tasks.notify_hiring_manager") as MockHMTask,
        patch("app.tasks.screener_tasks.send_rejection_email") as MockReject,
    ):
        db = _make_db_with_returns(mock_application, mock_job, mock_tenant, None)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=db)
        ctx.__aexit__ = AsyncMock(return_value=False)
        MockSession.return_value = ctx

        mock_ai_instance = AsyncMock()
        mock_ai_instance.complete_json = AsyncMock(return_value=ai_result)
        MockAI.return_value = mock_ai_instance

        from app.tasks.screener_tasks import _score_test_impl

        await _score_test_impl(application_id, tenant_id)

    assert mock_application.test_score == 2
    assert mock_application.test_status == "failed"
    assert mock_application.status == "test_failed"
    MockReject.delay.assert_called_once_with(str(application_id), str(tenant_id))
    MockHMTask.delay.assert_not_called()


@pytest.mark.asyncio
async def test_score_test_skips_non_completed(
    mock_tenant, mock_job, mock_application, tenant_id, application_id
):
    """score_test is idempotent — skips if test_status is not 'completed'."""
    mock_application.test_status = "in_progress"
    mock_application.test_score = None  # not yet scored

    with (
        patch("app.tasks.screener_tasks.AsyncSessionLocal") as MockSession,
        patch("app.tasks.screener_tasks.AIProvider") as MockAI,
    ):
        db = _make_db_with_returns(mock_application)
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=db)
        ctx.__aexit__ = AsyncMock(return_value=False)
        MockSession.return_value = ctx

        from app.tasks.screener_tasks import _score_test_impl

        await _score_test_impl(application_id, tenant_id)

    MockAI.assert_not_called()


# ── Test: _poll_mailboxes_impl ─────────────────────────────────────────────────


def _make_raw_email(
    subject: str = "PYDEV001 – Alice Smith Application",
    sender_name: str = "Alice Smith",
    sender_email: str = "alice@example.com",
    include_pdf: bool = True,
    message_id: str = "<test-msg-id@example.com>",
) -> dict:
    """Build a pre-parsed email dict as _parse_raw_email would return."""
    attachment_bytes = b"%PDF-1.4 fake pdf content" if include_pdf else None
    return {
        "subject": subject,
        "message_id": message_id,
        "sender_name": sender_name,
        "sender_email": sender_email,
        "attachment_bytes": attachment_bytes,
        "attachment_ext": "pdf" if include_pdf else "",
    }


@pytest.mark.asyncio
async def test_poll_mailboxes_creates_application_and_triggers_screening(
    mock_tenant, mock_job, tenant_id, job_id
):
    """poll_mailboxes: valid email with PDF creates Application and queues screen_resume."""
    raw_email = _make_raw_email()
    mock_tenant.email_inbox_host = "imap.example.com"
    mock_tenant.email_inbox_user = "jobs@example.com"
    mock_tenant.email_inbox_password = "encrypted-secret"
    mock_tenant.email_inbox_port = 993

    with (
        patch("app.tasks.screener_tasks.AsyncSessionLocal") as MockSession,
        patch(
            "app.tasks.screener_tasks.generate_embedding",
            new_callable=AsyncMock,
            return_value=[0.5] * 1536,
        ),
        patch("app.tasks.screener_tasks._fetch_imap_emails", return_value=[raw_email]),
        patch("app.tasks.screener_tasks.screen_resume") as MockScreen,
        patch(
            "app.tasks.screener_tasks._extract_text", return_value="Resume content here"
        ) as MockExtract,
    ):
        # First call: get_active_tenants (returns [mock_tenant])
        # Then for each email: job lookup, candidate lookup, duplicate check
        tenants_result = MagicMock()
        tenants_result.scalars.return_value.all.return_value = [mock_tenant]
        db_tenants = make_db_mock()
        db_tenants.execute = AsyncMock(return_value=tenants_result)

        db_process = _make_db_with_returns(
            mock_job,  # _get_job_by_ref
            None,  # _find_duplicate (no dup)
            None,  # _find_candidate_by_email (no match)
        )

        class Ctx:
            def __init__(self, db):
                self._db = db

            async def __aenter__(self):
                return self._db

            async def __aexit__(self, *args):
                pass

        session_instances = [Ctx(db_tenants), Ctx(db_process)]
        idx = [0]

        def session_factory():
            i = min(idx[0], len(session_instances) - 1)
            idx[0] += 1
            return session_instances[i]

        MockSession.side_effect = session_factory

        from app.tasks.screener_tasks import _poll_mailboxes_impl

        await _poll_mailboxes_impl()

    MockScreen.delay.assert_called_once()
    MockExtract.assert_called_once_with(raw_email["attachment_bytes"], "pdf")


@pytest.mark.asyncio
async def test_poll_mailboxes_no_attachment_sends_auto_reply(
    mock_tenant, mock_job, tenant_id
):
    """poll_mailboxes: email without attachment triggers auto-reply."""
    raw_email = _make_raw_email(include_pdf=False)
    mock_tenant.email_inbox_host = "imap.example.com"
    mock_tenant.email_inbox_user = "jobs@example.com"
    mock_tenant.email_inbox_password = "encrypted-secret"
    mock_tenant.email_inbox_port = 993

    with (
        patch("app.tasks.screener_tasks.AsyncSessionLocal") as MockSession,
        patch("app.tasks.screener_tasks._fetch_imap_emails", return_value=[raw_email]),
        patch(
            "app.tasks.screener_tasks.send_email",
            new_callable=AsyncMock,
            return_value=True,
        ) as MockEmail,
        patch("app.tasks.screener_tasks.screen_resume") as MockScreen,
    ):
        tenants_result = MagicMock()
        tenants_result.scalars.return_value.all.return_value = [mock_tenant]
        db_tenants = make_db_mock()
        db_tenants.execute = AsyncMock(return_value=tenants_result)

        db_process = _make_db_with_returns(mock_job, None)

        class Ctx:
            def __init__(self, db):
                self._db = db

            async def __aenter__(self):
                return self._db

            async def __aexit__(self, *args):
                pass

        session_instances = [Ctx(db_tenants), Ctx(db_process)]
        idx = [0]

        def factory():
            i = min(idx[0], len(session_instances) - 1)
            idx[0] += 1
            return session_instances[i]

        MockSession.side_effect = factory

        from app.tasks.screener_tasks import _poll_mailboxes_impl

        await _poll_mailboxes_impl()

    MockEmail.assert_called_once()
    MockScreen.delay.assert_not_called()


@pytest.mark.asyncio
async def test_poll_mailboxes_deduplicates_by_message_id(
    mock_tenant, mock_job, mock_application, tenant_id
):
    """poll_mailboxes: duplicate Message-ID skips Application creation."""
    raw_email = _make_raw_email()
    mock_tenant.email_inbox_host = "imap.example.com"
    mock_tenant.email_inbox_user = "jobs@example.com"
    mock_tenant.email_inbox_password = "encrypted-secret"
    mock_tenant.email_inbox_port = 993

    with (
        patch("app.tasks.screener_tasks.AsyncSessionLocal") as MockSession,
        patch("app.tasks.screener_tasks._fetch_imap_emails", return_value=[raw_email]),
        patch("app.tasks.screener_tasks.screen_resume") as MockScreen,
    ):
        tenants_result = MagicMock()
        tenants_result.scalars.return_value.all.return_value = [mock_tenant]
        db_tenants = make_db_mock()
        db_tenants.execute = AsyncMock(return_value=tenants_result)

        # _find_duplicate returns an existing application
        db_process = _make_db_with_returns(mock_job, mock_application)

        class Ctx:
            def __init__(self, db):
                self._db = db

            async def __aenter__(self):
                return self._db

            async def __aexit__(self, *args):
                pass

        session_instances = [Ctx(db_tenants), Ctx(db_process)]
        idx = [0]

        def factory():
            i = min(idx[0], len(session_instances) - 1)
            idx[0] += 1
            return session_instances[i]

        MockSession.side_effect = factory

        from app.tasks.screener_tasks import _poll_mailboxes_impl

        await _poll_mailboxes_impl()

    MockScreen.delay.assert_not_called()


# ── Test: helpers ─────────────────────────────────────────────────────────────


def test_extract_job_ref_from_subject():
    from app.tasks.screener_tasks import _extract_job_ref

    assert _extract_job_ref("PYDEV001 – Alice Smith Application") == "PYDEV001"
    assert _extract_job_ref("MI0T4AM3 – John Smith") == "MI0T4AM3"
    assert _extract_job_ref("No ref here at all") is None


def test_cosine_similarity_identical_vectors():
    from app.tasks.screener_tasks import _cosine_similarity

    v = [1.0] * 10
    assert abs(_cosine_similarity(v, v) - 1.0) < 1e-5


def test_cosine_similarity_orthogonal_vectors():
    from app.tasks.screener_tasks import _cosine_similarity

    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(_cosine_similarity(a, b)) < 1e-5


def test_cosine_similarity_zero_vector():
    from app.tasks.screener_tasks import _cosine_similarity

    assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_build_transcript_from_full_conversation():
    from app.tasks.screener_tasks import _build_transcript

    test_answers = {
        "full_conversation": [
            {"role": "examiner", "content": "Tell me about Python."},
            {"role": "candidate", "content": "I have 5 years of Python experience."},
        ]
    }
    transcript = _build_transcript(test_answers)
    assert "Examiner: Tell me about Python." in transcript
    assert "Candidate: I have 5 years" in transcript


def test_build_transcript_falls_back_to_answers():
    from app.tasks.screener_tasks import _build_transcript

    test_answers = {
        "full_conversation": [],
        "answers": [{"question": "Q1?", "answer": "My answer."}],
    }
    transcript = _build_transcript(test_answers)
    assert "Q1?" in transcript
    assert "My answer." in transcript


def test_extract_text_pdf():
    """Test PDF text extraction with minimal fake PDF (pdfplumber should handle gracefully)."""
    from app.tasks.screener_tasks import _extract_text

    # Can't easily create a real PDF in-memory, just verify it doesn't crash
    result = _extract_text(b"not a real pdf", "pdf")
    assert isinstance(result, str)


def test_extract_text_unknown_ext():
    from app.tasks.screener_tasks import _extract_text

    result = _extract_text(b"some data", "txt")
    assert result == ""


def test_parse_raw_email_extracts_fields():
    """_parse_raw_email correctly extracts subject, sender, and attachment."""
    from app.tasks.screener_tasks import _parse_raw_email

    msg = MIMEMultipart()
    msg["Subject"] = "PYDEV001 – Alice Smith"
    msg["From"] = "Alice Smith <alice@example.com>"
    msg["Message-ID"] = "<abc123@example.com>"

    body = MIMEText("Please find my resume attached.", "plain")
    msg.attach(body)

    pdf_attach = MIMEApplication(b"%PDF-1.4 test", _subtype="pdf")
    pdf_attach.add_header("Content-Disposition", "attachment", filename="resume.pdf")
    msg.attach(pdf_attach)

    result = _parse_raw_email(msg.as_bytes())

    assert result is not None
    assert result["sender_email"] == "alice@example.com"
    assert result["sender_name"] == "Alice Smith"
    assert result["attachment_ext"] == "pdf"
    assert result["attachment_bytes"] is not None
    assert "PYDEV001" in result["subject"]
