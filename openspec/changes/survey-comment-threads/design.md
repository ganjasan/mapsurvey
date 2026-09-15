## Context

Creators and the people helping them (us, a client's leadership, a consultancy's
municipality) discuss a survey over email today. The editor has no place to attach a remark
to the object it is about. Three facts in the codebase shape the design:

- **Publishing reshuffles rows.** `versioning.publish_draft()` moves the canonical survey's
  `SurveySection`/`Question` rows onto a new archived `SurveyHeader` and moves the draft's
  freshly cloned rows (same `code`, new ids) onto the canonical header. A thread holding an FK
  to `Question.id` would point at an archived row after the next publish and vanish from the
  editor. `SurveyMapLayer.source_question_code` + `layers.source_question_for()` already solve
  this by storing a code against the canonical survey; `canonical_of()` normalises any
  version or draft to the canonical header.
- **The editor is HTMX + server partials.** Section and question rows are rendered by
  `section_list_item.html` / `question_list_item.html` from about ten call sites in
  `editor_views.py` (create, edit, duplicate, paste, delete OOB swaps). JSON + client rendering
  exists only where there is real client state (the layer-object editor).
- **Two media tiers.** `LayerObjectAsset` is public (respondents load it anonymously);
  respondent `Upload` uses `_private_media_storage` (signed URLs, `querystring_auth`).
  Comment attachments are workspace-internal and belong on the private tier.

Decisions taken with the owner on 2026-09-15: all four anchors in v1; one slide-in drawer
everywhere; every role writes and resolves; plain text + @mentions + attachments; email to
thread participants via Celery; no kill switch; one PR. Mockup on real screens:
`comment-threads.mockup.html`.

## Goals / Non-Goals

**Goals:**
- A thread on a question, section, respondent session or public-results block that survives
  publishing and versioning without a backfill.
- One drawer component mounted once, opened from a toolbar button, a row badge, a modal header
  button, or a `#thread-<id>` deep link.
- Badge counts on every row with one query per page render, kept correct after HTMX swaps.
- Notification email to thread participants, sent by a Celery task, with an absolute deep link
  built without a request.
- Attachments stored privately under random keys, served only through a gated view.

