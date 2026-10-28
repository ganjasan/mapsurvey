## 1. Data model

- [x] 1.1 Add `CommentThread`, `Comment`, `CommentAttachment` to `survey/models.py` (choices, `comment_attachment_key`, `_private_media_storage`, indexes, `CheckConstraint commentthread_one_anchor_only`, `Comment.deleted_at` soft delete)
- [x] 1.2 `python manage.py makemigrations survey -n comment_threads` → `0081_comment_threads.py`; confirm `origin/master` has no newer migration before committing
- [x] 1.3 Register the three models read-only in `survey/admin.py`

## 2. Service layer — `survey/comments.py`

- [x] 2.1 `Anchor` dataclass + `resolve_anchor(thread)` for the four kinds (label, deep link, badge key, exists) resolving codes against `canonical_of(thread.survey)`
- [x] 2.2 `anchor_from_request(survey, kind, key)` — turns a posted `question_id`/`section_id`/`session_id`/`block_id` into stored fields, validating the object belongs to the survey family
- [x] 2.3 `open_thread`, `reply`, `resolve`, `reopen`, `delete_comment` (soft delete + storage cleanup), `attach` — all under `transaction.atomic`, thread `survey` always `canonical_of()`
- [x] 2.4 `open_counts(survey)` (one grouped query, section = own + inside) and `badge_count(survey, kind, key)`
- [x] 2.5 `participants_of(thread)` and `mentionable_members(survey)` (org memberships)
- [x] 2.6 `validate_attachment(file)` — 15 MB cap, MIME allow-list

## 3. Mail

- [x] 3.1 `SITE_URL` in `mapsurvey/settings.py` defaulting to `NEWSLETTER_SITE_URL`; add to web + worker in `render.yaml`; `.env.example`
- [x] 3.2 `survey/mail.py`: `send_templated_mail`, `absolute_url`
- [x] 3.3 `survey/tasks.py`: `send_thread_notification(thread_id, comment_id, actor_id, recipient_id)` with `max_retries=3`, `fail_silently=False`
- [x] 3.4 Templates `survey/templates/comments/notify.txt` / `.html` (actor, anchor label, survey, body, attachment names, one button)
- [x] 3.5 `comments.notify(thread, comment, actor)` enqueues per recipient inside `transaction.on_commit`

## 4. Views and URLs — `survey/comment_views.py`

- [x] 4.1 `threads_panel` GET (`anchor=`, `thread=`, `status=`) rendering the drawer partial; `thread_counts` GET JSON (the mention list ships inside the panel as `json_script`)
- [x] 4.2 `thread_create`, `comment_reply` (multipart with files), `thread_resolve`, `thread_reopen`, `comment_delete` (author-or-owner), `attachment_download` (gated, redirect to signed URL or `FileResponse`)
- [x] 4.3 URL block `editor/surveys/<uuid:survey_uuid>/comments/...` in `survey/urls.py`
- [x] 4.4 Mutating responses set `HX-Trigger: threadCountsChanged` and return the changed fragment
- [x] 4.5 PostHog: `COMMENT_THREAD_OPENED`, `COMMENT_REPLY_POSTED`, `COMMENT_THREAD_RESOLVED` in `product_events.py`, emitted from the views

## 5. Editor integration

- [x] 5.1 `partials/_comments_drawer.html` (shell + filters + composer), `_comment_thread_list.html`, `_comment_thread.html`, `_comment_badge.html`; include the drawer once in `editor_base.html`
- [x] 5.2 Template filter `thread_count` in `survey/templatetags/comment_utils.py`; badge in `section_list_item.html`, `question_list_item.html`, `pr_block_list_item.html` with `data-thread-badge="<kind>:<key>"`
- [x] 5.3 Pass `thread_counts` from every row-rendering site: `editor_survey_detail`, `editor_section_detail`, question create/edit/duplicate/paste/delete OOB, section create/duplicate/paste, `public_results_config`, block add/edit
- [x] 5.4 Toolbar button `Comments · N` in `survey_detail.html` (both read-only and editable bars) and `public_results.html`; header button in `question_form_modal.html`
- [x] 5.5 Inline thread under Tags & Notes in `analytics_session_detail.html` (serves the v1 modal and the v2 drawer)
- [x] 5.8 `?session=<id>#thread-<id>` on Responses opens the session detail and scrolls to the inline thread (the email deep link for a response thread)
- [x] 5.9 Badge on every row of Latest responses (`analytics_overview_pane.html`, counts from `analytics_dashboard`); a click opens the response and scrolls to its thread. The map identify popup stays without a badge until a client asks (owner request 2026-09-15)
- [x] 5.6 `survey/assets/js/comments_drawer.js`: open/close, z-index above modal, Esc closes drawer first, `#thread-<id>` routing after section/block-from-hash, `threadCountsChanged` → fetch counts → patch badges; CSS in a new `css/comments.css` linked from `editor_base.html` — the editor does not load `main.css` (+ full width under the mobile breakpoint); `collectstatic`
- [x] 5.10 Drawer width is draggable on the left edge (grip pill + col-resize cursor, indigo on hover/drag), 320px to 80vw, remembered in `localStorage['cmDrawerWidth']`, double-click resets, arrow keys nudge; hidden on phones (owner request 2026-09-15)
- [x] 5.7 Composer: textarea, `@` autocomplete from the members JSON embedded in the panel, attach button with pending list, mentions posted as ids

