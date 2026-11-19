# Creator app UI: support chat, help centre, changelog, comments, ways to start, design tokens, dialogs, mobile

Moved verbatim from `CLAUDE.md` (change `claude-md-diet`). `CLAUDE.md` keeps the one-line rules; this file keeps the detail. Update it in the PR that changes the behaviour.

**Support chat (Chatwoot, change `chatwoot-support-chat`, #291)**: one partial,
`partials/_support_chat.html`, included by the three base templates; config and the signed-in
creator's identity come from `survey.context_processors.support_chat`. The identifier is
`str(user.pk)`, signed with `identifier_hash = HMAC-SHA256(CHATWOOT_HMAC_TOKEN, pk)` on the
server — the token never reaches the browser; empty `CHATWOOT_WEBSITE_TOKEN` = no widget, no
third-party request (tests, local dev, previews without the env group). The creator bases
include it with `editor_bubble=True` (change `onboarding-friction`, #638): the bubble shows on a
desktop and never below 768 px, carries our own "×" that hides it in this browser
(`localStorage['msSupportBubble']`), and "Show chat button" in the "?" menu
(`.support-bubble-restore`, `showSupportBubble`) brings it back. The editor widget never speaks
first, bubble or not: no unread pop-up; the "?" menu in the header (`editor/partials/_help_menu.html`)
and "Help & support" in the ⋯/account menus stay the entry points, and an agent reply lights the
`.support-unread` dot on them. `openSupportChat(event, context)` opens the chat and sends `context` to the agent as
contact custom attributes (workspace, plan, page, survey are sent on every page) — the hook for
help at the point of failure (#295). Chatwoot's own cookies outlive our session, so a page
rendered for a different visitor clears them before the SDK loads; do not use
`$chatwoot.reset()` for that (it reloads the frame without a second `chatwoot:ready`).

**Help centre (`help/`, change `help-site`, #298)**: help.mapsurvey.org is a Starlight (Astro) site
built from `help/` by its own Render static service (`mapsurvey-help`, `buildFilter: help/**`,
automatic PR previews because static sites are free; previews mark every page `noindex`). Sections
follow Diátaxis — `start-here/` (tutorial), `how-to/`, `reference/`, `troubleshooting/`, `learn/`
(citizen engagement as a practice, written from `docs/research/survey-design-rules.md`),
`use-cases/`, `faq.md` — and `help/CONTRIBUTING.md` holds the page shapes and the FAQ rule (a
question is added only when someone asked it; source in a comment). A feature's guide ships in the
feature's PR. **Product → help links go through `survey/help_links.py`** (`HELP_URL.<key>` from the
`help_site` context processor; `HELP_SITE_URL` empty = no links) and `HelpSiteLinksTest` fails when a
registry path has no page under `help/src/content/docs/`, so a renamed page needs a `redirects` entry in
`help/astro.config.mjs` and a registry update in the same commit. The "?" menu's "Help centre" item
and the "Learn more" links (reference layers, embed, export, Pro) are the only entry points; the
help site's "Still stuck?" link is `mapsurvey.org/?support=1`, which opens the chat for a signed-in
creator (`open_on_load` in the support_chat context). `npm run build` in `help/` fails on a broken
internal link (`starlight-links-validator`); the MCP pages are `draft: true` until mcp.mapsurvey.org
is live.

**In-app changelog (change `in-app-changelog`, issue #227)**: "What's new" entries are files in
`survey/changelog/<YYYY-MM-DD>-<slug>.html` — a `---` header (`title`, `kind: new|fixed`,
optional `link` URL name, optional `image` static path) followed by an HTML body, English only,
shipped in the PR of the change they describe (format in `survey/changelog/README.md`; the loader
is `survey/changelog.py`, read once per process). Seen-state is ONE watermark per creator,
`CreatorPreferences.changelog_seen` = the newest id seen; ids start with the date, so "unseen" is a
string comparison. The card (`editor/partials/_whats_new_card.html`, included from
`editor_base.html` AND `base.html`, never from `base_survey_template.html`; the `whats_new`
context processor also returns nothing under `/surveys/` and `/r/`) shows only the latest unseen
entry, once; "Got it" / × / the page / "Don't show these" all move the watermark.
`changelog_cards` off hides the card only — the page `/editor/whats-new/`, the gift icon and the
account-menu item stay. New accounts start seen (`seed_changelog_watermark` in `signals.py`).
`ChangelogEntriesTest.test_shipped_entries_load` parses every file, so a malformed entry fails CI,
not every editor page. The first entry (`2026-10-02-whats-new.html`) announces the cards themselves; #226 (empty sessions hidden by default) writes the next.
**Hero tier (change `changelog-hero`, #423)**: an entry with `tier: hero` (+ `art`/`image`,
`link`+`link_query`, `cta_label`, optional `help`, `chips` with `{survey}`, `show_if`/`note_if`
from the predicate registry `survey/changelog_audience.py`) renders as a full-width banner on the
dashboard (`editor/partials/_whats_new_hero.html`, included from `editor.html` ONLY) instead of
the corner card. A hero is *pending* while unseen, ≤30 days old and in audience; while pending no
corner card renders anywhere (`whats_new.card` is None), a hero never becomes a corner card, and
closing it marks everything seen. Both partials remember the closed id in
`localStorage['msWhatsNewClosed']`, so a close whose POST failed stays closed — the second
"close, close, close" click was the owner's reason for the rule. Budget: two heroes ≥14 days
apart (`test_hero_budget`). Events carry `tier`; `changelog_card_clicked` (`target=cta|help`)
is the interest signal per feature.

**Comment threads (`CommentThread`/`Comment`/`CommentAttachment`, spec `survey-comment-threads`)**:
workspace members discuss a survey where it lives — the survey as a whole, a question, a section, a respondent
session or a public-results block — in ONE slide-in drawer (`editor/partials/_comments_drawer.html`, included
once from `editor_base.html`; `js/comments_drawer.js` + `css/comments.css`). Row badges
(`section_list_item`, `question_list_item`, a report block's toolbar in `reports/editor/_canvas_block.html`) and the toolbar/modal buttons
call `CommentsDrawer.open({anchor: "<kind>:<page id>"})`; the panel is an HTMX partial from
`survey/comment_views.py`. **Anchoring rule**: `thread.survey` is always `canonical_of()`, question
and section anchors are `code`s (never FKs — `publish_draft()` replaces the rows), session and
block anchors are FKs; a `CheckConstraint` enforces exactly one anchor. All of that lives in
`survey/comments.py` (`resolve_anchor`, `anchor_fields`, `open_counts`, `participants_of`, writes);
views only check roles. Every role opens/replies/resolves; delete = author or owner. Bodies are
PLAIN TEXT escaped on render — `coerce_creator_html` does not apply. Attachments sit on the private
media tier under random keys and are served only by `attachment_download`. Badge counts come from
one grouped query per page (`thread_counts` in every row-rendering context; the `thread_count`
filter) and are refreshed client-side on `HX-Trigger: threadCountsChanged`, so a render site that
forgets the context under-counts until the next action, never errors. Notification mail goes to the
thread's participants (creator, authors, everyone mentioned), never the actor, one Celery task per
recipient (`survey/tasks.py`) through `survey/mail.py::send_templated_mail` and `SITE_URL`
(defaults to `NEWSLETTER_SITE_URL`); the same helper is where invitation/activation mail should move.
Deep link: `<editor page>?section|block|session=<id>#thread-<id>`. "New since you last looked" is
`CommentSeen` (one row per member+survey, bumped when the drawer renders): `open_counts(survey,
user)` also returns `new_keys`/`new_total`, which drive the red dot on badges, the toolbar count and
the "N new" pill — so every render site passes `request.user`. Authors edit their own comments in
place (`edited_at`, no re-notification). Response anchors are labelled with the Responses ordinal
(`comments.session_seq`), never the session id.

**Ways to start (change `first-survey-onboarding`)**: a workspace with no surveys and, by default,
"+ New Survey" lead to the START PAGE `/editor/surveys/start/` (`editor_survey_start`) — two cards,
*Survey wizard* / *Start from scratch* — not to the create page. The third card (*Use your AI
assistant*) was removed in change `onboarding-friction` (#638): nothing on the first screen that
does not make a survey; the agent page is reached from the sidebar's *MCP* item, the "?" menu and
the help centre. Before the first survey (`app_nav.onboarding`: no canonical, non-trashed survey in
the active workspace; owner/admin/editor) workspace-level pages open the sidebar as the rail unless
the creator chose Expand (`msSidebar = 'wide'`).
**One click on a card does its action** (change `start-cards-one-click`, #335): the blank card IS
the submit `<button>` of its form, the AI card IS a link to `?from=start`, comes FIRST and is
called the *Survey wizard* with a "Best to start" badge (AI drafts publish ~2.5x as often; the
AI path is the **Wizard** on EVERY creator surface — start card, brief panel, intercept, feedback
strip, generation errors, help — and the only sentence that says what it is ("The Wizard is an AI
agent: …") is the provider disclosure on the create page; labels via `_survey_start_labels()`, the
model's choice label is unchanged; marketing landings still say AI); there is no selection
step, no detail block and no "Always start this way" on the page — creators clicked the card over
and over when a click only selected it. Do not bring a "choose, then confirm" step back.
`CreatorPreferences.survey_start_default` (`''` ask / `blank` / `ai`) is set ONLY on the personal
**Preferences** page `/editor/account/` (`editor_account_preferences`, login only, no org role;
"Preferences" in the account menus of BOTH bases) and is
what the dashboard renders the button from (context processor `survey_start`): `blank` makes it a
POST form to `editor_survey_create_blank`, the one-request empty survey ("Untitled survey", the
creator's UI language, map from the chain below) that shares `_finish_blank_survey` with the create
page's manual action so the two cannot drift. POST, never GET. The create page keeps every old
link; `?from=start` only swaps "Skip and start from scratch" for a way back. **Where a new map
opens is ONE chain**, `survey/map_start.py::suggest_start_position` — `browser` (coordinates the
creator's browser gave: permission already granted, or asked on the click that submits; NEVER on
page load) → `org_survey` (newest positioned survey in the workspace) → `country` (`CF-IPCountry`
from Render's Cloudflare edge, trusted only under `CLOUDFLARE_TRUSTED`; else the `Accept-Language`
region, never `en-US` — the stock-browser default says nothing; `survey/country_centroids.py`) → `world`. The create page's first `setView` and the AI
draft (through the same hidden fields) start there — the Berlin default is gone and must not come
back. `survey_created` carries `surface` (`start_blank` | `create_page`) and `map_source` (the
rung, `creator` when the map was framed, `brief` when the AI task geocoded the brief): names only,
never coordinates. `/editor/account/mcp/` (`editor_account_mcp`) is a redirect to
`/editor/account/connections/` (change `auth-core`), where the MCP block with "Tell me when it's
ready" (`agent_access_requested_at`, the launch list, one event) sits under the tokens until #306
ships — the URL name, the account-menu item "API & connections" in BOTH bases and the "?"-menu
item stay. New creator strings go into all offered catalogs (`TranslationCatalogHygieneTest`
enforces it); the entries are appended by hand like PR #274, not by `makemessages`.

**Design tokens (change `design-tokens`)**: the creator app's colours, text sizes, spacing, radii and
shadows are `survey/assets/css/tokens.css`, loaded by `base.html` and `editor_base.html` right after
Bootstrap — never by the respondent or marketing bases. Two layers: a palette (`--gray-500`,
`--indigo-600`, used only inside that file) and tokens named by purpose (`--color-action`,
`--color-danger`, `--color-text-muted`, `--color-border`, `--surface`, `--radius-control`,
`--radius-card`, `--space-4`, …). The action colour is indigo (owner decision 2026-11-18); teal is the
marketing pages'. The same file sets Bootstrap's buttons, links, badges, alerts, form focus and modals
from the tokens, so plain Bootstrap markup already has the app's look; `btn-secondary` and
`btn-outline-secondary` are both the quiet white button. The editor's (`--accent`, `--border-color`,
`--radius`), the builders' (`.lb --ink/--line/--accent`) and the Pro badge's (`--pro`) variables are
references to the tokens. Tones are written out, not `color-mix()` (old council browsers). **A new
colour is a token, never a literal** (change `tokens-editor-shell`, #742, moved every creator file):
`TokenisedModulesTest` fails when any creator template or stylesheet writes a colour in a CSS
declaration outside `<script>` — only `WITHOUT_TOKENS` (two emails, the group preview iframe, the
public site page, `plan_cards.css`, which the pricing page also draws — app token first, landing name as fallback) render without the tokens and
keep their own; colours inside scripts are data (map palettes, colour inputs, iframe `srcdoc`) and are
not counted. `ColourRatchetTest` still caps every literal per file at
`survey/tests/colour_baseline.json`; after removing some, `python scripts/colour_baseline.py`. To put
foreign CSS onto the tokens, `python scripts/tokenise_colours.py FILE…` maps each colour by its role
where it stands (the same grey is `--color-text-muted` in `color:` and `--color-border-strong` in
`border:`), black shadows to `--shadow-sm|md|lg`, and lists what it does not know. A role the file
lacks is a new purpose token; a picture's colours (`--art-*`, `--brand-*`) and identity colours
(`--type-*`, `--heat-ramp`) are tokens too, so no page writes one. The older names (`--accent`,
`--accent-light`, `--border-color`, `--bg-muted`, `--radius`) live in `tokens.css`; never define
them, or module palettes of literals, in a page's `:root` again. **A new module gets
no look of its own** (owner 2026-11-18: "one consistent design across the app, not a new design per
module"): build it from plain Bootstrap markup and the partials other pages already use, and write a
rule only for what no existing component covers — with tokens.

**One confirmation dialog (change `one-confirm-dialog`)**: every "are you sure?" a creator sees is
`partials/_app_dialog.html` (`#editorDialog`), included by `base.html` and `editor_base.html` and driven
by `js/editor_dialog.js`. From script: `Dialog.confirm(text, {title, note, okLabel, danger})` /
`Dialog.alert()`. From markup: a form with `data-confirm="<title>"` and optional `data-confirm-body`,
`-note`, `-action`, `-tone="primary"` (an action that destroys nothing; default is the red button), or
`hx-confirm`. Never add a browser `confirm()`, a second confirm modal or a confirmation PAGE — there were
five kinds before this change. A modal with choices of its own (group delete, the dashboard's Trash /
Purge) stays a modal of its own.

**Mobile-adaptive layouts (two kill switches)**: `MOBILE_EDITOR_NAV` gives the editor
two-level contextual navigation below 768px: top strip = page tabs, bottom bar = panes of
the active page — Survey and Public results share the Structure/Edit/Preview vocabulary,
Responses gets Overview/Map/Responses/Perf under `RESPONSES_V2` (legacy switch-off:
Table/Map/Charts/Perf) (chrome in `editor/partials/_mobile_nav.html` +
`css/editor-mobile.css` + `js/editor_mobile_nav.js`; double-gated by the
`mobile-nav-enabled` body class AND the media query, so desktop is untouched; the Preview
pane is a full-screen overlay with a back button). `EDITOR_AUTOSAVE` replaces Save/Apply on
question EDIT forms with debounced autosave + a loud saved/saving/error indicator on ALL
viewports (autosave POSTs carry `autosave=1`, validation errors return 422 JSON so the
typed-in form is never re-rendered); new-question forms keep an explicit Create button.
Both default ON since PR #108 (owner decision); setting the env var to
False serves the pre-change layout, which is the rollback story. The RESPONDENT
survey page was deliberately left as-is: a bottom-sheet variant was built, reviewed and
REMOVED (2026-08-23) — the owner kept the legacy panel/crosshair flow; do not reintroduce
a sheet without an explicitly approved respondent-flow mockup. Touch reorder uses
SortableJS `delay:300 + delayOnTouchOnly` (long-press) — do not add ▲▼ reorder buttons.
Leaflet.draw tooltips pick tap-phrased strings via `pointer: coarse`
(`survey/templatetags/i18n_extras.py`).
