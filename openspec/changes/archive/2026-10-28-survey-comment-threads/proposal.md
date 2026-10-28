## Why

A survey is finished by two people who are not in the same room: the client who owns it and
us, sitting inside their workspace. Today that conversation runs over email, and within a week
nobody can say which question "note three" referred to. City of Olney registered on
2026-09-14 and is about to send exactly such notes for the October count; 17 of the 391 prod
workspaces have more than one member and every one of them is a top lead working this way
(backlog #169, epic `team-collaboration`). Comment threads that live on the object they are
about — a question, a section, a respondent's answer, a public-results block — with an email
on every reply are the working surface for the service we already deliver by hand.

## What Changes

- **Comment threads on survey objects.** A workspace member opens a thread on a question, a
  section, a respondent session (the whole response) or a public-results block, replies,
  @mentions other members, attaches images and files, and marks the thread resolved or
  reopens it. Threads belong to the canonical survey and survive publishing: question and
  section anchors are stored by `code` (the same rule reference layers use), session and
  block anchors by FK.
- **One slide-in drawer, everywhere in the editor.** Survey page, question modal and
  public-results config open the same drawer from the right (full width on phones); it lists
  the survey's threads grouped by anchor with Open/Resolved filters and a composer pinned at
  the bottom. Section, question and block rows carry a `💬 N` badge with the open count; the
  toolbar carries a `Comments · N` button. On Responses the thread mounts inside the existing
  session drawer under Tags & Notes. See `comment-threads.mockup.html` (frames on real screens).
- **Email to the people in the thread.** Every new comment emails the thread's participants
  (author, repliers, mentioned members), never the actor, with a deep link that opens the page
  with the drawer on that thread. Sent by a Celery task through a new `send_templated_mail`
  helper and a `SITE_URL` setting; invitations and activation mail can move onto the same
  helper later without a rewrite.
- **Permissions**: every survey role (owner, editor, viewer) may open, reply, resolve, reopen
  and delete their own comment; an owner may delete any comment. Attachments live on the
  private media tier under random keys and are reachable only through a gated view.
- Three PostHog creator events (`comment_thread_opened`, `comment_reply_posted`,
  `comment_thread_resolved`) in the existing `product_events` convention.
- No kill switch (owner decision 2026-09-01); rollback is a revert.

## Capabilities

### New Capabilities
- `survey-comment-threads`: threads anchored to survey objects — data model and anchoring
  across versions, who may do what, the drawer and badges in the editor, attachments,
  deep links.
- `comment-notifications`: participant resolution and the notification email, the Celery
  mail task and the reusable templated-mail helper with `SITE_URL`.

### Modified Capabilities
- `creator-funnel-events`: three new creator-side events are emitted for thread activity
  (added requirement; existing requirements unchanged).

## Impact

- New models `CommentThread`, `Comment`, `CommentAttachment` (migration `0081`), new modules
  `survey/comments.py`, `survey/comment_views.py`, `survey/mail.py`, `survey/tasks.py`,
  new URL block under `editor/surveys/<uuid>/comments/`.
- Editor templates: `editor_base.html` mounts the drawer once; `survey_detail.html`,
  `question_form_modal.html`, `public_results.html` get the toolbar/header button;
  `section_list_item.html`, `question_list_item.html`, `pr_block_list_item.html` get the badge;
  `analytics_session_detail.html` gets the inline thread. Every view that renders those row
  partials passes thread counts (one query per page, refreshed client-side after actions).
- New JS `survey/assets/js/comments_drawer.js` (drawer chrome + `#thread-<id>` deep link);
  `collectstatic` on deploy as usual.
- Settings: `SITE_URL` (defaults to the value of `NEWSLETTER_SITE_URL`); `render.yaml` gets
  the env var on web and worker. The Celery worker already carries the `EMAIL_*` variables.
- PostHog: `product_events.py` gains three constants.
- Tests in `survey/tests.py`: model/anchoring across a publish, permissions matrix, badge
  counts after every row-rendering endpoint, notification recipients, attachment gating,
  deep links.
