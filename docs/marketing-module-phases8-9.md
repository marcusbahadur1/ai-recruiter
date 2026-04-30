# AI Marketing Module — Phases 8–9: Tenant & Super Admin Frontend

*Full index: [marketing-module.md](marketing-module.md)*

## Phase 8 — Frontend: Tenant Marketing Dashboard

**Claude CLI session prompt:**
```
You are building the tenant-facing Marketing dashboard for AIRecruiterz.
Stack: Next.js 16 TypeScript App Router, Tailwind CSS.
i18n routing: all pages under /[locale]/ — e.g. /en/marketing.
Match the existing sidebar layout, tab navigation component, and design system exactly.
Look at /[locale]/candidates or /[locale]/jobs for the tab+sidebar pattern to copy.
All Phase 7 API routes are available.
```

### Tasks

**8.1 — Sidebar entry & plan gate**
```
Add "Marketing" to the tenant sidebar component.
- Visible only for plans: agency_small, agency_medium, enterprise
- Icon: Megaphone (match existing icon library and size)
- Route: /[locale]/marketing
- trial / recruiter plans: show entry greyed-out with a lock icon
  Tooltip on hover: "Available from Agency Small plan — upgrade to access"
```

**8.2 — Page layout with tabs**
```
Create app/[locale]/marketing/page.tsx

5 tabs: LinkedIn Account | Settings | Content Calendar | Post Queue | Performance

Use the existing tab component. Default tab: "LinkedIn Account".
Support ?tab= query param for deep-linking (e.g. from notification emails).
Fetch tenant plan on load — pass to child components for plan-gated UI sections.
```

**8.3 — LinkedIn Account tab**
```
Create components/marketing/LinkedInAccountTab.tsx

Not connected state:
  Two CTA buttons: "Connect Personal Profile" and "Connect Company Page"
  Each calls POST /api/v1/marketing/accounts/linkedin/connect {account_type}
  then window.location = response.authorization_url

Company page selector page (app/[locale]/marketing/linkedin/select-page/page.tsx):
  Fetch available pages using the ?token= query param.
  Show radio list of company page names.
  "Connect this page" -> POST /api/v1/marketing/accounts/linkedin/select-page
  On success: redirect to /[locale]/marketing?connected=true

Connected state:
  Card per connected account:
    - Badge chip: "Personal Profile" or "Company Page"
    - Account name (bold)
    - Status chip: Active (green) / Expiring Soon (amber, < 7 days) / Expired (red)
    - Token expiry date in locale format
    - "Reconnect" button (if expired/expiring) | "Disconnect" button (confirm dialog)
  "Add account" button if both types not yet connected.

On page load with ?connected=true: show success toast, clean URL.
On page load with ?error=auth_failed: show error banner with "Try again" button.
```

**8.4 — Settings tab**
```
Create components/marketing/SettingsTab.tsx

Form fields (all from Section 25.6 of spec):
  Target audience:         Textarea (placeholder: "e.g. CTOs and HR Directors at Sydney tech companies")
  Agency specialisation:   Text input
  Posting frequency:       Radio group: Daily / Twice a week / Weekly
  Preferred posting time:  Time picker — display in browser local time,
                           store/send as UTC (show "Times are in UTC" note)
  Tone:                    Segmented control: Professional | Conversational | Bold | Educational
  Topics:                  Tag input — user types to add chip, clicks × to remove
  Post types enabled:      Checkbox group, one per type with short description
  Include images:          Toggle — "Attach a Unsplash stock photo to each post"
  Auto-engage:             Toggle
                           If plan doesn't allow: show lock icon + 
                           "Available on Agency Medium and above" label, disable toggle
  Max engagements/day:     Number slider 5–20 (hidden when auto-engage off)
  Content approval:        Toggle — default ON
                           Helper text below: "When on, posts are saved as drafts for 
                           you to review before they go live. Recommended."

On save: PATCH /api/v1/marketing/settings
Show save confirmation toast. Warn "Unsaved changes" if navigating away.
```

