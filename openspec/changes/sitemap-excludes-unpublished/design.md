## Context

`sitemap_xml` and the landing page `index` both decide "which surveys may an anonymous
visitor see". They were written at different times and never reconciled. The landing page
carries the correct filter; the sitemap carries `visibility` and nothing else.

The divergence stayed invisible because nothing reads a sitemap in review and nothing tested
its contents beyond "does it mention `/for-educators/`". It surfaced only once PostHog error
tracking shipped (2026-08-15) and the resulting `Http404` events were traced back through
Render request logs to their user agents.

This change is the follow-up that `tenant-data-exposure` explicitly deferred. That change
removed the public `/surveys/` listing, which exposed every organization's surveys directly.
Its proposal recorded the sitemap and the error-tracking noise as out of scope, "same
investigation, separate change" — this is that change, minus the error-tracking half, which
is a defect in the reporter rather than in what we publish.

Prior art in this repo for the shape of the fix: `SEO_LANDINGS` in `survey/seo_landings.py`
exists precisely so a landing page "can't have a route yet silently miss the sitemap". The
same single-source reasoning applies to surveys, and was never extended to them.

## Goals / Non-Goals

**Goals:**
- The sitemap lists only survey URLs that return a survey to an anonymous visitor.
- Unpublished surveys are not indexable even when the sitemap never mentioned them, because
  external links reach them anyway.
- A person who arrives at an unavailable survey reads a sentence instead of a blank 404.
- One queryset expresses "publicly visible survey", so the next consumer cannot drift.

**Non-Goals:**
- Changing `check_survey_access`'s decisions. Which statuses are reachable, and link-based
  access to an unlisted survey, stay exactly as they are. Only the shape of the `draft`
  response changes.
- Reworking `visibility` semantics, versioning, or `published_version`.
- De-indexing what Google and Bing already hold. A 404 plus `noindex` is the mechanism;
  waiting for a recrawl is the timeline. No URL removal requests.
- `Http404` reaching PostHog error tracking. Separate change; see the backlog.
- Telling creators their draft link is circulating. That is outreach, not code.

## Decisions

**One helper, called by both, rather than a second correct copy.**

```python
def publicly_visible_surveys():
    """Surveys an anonymous visitor may be shown or sent to.

    The landing page and the sitemap are the only two places that make this
    decision, and when they made it separately they diverged: the sitemap
    filtered on `visibility` alone and advertised 61 drafts as crawlable URLs.
    """
    return (
        SurveyHeader.objects
        .filter(
            visibility__in=['demo', 'public'],
            is_canonical=True,
            published_version__isnull=True,
            deleted_at__isnull=True,
        )
        .exclude(status='draft')
    )
```

The sitemap then adds `.filter(status='published')`. The two consumers legitimately differ
here and the difference is worth stating: the landing page *shows* closed and archived
surveys, with an "archived" ordering and a closed notice, because a person browsing may
reasonably want to see that a survey existed. A search engine should not hold a URL whose
only content is "this survey is closed" — it is a dead end from a search result, and 41 of
the current 140 entries are exactly that, 36 of them duplicates of a canonical survey via
non-canonical version headers.

Rejected: making the sitemap call `index`'s queryset verbatim and accepting the closed
entries. It keeps one query but indexes 44 dead ends, trading one defect for a smaller one.

Rejected: a `SurveyHeader.objects` custom manager method. The filter is a policy about
anonymous visitors, not an intrinsic property of the model, and two call sites do not justify
moving it onto the model where the editor's own queries would sit next to it and invite
accidental use.

**`noindex` as a header, not a meta tag.**

`X-Robots-Tag: noindex` is set on the response in `check_survey_access`, next to the decision
that produced it, rather than as a `<meta>` in a template. Three reasons: the `draft` response
has no template today, and the redirect responses for password-gated surveys never render one
either; a header survives the redirect chain that `survey_header` performs for multilingual
surveys and start sections; and a template tag would have to be added to every survey base
template, which is the same failure mode `POSTHOG_EXCLUDED_PREFIXES` was written to avoid —
a new base template inheriting whatever its author happened to copy.

**The unavailable page names nothing.**

`tenant-data-exposure` established that a denial must not confirm whether a UUID names a real
survey; that is the fact the removed listing used to hand out. An "this survey is not yet
published" page would re-establish it. So the page is generic — the same body for a draft, a
purged survey, and a random UUID — and lists the possibilities without saying which applies:

> This survey isn't available. It may not be published yet, or it may have been closed or
> removed. If you have a link from an organizer, check with them.

This costs a little clarity for the honest visitor and keeps the enumeration guarantee. It
also means one template covers the existing bare-`Http404` paths in `resolve_survey`, which
today return Django's default 404 page.

**Status stays 404.**

Serving the explanation as `200` would be the easy version and would defeat the change: the
URL would remain indexable and the sitemap fix would be the only thing standing between a
draft and Google. `render(..., status=404)` gives a body and a correct status.

## Risks / Trade-offs

- **The sitemap drops from 140 URLs to 32.** That is a 77% reduction and it will look like a
  regression in Search Console's "discovered pages" for weeks. It is the point: 108 of those
  URLs were 404s, duplicates, or dead ends. Coverage errors should fall in the same window.
  Worth noting before someone reads the graph as damage.
- **`published` is stricter than "reachable".** A `testing` survey with no password is open to
  anyone with the link, and 3 `demo`-visibility ones are in the sitemap today. They leave it.
  Testing surveys are a pre-publication state; indexing them was never intended.
- **A creator who publishes gains a URL the sitemap did not previously lose.** Nothing about
  publication triggers a sitemap regeneration — the sitemap is computed per request, so this
  is a non-issue, but it is worth recording that the fix depends on that.
- **`noindex` on non-published surveys is a behaviour change for password-gated ones.** A
  `testing` or `published` survey behind a password gate redirects to the gate; the gate
  itself should not be indexed either. The header follows the survey's status, so a published
  password-gated survey stays indexable while its gate page is what a crawler would actually
  reach. Acceptable: the gate carries no content worth de-indexing separately, and narrowing
  the rule further adds a branch for no gain.

## Migration Plan

No migration. The change is live at the next deploy and takes effect on the next crawl.

Search engines will drop the 61 draft URLs on recrawl, which for AhrefsBot and bingbot at the
observed rate is days, and for Google is governed by its own schedule. No removal requests: a
404 plus `noindex` is the documented mechanism and these URLs carry no traffic worth
expediting.

Verification after deploy is task 4.1: fetch the live sitemap, assert every `/surveys/<uuid>/`
entry it contains returns `200`, and assert the count matches the `published` count in the
database.

## Open Questions

- Should `closed` surveys keep a public page at all, or 410? Out of scope here — they are
  removed from the sitemap either way, and a `410` is a decision about creators' expired links
  rather than about indexing.
