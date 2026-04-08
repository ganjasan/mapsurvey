## 1. Celery + Redis Infrastructure

- [x] 1.1 Add `celery[redis]` to `Pipfile`
- [x] 1.2 Create `mapsurvey/celery.py` — standard Celery app bootstrap with `autodiscover_tasks()`
- [x] 1.3 Update `mapsurvey/__init__.py` — expose `celery_app`
- [x] 1.4 Add `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `CELERY_TASK_ALWAYS_EAGER` to `mapsurvey/settings.py`
- [x] 1.5 Add `NEWSLETTER_PHYSICAL_ADDRESS` and `NEWSLETTER_SITE_URL` to `mapsurvey/settings.py`
- [x] 1.6 Add `redis` and `celery` worker services to `docker-compose.yml`

## 2. Newsletter App Skeleton

- [x] 2.1 Create `newsletter/` directory with `__init__.py` and `apps.py`
- [x] 2.2 Add `'newsletter'` to `INSTALLED_APPS` in settings
- [x] 2.3 Create `newsletter/models.py` — `Campaign`, `NewsletterPreference`, `CampaignRecipient`, `BounceRecord`
- [x] 2.4 Run `makemigrations newsletter` to generate `0001_initial.py`
- [x] 2.5 Create `newsletter/urls.py` with `app_name = 'newsletter'`
- [x] 2.6 Wire into `mapsurvey/urls.py` at `path('nl/', include(...))`

## 3. Email Rendering

- [x] 3.1 Create `newsletter/email_renderer.py` — `render_campaign_email()` function returning `EmailMessage` with `List-Unsubscribe` headers
- [x] 3.2 Create `newsletter/templates/newsletter/email_base.html` — brand HTML table shell with footer (physical address, unsubscribe link, tracking pixel)
- [x] 3.3 Create `newsletter/templates/newsletter/email_campaign.html` — extends `email_base.html`, renders `{{ body_html|safe }}`

## 4. Celery Task

- [x] 4.1 Create `newsletter/tasks.py` — `send_campaign_chunk` task with cursor-based chunking, SMTP connection reuse, per-recipient error handling
- [x] 4.2 Idempotency: use `CampaignRecipient` unique constraint `(campaign, user)` + `update_or_create` to handle already-sent recipients

## 5. Public Views

- [x] 5.1 Create `newsletter/views.py` — `unsubscribe_confirm` (GET: show form, POST: set unsubscribed), `unsubscribe_one_click` (POST-only, RFC 8058), `track_open` (GET: return 1x1 GIF, update `opened_at`)
- [x] 5.2 Add URL patterns to `newsletter/urls.py`: unsubscribe, one-click, track pixel
- [x] 5.3 Create `newsletter/templates/newsletter/unsubscribe_confirm.html` — confirmation page with button
- [x] 5.4 Create `newsletter/templates/newsletter/unsubscribe_done.html` — post-unsubscribe message

## 6. Admin

- [x] 6.1 Create `newsletter/admin.py` — `CampaignAdmin` with `list_display`, `list_filter`, `readonly_fields`, custom `get_urls()` for preview/test-send/send
- [x] 6.2 Add `CampaignRecipientInline` (read-only) to `CampaignAdmin`
- [x] 6.3 Add `NewsletterPreferenceAdmin` and `CampaignRecipientAdmin` (read-only list views)
- [x] 6.4 Create `newsletter/forms.py` — `TestSendForm` with single `EmailField`
- [x] 6.5 Create `newsletter/templates/newsletter/admin/campaign_change_form.html` — extends `admin/change_form.html`, adds Quill.js editor, preview modal, test-send modal, "Send to all" button with confirm dialog

## 7. Tests

- [x] 7.1 Create `newsletter/tests.py` with `CELERY_TASK_ALWAYS_EAGER=True` and `locmem.EmailBackend` overrides
- [x] 7.2 Test Campaign model: creation, status transitions, `get_recipient_queryset()` excludes unsubscribed users
- [x] 7.3 Test `send_campaign_chunk`: sends to active users, skips unsubscribed, logs SMTP failures, updates cursor, marks campaign sent
- [x] 7.4 Test crash recovery: partially-sent campaign re-run does not create duplicate `CampaignRecipient` rows
- [x] 7.5 Test unsubscribe flow: GET shows confirmation, POST sets `is_unsubscribed=True`
- [x] 7.6 Test RFC 8058 one-click: POST with correct body unsubscribes, GET returns 405
- [x] 7.7 Test open tracking: pixel request sets `opened_at`, returns `image/gif`, second request is idempotent
- [x] 7.8 Test email rendering: `List-Unsubscribe` header present, physical address in body, pixel img in body

## 8. Epic: Bounce Parsing (deferred)

- [ ] 8.1 Design bounce email parsing pipeline (management command or webhook)
- [ ] 8.2 Implement `BounceRecord` population from incoming bounce emails
- [ ] 8.3 Auto-mark users as bounced after N hard bounces, exclude from future sends