**8.5 — Content Calendar tab**
```
Create components/marketing/ContentCalendarTab.tsx

Weekly grid layout:
  7 columns (Mon–Sun), time-slot rows (show slots with posts; collapse empty hours)
  Each post renders as a card at its scheduled_at time slot:
    - post_type badge (colour-coded: thought_leadership=blue, stat=green, etc.)
    - First 60 characters of content
    - Status chip (Draft=amber, Scheduled=blue, Posted=green, Failed=red)
    - Small image thumbnail if post.image_url set

Click card -> open PostDrawer (right-side panel):
  - Full content (editable <textarea> if status in ['draft','scheduled'])
  - Hashtag chips display
  - If image: show preview image with attribution line below:
      "Photo by [photographer_name link] on [Unsplash link]"
      (REQUIRED by Unsplash ToS — must always be shown)
  - "Include image" toggle (per-post) — calls PATCH post with include_image
  - Approve button (if status='draft') -> POST /approve -> update UI optimistically
  - Reject button (if status='draft') -> POST /reject
  - Save button (if content edited)
  - Delete button (confirm dialog)

"Generate Post" floating button:
  Calls POST /api/v1/marketing/posts/generate
  On response: add post to calendar, open drawer in draft state

Week navigation: < Previous | This Week | Next > buttons
```

**8.6 — Post Queue tab**
```
Create components/marketing/PostQueueTab.tsx

Table columns:
  Scheduled | Post Type | Platform | Status | Image | Content Preview | Actions

Filter bar:
  Status dropdown (All / Draft / Scheduled / Posted / Failed)
  Date range picker
  Platform filter (show only if multiple platforms connected)

Row actions:
  draft:     ✓ Approve (green) | ✗ Reject (red)
  scheduled: ✏ Edit (inline textarea + include_image row toggle) | 🗑 Delete
  failed:    ↺ Retry (re-sets status='scheduled') | 🗑 Delete
  posted:    (read-only)

Image column:
  - Thumbnail if image_url set + include_image=True
  - Camera-off icon if include_image=False
  - Click thumbnail: modal with full image + attribution (photographer name + Unsplash link)

Pagination: 20 rows per page with page controls.
```

**8.7 — Performance tab**
```
Create components/marketing/PerformanceTab.tsx

Summary cards row:
  Total Posts This Month | Total Impressions | Avg Engagement Rate | Best Post preview

Line chart — Impressions over time:
  Toggle: 30 days / 90 days / 1 year
  agency_small: show "Upgrade for extended history" overlay on 90-day/1-year tabs
  Use the existing chart library already in the project (recharts or chart.js)

Bar chart — Engagement by post type:
  Grouped bars: impressions + (likes + comments) per post_type

Top Posts table (top 5 by impressions):
  Date | Type | Image thumb | Preview | Impressions | Likes | Comments | Eng. Rate
  Click row -> opens PostDrawer (same component as Calendar tab)

Data: GET /api/v1/marketing/analytics + /analytics/summary
```

---

## Phase 9 — Super Admin Marketing Dashboard

**Claude CLI session prompt:**
```
You are building the Super Admin marketing dashboard at /super-admin/marketing.
Match the existing super admin panel UI patterns in app/super-admin/ exactly.
The platform account always uses a LinkedIn company page.
Reuse the marketing tab components from Phase 8 with an isPlatformAdmin prop 
where needed to scope API calls and show additional controls.
```

### Tasks

**9.1 — Nav + layout**
```
Add "Marketing" to the super admin sidebar.
Create app/super-admin/marketing/page.tsx with 5 tabs:
  Platform Account | Content Calendar | Post Queue | Performance | Settings

Content Calendar, Post Queue, and Performance reuse Phase 8 components 
with isPlatformAdmin=true (scopes to tenant_id=null API calls).
```

**9.2 — Platform Account tab**
```
Top half: Connect the AIRecruiterz LinkedIn company page.
  Same LinkedInAccountTab component, account_type hardcoded to 'company'.
  No "Connect Personal Profile" option here.

Bottom half: Tenant accounts table
  Columns: Tenant Name | Plan | Account Name | Type | Status | Posts This Month | Last Post | Actions
  Actions: "View Posts" (link to post list filtered to that tenant) | "Disconnect" (confirm)
  Sortable columns. Search by tenant name. Paginated 25/page.
```

**9.3 — Settings tab**
```
Reuse SettingsTab component with isPlatformAdmin=true, plus additional fields:
  - requires_approval: toggle (always visible, controls platform default)
  - "Marketing module active" master on/off toggle
    On toggle OFF: confirmation modal —
    "This will pause all platform scheduled posts. Are you sure?"
    Calls POST /api/v1/marketing/toggle {is_active: false/true}
```

**9.4 — Post Queue with approval workflow**
```
Reuse PostQueueTab component with isPlatformAdmin=true, plus:
  - "Pending Approval" banner when draft_count > 0:
    "You have {N} posts waiting for review"  [Review Now] button -> filters to Draft
  - Checkbox per draft row + "Approve Selected ({n})" bulk action button
  - After approve/reject: optimistic row removal + undo toast (5 second window)
    On undo: revert status locally, call reject/un-approve endpoint
```

---