**Non-Goals:**
- Reply-by-email, suggestion mode, an AI agent acting on threads (backlog "Later").
- A per-answer (map feature) anchor; the session is the anchor for responses.
- Read-only guest role (#91): viewers are workspace members today.
- Moving invitation and activation mail onto Celery in this change (the helper is shaped so
  that is a follow-up, not a rewrite).
- Rich text in comments. Bodies are plain text, escaped on render; the Quill/`html_sanitize`
  pipeline is not involved.

## Decisions

### D1. Anchor = canonical survey + code for structure, FK for stable rows
`CommentThread.survey` is always `canonical_of(request.survey)`. Question and section anchors
are `question_code` / `section_code` CharFields resolved against the canonical survey's live
rows at read time; session and block anchors are nullable FKs (`on_delete=CASCADE`) because
those ids never change. A DB `CheckConstraint` (`commentthread_one_anchor_only`) enforces
exactly one anchor matching `anchor_kind`.
*Alternatives:* FK to `Question` (breaks on publish, see Context); `GenericForeignKey`
(contenttypes is used nowhere in this codebase; four explicit columns are indexable and
readable in SQL). Codes are regenerated on duplicate/paste, so threads do not follow a
duplicated survey — accepted, same as reference layers.

### D2. `survey/comments.py` owns anchoring, counting and participants
An `Anchor` dataclass (`kind`, `label`, `deep_link`, `badge_key`, `exists`) and
`resolve_anchor(thread)` are the single place that knows how to turn a stored anchor into a
label, a badge target and an editor URL. `open_counts(survey)` returns
`{'question': {code: n}, 'section': {code: n}, 'session': {id: n}, 'block': {id: n}, 'total': n}`
from one grouped query. `participants_of(thread)` = thread creator + authors of every
comment + every mentioned user across the thread. Write paths (`open_thread`, `reply`,
`resolve`, `reopen`, `delete_comment`, `attach`) live here so a later AI agent posts through
the same function a view does. Permission checks stay in the views.
*Alternative:* inline logic in views (the minimal blueprint) — loses the single resolver a
fifth anchor kind would need.

### D3. Drawer = HTMX partials, mounted once in `editor_base.html`
`<aside id="comments-drawer">` is included once from `editor_base.html` and is off-canvas by
CSS (`transform`), full width under the existing mobile breakpoint. `GET
editor_comment_threads?anchor=<kind>:<key>|thread=<id>|status=open|resolved` returns the whole
panel partial; reply/resolve/reopen/delete POST small fragments back. The drawer sits at
`z-index` above the Bootstrap modal so it opens over "Edit question"; Esc closes the drawer
first (its listener stops propagation while open), and neither closing order touches the
other surface. On Responses the same thread partial is included inline under Tags & Notes in
`analytics_session_detail.html`, which serves both the v1 modal and the v2 drawer.
*Alternative:* JSON API + `comments_drawer.js` rendering (like the layer editor). Rejected:
no client state to justify it, and escaping, mention chips and attachment rendering would be
duplicated client-side. JS is limited to drawer chrome, hash routing and badge refresh.

### D4. Badge counts: one query per page, client refresh after actions
Views that render row partials call `comments.open_counts(canonical)` once and pass the dict
down; a `thread_count` template filter reads it by code/id. Single-row HTMX responses use
`comments.badge_count(canonical, kind, key)` (one indexed COUNT). Section badge = own
threads + threads on questions inside it. After any drawer action the server answers with
`HX-Trigger: threadCountsChanged`; a listener fetches `GET editor_comment_counts` (JSON) and
patches every `[data-thread-badge]` on the page. The refresh endpoint is the safety net for a
row-render site that forgets the context key. A test walks every row-rendering endpoint and
asserts the badge is present.

### D5. Notification = Celery task per recipient through `survey/mail.py`
`mail.send_templated_mail(template_prefix, to, subject, context)` renders `.txt` + `.html`
and calls `send_mail`; `mail.absolute_url(path)` prefixes `settings.SITE_URL`.
`tasks.send_thread_notification(thread_id, comment_id, actor_id, recipient_id)` is one task
per recipient (`max_retries=3`, `fail_silently=False`, so a bad address retries alone and a
permanent failure reaches PostHog through the existing `task_failure` receiver). Views enqueue
inside `transaction.on_commit`. `SITE_URL` defaults to `NEWSLETTER_SITE_URL`'s value;
`NEWSLETTER_SITE_URL` is left in place (six tests and two Render services read it).
*Alternatives:* synchronous `send_mail` in the view (blocks the POST, no retry); background
thread (lost on restart, races `mail.outbox` in tests).

### D6. Attachments on the private tier, gated download view
`CommentAttachment.file` uses `_private_media_storage` and `comment_attachment_key`
(`comment_attachments/<uuid4>.<ext>`). `GET editor_comment_attachment` is decorated with
`survey_permission_required('viewer')` and redirects to the signed URL on S3 or streams the
file locally. Validation: size cap 15 MB, MIME allow-list (images, PDF, office documents,
plain text). Deleting a comment deletes its files from storage.

### D7. Permissions
All endpoints: `survey_permission_required('viewer')`. `comment_delete` additionally allows
only the author or `effective_survey_role == 'owner'`. Mentions autocomplete lists
`Membership.objects.filter(organization=survey.organization)` — org owners/admins without a
`SurveyCollaborator` row are still valid targets. Comments on trashed (soft-deleted) sessions
stay visible; hard-deleting a session cascades its thread.

### D8. Deep links
Email and drawer links: question → `editor_survey_detail?section=<containing id>#thread-<id>`,
section → `editor_survey_detail?section=<id>#thread-<id>`, session →
`editor_survey_analytics?session=<id>#thread-<id>`, block →
`editor_survey_public_results?block=<id>#thread-<id>`. On load `comments_drawer.js` reads the
hash, waits for the section-from-hash flow where one exists, then opens the drawer with
`?thread=<id>`; the server renders it scrolled to and expanded on that thread. Anchors that no
longer resolve (deleted question) render greyed under "No longer in the survey" and still
count in the toolbar total.

### D9. Product events
`product_events.py` gains `COMMENT_THREAD_OPENED`, `COMMENT_REPLY_POSTED`,
`COMMENT_THREAD_RESOLVED`, emitted from the views with `survey_id`, `anchor_kind`,
`organization_id`. These are creator events; nothing about the respondent is sent.

## Risks / Trade-offs

- [Thread created from a draft-copy page stored against the draft header → vanishes at
  publish] → `open_thread` always stores `canonical_of()`; a test creates a thread from a
  draft, publishes, and asserts it still resolves.
- [A row-render call site forgets the counts dict → stale badge until reload] → the
  `threadCountsChanged` refresh plus a test over every row-rendering endpoint.
- [Esc/focus interaction between drawer and Bootstrap modal] → manual click-through on the PR
  preview; the test client cannot see it.
- [`on_commit` never fires under `CELERY_TASK_ALWAYS_EAGER` in tests] → notification tests use
  `self.captureOnCommitCallbacks(execute=True)`.
- [Mention chips parsed from free text on every render] → mentions are stored as M2M at post
  time; render reads the M2M.
- [Large drawer on a survey with hundreds of resolved threads] → the drawer loads
  `status=open` by default; Resolved is a separate fetch.

## Migration Plan

1. Merge → Render deploys web + worker; migration `0081` creates three tables and one M2M
   table, no data migration.
2. Add `SITE_URL` to the web and worker services in `render.yaml` (same value as
   `NEWSLETTER_SITE_URL`); until set, the code falls back to it.
3. `collectstatic` runs in the build as usual.
4. Rollback: revert the PR. Tables stay (harmless); the drawer, badges and task disappear.

## Open Questions

- None blocking. Section badge = own + inside (chosen); composer with nothing focused targets
  the current section; sessions of archived versions keep their threads.
