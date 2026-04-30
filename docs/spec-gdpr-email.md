# Spec §16–17: GDPR Compliance & Email Templates

*Full spec index: see [spec.md](spec.md)*

---

## 16. GDPR Compliance

### 16.1 Lawful Basis

- **Talent Scout outreach**: legitimate interest. Every outreach email must include unsubscribe link. `opted_out = TRUE` → no further emails.
- **Resume processing**: consent (candidate submits voluntarily). `gdpr_consent_given = TRUE` on Application creation.
- **BrightData profiles**: publicly available data, legitimate interest. Only used for recruitment evaluation.

### 16.2 Data Subject Rights

- **Right to erasure**: `DELETE /candidates/{id}` and `DELETE /applications/{id}` anonymise all PII. Audit trail PII redacted in-place.
- **Right to access**: data export (JSON/CSV) from admin dashboard.
- **Right to rectification**: recruiter can edit candidate data from profile page.

### 16.3 Data Retention

- Default: 12 months after last activity
- Tenant-configurable: 3–36 months
- Celery task flags records at retention limit, notifies tenant admin
- Resumes deleted in sync with Application record erasure

### 16.4 Data Processing Agreement

- Tenants must accept DPA during onboarding before candidate search activates
- `gdpr_dpa_signed_at` stamped on acceptance
- Tenant = data controller, airecruiterz.com = data processor

### 16.5 Technical Measures

- All data in transit: TLS 1.3
- All data at rest: AES-256 (Supabase)
- Tenant API keys: additionally Fernet-encrypted before DB storage
- Audit log for all data access, deletions, exports
- Data residency: EU Supabase region for EU tenants

---

## 17. Email Templates

All HTML, Jinja2 templates, SendGrid delivery. Support EN, DE, ES, FR.

| Template | Description |
|---|---|
| outreach_invite | Hyper-personalised candidate outreach (AI body + Jinja wrapper + unsubscribe link) |
| resume_rejection | Polite rejection after screening fails (AI-generated) |
| test_invitation | Invite to competency test with unique link |
| test_rejection | Polite rejection after test failure (AI-generated) |
| interview_invitation_hm | Hiring manager: candidate summary + Invite to Interview button |
| interview_invitation_candidate | Candidate: interview invitation |
| daily_summary | Hiring manager digest: new candidates + applications |
| welcome | Tenant sign-up welcome with onboarding link |
| payment_failed | Stripe payment failure alert |
| promo_code | Share promo code with prospect |
| data_retention_warning | Alert tenant that data approaching retention limit |
| gdpr_unsubscribe_confirm | Confirm candidate removed from outreach |
