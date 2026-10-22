## Context

`CROSS_SITE_COOKIES` was on whenever `DEBUG` was off. It set `SameSite=None; Secure` through
Django settings and `PartitionedCookieMiddleware` appended `Partitioned` (CHIPS). Two things the
design did not account for: WKWebView-based in-app browsers on iOS drop the partitioned cookie
outright, and CHIPS keys a cookie by partition, so a browser that already had a plain
`csrftoken` keeps both and sends both. Django's `parse_cookie` keeps the last value; the
editor's JavaScript (`document.cookie.match(/csrftoken=…/)`, ten places) takes the first.

## Goals / Non-Goals

**Goals:** respondents answer from any browser as before 13 October; creators' JavaScript
POSTs work again without clearing cookies; the worker's signed links verify.

**Non-Goals:** rewriting the JavaScript token readers (they are correct once one cookie remains);
a second cookie scheme for embeds; alerting on 403 rates (follow-up in #388).

## Decisions

- **Default off, env opt-in.** `CROSS_SITE_COOKIES` is read from the environment only; nothing
  depends on `DEBUG`. The e2e embed run that sets it to 1 is unaffected.
- **Embeds rely on the carrier.** `EmbedSessionMiddleware` applies exactly when no session
  cookie arrives, which with `SameSite=Lax` is every cross-site frame. Safari and iOS already
  took that path (the docstring records that `Partitioned` never helped there); Chromium and
  Firefox now take it too. The CSRF secret rides in the session on that path.
- **Sweep, do not rename.** Renaming the cookies would log every creator out and restart every
  respondent mid-survey. Instead, when the raw `Cookie` header carries two values for
  `sessionid` or `csrftoken` — the only way a browser shows the duplicate — the middleware
  answers with a deletion of the partitioned variant (`Max-Age=0; Secure; SameSite=None;
  Partitioned`, which is what matches it). A response can carry one `Set-Cookie` per name, so
  the deletion waits for a response that is not itself setting that cookie; Django re-sets the
  plain `csrftoken` on every HTML page with the value it read, so by the time a JSON response
  carries the deletion the two values agree and nothing is lost. Where they still differ (a
  session cycled by login while the stale cookie sat first), the browser is left with the
  plain cookie and the person signs in once more. No request is ever rejected by the sweep.
- **Worker key from the group, not `fromService`.** Render Blueprints reference service
  properties (host, connection strings), not another service's environment variables. The
  worker drops its generated `SECRET_KEY` and inherits the group's; the owner pastes the web
  service's value into `mapsurvey-shared` first. The web service keeps its own value (changing
  it would invalidate every session). The cron signs nothing and keeps its generated key.

## Risks / Trade-offs

- [A creator with a cycled session plus the stale cookie first] → one extra sign-in, documented.
- [Blueprint sync before the group has `SECRET_KEY`] → the worker starts without one and Django
  refuses to boot; the sync is a manual step after the group is set, called out in the PR.
- [Preview workers get the group's key, preview webs their own] → previews never verify
  worker-signed links; they never did.
