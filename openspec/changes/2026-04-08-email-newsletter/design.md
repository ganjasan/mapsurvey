## Context

Mapsurvey has ~50 registered users and needs admin-driven email campaigns. The platform already sends transactional emails (registration activation, org invitations) via Django's `send_mail` with SMTP. The user has their own mail server. Newsletter is a platform-level service, not per-organization.

Existing email patterns: `AsyncEmailRegistrationView` uses `threading.Thread` for fire-and-forget; `org_send_invitation` uses synchronous `send_mail` with `fail_silently=True`. Both use `text_body` + `html_body` via `render_to_string`.

The project has a single `survey` app but uses module-level file separation (`editor_views.py`, `analytics_views.py`, `org_views.py`, `share_views.py`). Newsletter is a separate domain — a new Django app is appropriate.

## Goals / Non-Goals

**Goals:**
- Admin can create, preview, test-send, and send email campaigns to all active users
- Users can one-click unsubscribe via link in every email
- Open tracking via invisible pixel
- SMTP errors logged per-recipient
- Crash-recoverable chunk-based sending
- Introduce Celery + Redis infrastructure for background tasks

**Non-Goals:**
- Click tracking (UTM + TrackedLink already cover survey links)
- Scheduling campaigns for future delivery (admin triggers manually)
- Segmentation or audience targeting (send to all active, non-unsubscribed users)
- Bounce email parsing (model stub only, implementation deferred)
- Multi-language email content (English only)

## Decisions

### 1. Separate `newsletter` Django app, not inside `survey`

Newsletter introduces Celery (import-time dependency on Redis), has its own admin UX, own public endpoints, and zero domain overlap with surveys. Isolating it prevents Celery imports from breaking the survey app in environments without Redis, and keeps the 628-line `survey/models.py` from growing further.

**Alternative considered**: Adding models to `survey/newsletter_models.py` with re-export. Rejected — couples unrelated domains, shared migration timeline.

### 2. Quill.js via CDN, not django-ckeditor package

Quill is lightweight (~40KB), renders clean HTML, and requires no pip dependency. It's loaded in the admin change form template via CDN, synced to a hidden textarea. CKEditor adds a heavy pip package with its own static file management.

**Alternative considered**: `django-ckeditor`. Rejected — unnecessary dependency for an admin-only use case.

### 3. Chunk-based Celery task with cursor for crash recovery

The `send_campaign_chunk` task processes N users (default 50), updates a `cursor_user_id` on the Campaign, then re-queues itself if more users remain. On crash, re-triggering the task resumes from the cursor. `CampaignRecipient` unique constraint `(campaign, user)` prevents duplicate sends.

**Alternative considered**: Single task iterating all recipients. Rejected — no crash recovery, blocks the Celery worker for the entire send duration.

### 4. `NewsletterPreference` model, not a field on User

Adding fields to Django's auth.User requires either a custom user model (breaking change) or monkey-patching. A separate one-to-one model is clean, created lazily via `get_or_create` at send time.

**Alternative considered**: Custom user model with `is_subscribed` field. Rejected — massive migration effort for one boolean.

### 5. Open tracking via CampaignRecipient, not separate TrackingEvent model

Each `CampaignRecipient` stores `opened_at`. The first pixel load sets it; subsequent loads are ignored. This avoids a separate event table and keeps queries simple.

**Alternative considered**: Separate `OpenEvent` model logging every pixel hit. Rejected — over-engineering for current scale; one open timestamp per recipient is sufficient.

### 6. RFC 8058 one-click unsubscribe

Two endpoints: GET `/nl/unsubscribe/<token>/` shows confirmation page; POST `/nl/unsubscribe/<token>/one-click/` handles machine-initiated one-click (RFC 8058). `List-Unsubscribe` and `List-Unsubscribe-Post` headers are set on every outgoing email. Gmail and other providers surface the unsubscribe button when these headers are present.

### 7. Physical address in email footer

CAN-SPAM requires a physical mailing address. Stored in `settings.NEWSLETTER_PHYSICAL_ADDRESS`, rendered in the email base template footer. Default: "Kyrgyzstan, Bishkek, 11 mkr., d. 14, kv. 53, 720049".

### 8. `NEWSLETTER_SITE_URL` for absolute URLs in Celery tasks

`request.build_absolute_uri()` is not available inside Celery tasks. A `NEWSLETTER_SITE_URL` setting (default `https://mapsurvey.org`) is used to construct absolute unsubscribe and pixel URLs.

## Risks / Trade-offs

- **Quill CDN dependency** → Admin page won't load Quill if CDN is down. Acceptable — admin is internal, and fallback is raw textarea editing.
- **No retry for failed recipients** → A separate `retry_failed` management command can be added later. Current scope logs the error for manual review.
- **Reserved URL prefix `/nl/`** → Minimal collision risk. Short, memorable, doesn't conflict with existing routes.
- **Redis as single point of failure for sending** → If Redis is down, Celery tasks queue locally and retry on reconnect. Campaign status stays `sending` until the worker processes it.