## 6. Tests (`survey/tests.py`, GIVEN/WHEN/THEN)

- [x] 6.1 `CommentThreadModelTest`: CheckConstraint, soft delete, attachment key on private storage
- [x] 6.2 `CommentThreadVersioningTest`: thread from a draft resolves after publish; deleted question → "no longer in the survey"
- [x] 6.3 `CommentThreadEditorTest`: permissions matrix (viewer/editor/owner/outsider) for open, reply, resolve, reopen, delete own, delete any; HTML in body escaped; mention list = org members
- [x] 6.4 `CommentBadgeTest`: counts (own + inside), badge present in the response of every row-rendering endpoint, counts JSON after resolve
- [x] 6.5 `CommentNotificationTest` (`captureOnCommitCallbacks`, `mail.outbox`): reply → author, mention → mentioned, earlier mention keeps receiving, never the actor; subject and deep link
- [x] 6.6 `CommentAttachmentTest`: upload, gated download for member vs outsider, size and type rejection, storage cleanup on delete
- [x] 6.7 `CommentDeepLinkTest`: `?thread=` renders the drawer expanded on that thread; anchor URLs per kind
- [x] 6.8 `./run_tests.sh survey` green — 2032 tests, OK (skipped=1), 2026-09-15

## 7. Manual verification and ship

- [x] 7.1 Browser click-through on the worktree dev server (curl login → cookie): drawer from toolbar, badge, modal header; Esc order; mobile 390px; session drawer; public results
- [ ] 7.2 `makemessages` for new creator-facing strings — NOT run here: on 2026-09-15 `makemessages -l ru` produced +612/-148 msgids of unrelated drift (the catalog has not been regenerated for several changes), a 4,500-line diff that does not belong in this PR. The strings are `{% trans %}`-wrapped and will be picked up by the next catalog sync (change `creator-ui-localization`). `TranslationCatalogHygieneTest` only checks msgstr collisions and is unaffected.
- [x] 7.3 Update `CLAUDE.md` (comment threads section: anchoring rule, drawer mount, mail helper) and the backlog item status
- [ ] 7.4 PR to `master`; verify on the Render preview with a real email to a second account; `SITE_URL` set on web + worker

## 8. UX audit follow-ups (owner: "do everything", 2026-09-15)

- [x] 8.1 Accessibility: aria-labels on close/delete/edit/mention/toolbar buttons and badges; badges are real buttons (ghost shows on focus); textarea labelled; focus moves to the panel title on open and back to the opener on close; `aria-live` region announces post/reply/resolve/reopen/delete/edit; resize handle carries `aria-valuenow/min/max`; filters use `aria-pressed`; reply toggle `aria-expanded`
- [x] 8.2 Contrast: hint and icons `#6b7280` (4.8:1), Resolve `#047857` on `#ecfdf5` (4.9:1); nothing text-sized in `#9ca3af`
- [x] 8.3 New since you last looked: `CommentSeen` per (member, survey), migration `0082`; threads marked and sorted first, "N new" pill, red dot on row badges and the toolbar count, `new`/`new_total` in the counts JSON; opening the drawer marks seen
- [x] 8.4 Edit own comment in place (`edited_at`, "edited" mark, no re-notification, author only, `editor_comment_edit`)
- [x] 8.5 Sending state: `hx-disabled-elt` + "Sending…" label; server errors shown inline under the textarea (`[data-cm-error]`, `role=alert`) instead of `alert()`, typed text kept
- [x] 8.6 Attachments: size/type checked on `change` before upload, oversized files flagged and dropped from the input, × removes a pending file; image previews `loading=lazy` with fixed size
- [x] 8.7 Response anchor labelled with the Responses ordinal (`comments.session_seq`), not the database id
- [x] 8.8 Touch targets 44px under `pointer: coarse`; text sizes ≥ .75rem, comment body .9rem/1.5 capped at 70ch; ⌘/Ctrl+Enter shown in the send button title; shorter hint on reply forms
- [x] 8.10 Dashboard: every survey card shows `💬 N` open comments and `· M new` in red when there is unseen activity (`comments.unseen_by_survey`, two queries for the whole list); links to the survey editor (owner request 2026-09-15)
- [x] 8.11 General threads: the survey itself is the fifth anchor (`anchor_kind=survey`, migration `0083` widens the constraint); the whole-survey drawer view has a composer for it and lists these threads first (owner request 2026-09-15)
- [ ] 8.9 Deferred: server-side image thumbnails for attachments (previews still load the original, lazily)
