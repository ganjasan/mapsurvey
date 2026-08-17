## Why

`sitemap.xml` hands search engines 140 survey URLs. 32 of them work.

`sitemap_xml` (`survey/views.py:1739`) filters on `visibility` alone:

```python
surveys = SurveyHeader.objects.filter(visibility__in=['public', 'demo'])
```

No `status`, no `is_canonical`, no `published_version`, no `deleted_at`. The landing page
at `/` — the other place we decide what the public may see — filters on all five. The two
queries answer the same question and have drifted the whole way apart.

What we currently submit to Google and Bing:

| `status` | Entries | What the URL actually returns |
|---|---|---|
| `draft` | **61** | **hard `404`** — `check_survey_access` raises `Http404` |
| `closed` | 41 | "survey closed" page; 36 of them are non-canonical version headers, i.e. duplicates |
| `published` | 32 | the survey |
| `archived` | 3 | "survey closed" page |
| `testing` | 3 | opens if the creator set no password |

44% of the sitemap is a guaranteed 404. This is not hypothetical crawl-budget theory —
PostHog error tracking caught it happening. Over the two days since error capture shipped,
`survey/access_control.py:21` raised `Http404` 16 times for 15 distinct visitors. Render
request logs name them: bingbot ×7, AhrefsBot ×5, SERankingBacklinksBot ×2 — and one real
person, on Edge, on 2026-08-17 at 02:45, opening `/surveys/0388f301-…/` ("ENVIRONMENT",
`public` + `draft`). Bingbot had crawled that same UUID from our sitemap two days earlier.
A human searched, found a customer's unpublished survey in the index, and hit a blank 404.

The sitemap is only half of it. Seven of the thirteen crawled UUIDs are `visibility=private`
and are not in the sitemap at all — backlink crawlers found them from links elsewhere on the
web, because creators circulate a draft link before publishing. Nothing on those pages tells
a crawler not to index them. One belongs to a named prospect's second survey.

## What Changes

- **One query, two consumers.** Extract the landing page's filter into a single
  `publicly_visible_surveys()` helper in `survey/views.py` and have both the landing page and
  the sitemap call it. The sitemap narrows further to `status='published'`.
- **`X-Robots-Tag: noindex`** on every `/surveys/<slug>/` response for a survey that is not
  `published`. This is what covers the private drafts the sitemap never advertised.
- **A body on the 404.** `check_survey_access` raises a bare `Http404` for `draft`. It will
  render an "unavailable" page with HTTP status `404` instead — the same page and the same
  status for a draft, a closed-and-deleted survey, and a UUID that never existed, naming
  neither the survey nor the reason. A visitor gets a sentence explaining what to do; a
  crawler still gets a 404 and drops the URL.

The status code stays `404`. Only the body changes. That is deliberate: an explanatory page
served as `200` would keep the URL indexed, which is the defect being fixed.

## Capabilities

### New Capabilities

- `search-engine-indexing` — what the platform submits to search engines, and which survey
  URLs are allowed into an index. No such capability exists today; the rules were implicit in
  one unreviewed queryset.

### Modified Capabilities

- `survey-access-control` — the `draft` denial gains a response body while keeping its status
  code and its silence about whether the survey exists.

## Impact

- `survey/views.py` — `publicly_visible_surveys()` helper, `index`, `sitemap_xml`
- `survey/access_control.py` — `draft` branch renders instead of raising; `noindex` header
- `survey/templates/survey_unavailable.html` — new
- `survey/tests.py` — new tests

No migration. No model change. The sitemap shrinks from 140 survey URLs to 32, which is a
deliberate removal of URLs we told search engines were real.

Out of scope, tracked in `openspec/backlog/`: `Http404` is reported to PostHog error tracking
as though it were a defect (16 of 19 events in the first two days). That is an instrumentation
bug in the error reporter, not in what we index, and it should not ride along with a change to
public URLs.
