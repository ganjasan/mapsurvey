## Why

Mapsurvey needs a way to communicate with registered users — announce features, share updates, drive engagement. Currently there is no newsletter or bulk email capability. External services add cost and complexity for what is a straightforward admin-driven email blast to a small user base. Building it in-house gives full control, integrates with existing User model, and introduces Celery infrastructure that benefits future background tasks.

## What Changes

- New `newsletter` Django app with its own models, admin, views, tasks, and templates
- **Campaign model**: subject, HTML body (Quill.js WYSIWYG), status lifecycle (draft→sending→sent→failed), chunk-based sending with crash recovery cursor
- **NewsletterPreference model**: per-user unsubscribe preference with stable UUID token
- **CampaignRecipient model**: per-recipient delivery tracking (sent/failed/opened, SMTP errors)
- **BounceRecord model** (stub): prepared for future bounce email parsing
- **Celery + Redis infrastructure**: `mapsurvey/celery.py`, worker service in docker-compose, Redis service
- **Open tracking**: 1x1 transparent GIF pixel endpoint, records first open timestamp
- **Unsubscribe flow**: one-click GET page + RFC 8058 POST endpoint, List-Unsubscribe header
- **Admin UX**: Quill.js editor, preview, test send, "Send to all" with confirmation, delivery statistics
- **Email template**: brand-consistent HTML email with physical address footer (Kyrgyzstan, Bishkek, 11 mkr., d. 14, kv. 53, 720049)

## Capabilities

### New Capabilities
- `email-newsletter`: Admin-driven email campaigns to registered users with WYSIWYG editor, delivery tracking, open tracking, and one-click unsubscribe
- `celery-infrastructure`: Celery + Redis setup for background task processing

### Modified Capabilities
- None

## Impact

- New Django app: `newsletter/` (models, admin, views, urls, tasks, email_renderer, forms, templates, migrations)
- `mapsurvey/celery.py` — new Celery app bootstrap
- `mapsurvey/__init__.py` — expose celery_app
- `mapsurvey/settings.py` — add `newsletter` to INSTALLED_APPS, Celery settings, newsletter settings
- `mapsurvey/urls.py` — include newsletter URLs at `/nl/`
- `docker-compose.yml` — add redis and celery worker services
- `Pipfile` — add `celery[redis]`
