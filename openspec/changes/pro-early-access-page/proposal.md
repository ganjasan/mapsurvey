## Why

We intend to sell something beyond the free platform, and we do not know what it
is. The monetization model says a paid tier is sold as a **project line item for
grant-funded work**, but that is a hypothesis about the *shape* of a price, not a
list of what people would pay for. Guessing the feature set and publishing a
price table would close the conversation we actually need: a visitor either
clicks or leaves, and we learn nothing about why.

Two things make guessing especially expensive here:

- **The audiences want different things.** Municipalities need paperwork their
  legal, IT and accessibility colleagues can sign. Consultancies need several
  clients in one account, white-label, and the right to resell. NGOs and
  community groups need turnout. A single "Pro" bundle built on intuition serves
  none of them, and the ones we drop are audiences we already have.
- **Creators work around gaps silently.** One author produced 12 copied blocks
  and 9 versions in a day and never reported a thing. What people route around
  is invisible in usage data and only surfaces if asked directly.

So the first artefact should be an instrument for asking, not for selling. Prices
come after we have answers, and are derived from them.

Related surface: `/services/` already sells done-with-you help per project. This
change does not replace it — the two are different offers (a product we have not
built yet vs. work we do by hand today) and the new page routes anyone who needs
help *now* to it.

## What Changes

- Add a public **"Pro — early access" page** at `/pro/`, styled like the existing
  audience landings (`base_landing.html`), that asks visitors which capabilities
  would matter on a real project instead of announcing a plan.
- Four inputs: **segment** (public body / consultancy / NGO / research / other),
  **capability checkboxes** grouped by outcome so each audience finds itself
  without reading another's compliance list, a free-text **"what did we miss"**,
  and **budget shape** ("where would the money come from") — the shape of a
  price, never a number.
- **No prices anywhere on the page.** The page states three times that everything
  free today stays free, which is what keeps it consistent with the "not a
  paywall on Mapsurvey" line already on `/services/` and the landing.
- Persist submissions in a new `ProInterest` model and emit one PostHog event so
  the answers are queryable as a frequency table, not an inbox.
- Require an explicit **consent checkbox** and link the privacy policy: the page
  collects email plus organisation while arguing we are safe to sign a DPA.
- Add nav and footer entries for `/pro/` **and for the existing `/services/`**,
  which today has no internal link from any page despite being live and
  crawlable. Add `/pro/` to `robots.txt` and `sitemap.xml`; `/services/` is
  already in both, so its problem is internal linking alone.

## Capabilities

### New Capabilities

- **pro-interest-capture**: a public page that collects which paid capabilities a
  visitor would need, persists the answer, and makes it queryable.

## Impact

- New view `pro_early_access` (GET + POST) + URL `pro/` + template `pro.html`.
- New model `ProInterest` + migration. No changes to existing models.
- New module `survey/pro_interest.py`: capability constants, `ProInterestForm`
  and the event emitter. Not `forms.py` (respondent form machinery) and not
  `editor_forms.py` (editor) — neither is this page's home, and the form's only
  real job is validating against the constants it now sits beside.
- `robots_txt` gains `Allow: /pro/`; `sitemap_xml` gains `/pro/`.
- `base_landing.html` nav and footer gain "Pro" and "Services" entries.
- PostHog: one `pro_interest_submitted` event. This measures **us**, so it belongs
  in PostHog and must not touch `SurveyEvent`.

## Out of Scope

- Any price, plan, checkout or billing.
- Contextual entry points inside the editor (share screen, publish widget,
  Responses tab, dashboard banner). Deliberately deferred: they raise response
  volume but only from people who already signed up, and they touch working
  screens. A follow-up change once this page proves it collects anything.
- Building any of the capabilities the page asks about.
