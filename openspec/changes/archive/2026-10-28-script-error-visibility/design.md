## Context

`window.onerror` receives a sanitised event when the throwing script came from another origin: the
message becomes `Script error.`, the filename and line are blanked, and the stack is empty. The
browser lifts that sanitisation only when both sides agree — the tag says
`crossorigin="anonymous"`, and the response carries an `Access-Control-Allow-Origin` header covering
our origin.

PostHog's exception autocapture sits on top of `window.onerror`, so it inherits the blanking. That
is why the two errors from the first recorded editor session arrived as `Error: "Script error."`
with `handled: false` and nothing else.

Measured before designing (not assumed):

- 26 external `<script>` tags across 8 templates; 6 carry `crossorigin`, 20 do not.
- The missing ones include all three on `editor/analytics_dashboard.html` — the page where the two
  errors fired — and all seven on `editor/editor_base.html`, which every editor page inherits.
- All twelve distinct CDN hosts answer `Access-Control-Allow-Origin: *` when asked with
  `Origin: https://mapsurvey.org`: jsdelivr, unpkg, cdnjs, code.jquery.com, stackpath.bootstrapcdn,
  challenges.cloudflare.com.

That last check is the one that matters for safety, and it had to be done before writing any of
this: `crossorigin="anonymous"` against a host that does *not* send CORS headers makes the browser
refuse the script entirely. The fix would then take down the editor rather than illuminate it.

## Goals / Non-Goals

**Goals:**

- A third-party script that throws tells us what threw, where, and with what stack.
- New external script tags cannot silently reintroduce the blindness.

**Non-Goals:**

- Fixing the two analytics-page errors. We still do not know what they are — that is the point.
- Subresource Integrity. Related, separately risky, separately decided.
- Self-hosting the CDN assets. That would also fix this (same-origin scripts are never sanitised)
  but it is a much larger change with its own trade-offs, and `/trust/` currently describes the CDN
  situation accurately.

## Decisions

### 1. Attribute on every external tag, not only the analytics page

The two known errors are on one page, so the minimal fix is three tags. Rejected: the blindness is
not a property of that page, it is a property of every third-party script we load, and the next
`Script error.` will come from wherever we did not look. 20 tags is a mechanical edit.

`crossorigin="anonymous"` rather than `use-credentials`: we want no cookies sent to CDNs, and
`anonymous` is what a `Access-Control-Allow-Origin: *` response accepts. `use-credentials` against a
wildcard ACAO is a hard failure.

### 2. A test over the template tree, not over rendered pages

The guard walks `survey/templates/**/*.html`, finds `<script src="https://…">`, and asserts each
carries `crossorigin`. A rendering test would only cover the pages a test happens to fetch, and the
templates most likely to acquire a new CDN script are the ones nobody renders in tests.

The failure message names the file and the URL, so the fix is obvious from CI output alone.

Accepted limitation: this checks presence of the attribute, not that the CDN still sends CORS
headers. A host that stops sending them would break the script and no test would catch it. That is
a monitoring concern rather than a test concern — and now, with the attribute in place, it would at
least surface as a real error rather than a blank one.

### 3. Nothing is said on `/trust/`

The page already discloses that third-party scripts load from CDNs in the survey flow. This change
does not add a script, remove one, or send anything new to those hosts — `anonymous` explicitly
means no credentials. There is no new claim to make, and adding one would imply a change that did
not happen.

## Risks / Trade-offs

- **A CDN that does not send CORS headers would break** → All twelve hosts were checked with an
  explicit `Origin` header before this was written. Re-check if a new host is ever added; the test's
  failure message is the natural place to remind whoever adds one.
- **More error detail means more error volume in PostHog** → That is the intent. Two blanked errors
  are worth less than two explained ones, and error tracking already scrubs respondent paths.
- **Third-party stack traces may contain URL fragments** → Same scrubbing as every other exception
  (`_posthog_scrub_tags`), and these are our own creator-facing pages.

## Migration Plan

Mechanical edit, deploy, then wait for the analytics page to throw again — it did so twice in a
two-minute session, so a repeat should not be long. The follow-up is reading the real error and
deciding whether it deserves its own change.

## Open Questions

- **What is actually throwing on the analytics page?** Unanswerable today; that is why this change
  exists. Candidates worth checking first once detail arrives: chart.js against an empty dataset,
  leaflet.heat with no points, leaflet.draw initialising against a map that is not ready.
