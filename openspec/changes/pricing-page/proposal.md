## Why

Pro is on sale through PayPro Global (change `paywall-payproglobal`, #268), but nobody can see
what it costs before paying. **Plan & billing** shows no price: Free is a one-line box, Pro a
paragraph with three buttons, and its "Prices" link points to `/#pricing`, an anchor the homepage
does not have. The marketing nav and footer say **Pro** and lead to `/pro/`, a research
questionnaire that by design quotes nothing. The only place the price appears,
`partials/_landing_pricing.html` on the category landings, still says "early access" and lists
public results pages, which are free, as Pro, while leaving out what Pro actually adds (no badge,
the team's consulting, the API and MCP server). There is also no visible offer for the case where
we build and run the survey for the customer — work we sell by the hour after a call (issue #433).

## What Changes

- **One plan-card partial** (`partials/_plan_cards.html`, own stylesheet `css/plan_cards.css`):
  three cards — **Free** ($0), **Pro** ($49 a month or $490 a year per workspace, a monthly/yearly
  switch without JavaScript), **Done for you** (we build, launch and run the survey and hand over
  the analysis; quoted after a call, no figure). The Pro bullets come from `billing/features.py`
  through `{% feature_label %}`. The partial is the ONLY template that names the Pro figure; the
  `surface` parameter (`public` | `billing`) decides the buttons.
- **New page `/pricing/`** (`views.pricing`, `pricing.html`, in `sitemap.xml`): the cards, a short
  payment FAQ (PayPro Global as merchant of record, card/PayPal, invoice or purchase order on the
  yearly plan, cancelling keeps everything), a link to `/pro/` ("tell us what Pro should do
  next") and to `/services/`.
- **Nav and footer:** the **Pro** item becomes **Pricing** → `/pricing/`. `/pro/` stays as it is
  and is linked from the pricing page.
- **Plan & billing:** the Free / Pro / Done-for-you cards replace the two boxes; the current plan
  is marked, the owner's upgrade button and "Get a quote" live in the Pro card and follow the
  monthly/yearly switch; "Prices" → `/pricing/`. Current-plan state, manage and cancel blocks stay.
- **Category landings:** `_landing_pricing.html` keeps its section and heading and renders the
  same partial, so the four landings and the hub say what `/pricing/` says.

## Capabilities

### New Capabilities
- `pricing`: the plan cards, the `/pricing/` page, the nav entry and the cards on Plan & billing.

### Modified Capabilities
- `landing-page`: the footer's "Product" column links `/pricing/` instead of `/pro/`.

## Impact

- Templates: `partials/_plan_cards.html` (new), `pricing.html` (new), `partials/_landing_pricing.html`,
  `base_landing.html` (nav + footer), `billing/templates/billing/org_billing.html`.
- `survey/views.py` (`pricing`, sitemap), `survey/urls.py`, `survey/assets/css/plan_cards.css`.
- Strings: English only, like the rest of the billing UI and the landings' pricing block today;
  translating billing is a follow-up.
- Tests: the "price lives in one place" test moves to the new partial; new tests for `/pricing/`,
  the nav, and the billing cards.
- No model, migration, setting or checkout change: the form still posts `period` and `quote`.
