# Design — Pro early-access page

## Context

`/pro/` is a discovery instrument disguised as a product page. Its output is a
frequency table ("which capabilities do public bodies tick, and do consultancies
tick different ones?") plus a list of warm contacts to call. Everything below
follows from that: the page optimises for a complete, honest answer, not for a
conversion.

A mockup of the intended page is next to this file
(`pro-discovery.mockup.html`). `pricing.mockup.html` is the rejected
price-table variant, kept because it becomes useful once answers exist.

## Goals

- Learn what each of the three audiences would pay for, separately.
- Learn the *shape* of a payable price (project budget vs. annual software
  budget vs. billed on to a client) without asking for a number.
- Produce warm contacts for calls.
- Not contradict, and not quietly retire, the "free and open source, not a
  paywall" positioning.

## Non-Goals

- Selling. No price, no plan, no checkout.
- Segmenting visitors into separate pages. One page, one list.
- Replacing `/services/`.

## Decisions

### One page with grouped capabilities, not three audience doors

Rejected: a "who are you" fork into municipality / consultancy / NGO pages.

Doors are three texts to maintain, and they presuppose we already know what to
sell each audience — the exact thing we are trying to find out. Grouping
capabilities by outcome ("Satisfy the paperwork", "Run more than one project",
"Get people to answer") lets each audience recognise itself while leaving the
cross-tabulation intact. If public bodies turn out to tick "resell it to your own
clients", that finding only exists because nothing was hidden from them.

The segment question is still asked (step 1) — it is a field on the answer, not a
routing decision.

### Budget shape, not willingness to pay

"How much would you pay" is answered with silence or with a lie. "Where would the
money come from" is answered readily and settles the question that actually
blocks us: per project or per year. A price table cannot be designed without it —
in the rejected mockup the billing toggle was set by guesswork.

### Free-text "what did we miss" is a first-class field

The highest-value input on the page. Silent workarounds do not appear in usage
data; this is the only channel that surfaces them without us going digging in the
database.

### Persist to a model, and also emit a PostHog event

The model is the record of truth and the contact list; the event makes the answer
queryable alongside the rest of our product analytics. Storing only an event
would put warm leads somewhere we cannot reliably read back, and emailing
ourselves would make the frequency table a manual job.

This measures **us**, which is why PostHog is correct here.
`SurveyEvent`/`TrackedLink` measure our customers' respondents on their behalf
and must stay out of it.

### Capability list lives in one Python constant

The checkboxes, their groups, and their stable machine keys are defined once in
`survey/pro_interest.py` and drive the template, the form's validation, and the
stored value. A checkbox that exists in the template but not in the constant
would be silently dropped on save, which is the failure mode that would quietly
destroy the dataset the page exists to collect.

Keys are stable strings (`own_domain`, `eu_hosting`, `resell`), never indexes, so
reordering or adding an option does not rewrite the meaning of rows already
collected.

### Consent is required, and the page says who processes what

The page argues we are the kind of vendor who can sign a DPA, while collecting
email and organisation. Shipping it without a consent checkbox and a privacy link
hands the first Datenschutzbeauftragte who visits exactly the objection we are
claiming to solve. Consent is a required form field, not a pre-ticked box.

### Anonymous by default, pre-filled when signed in

The page must not require login: a municipality that found `for_government` in
search and never registered is precisely the answer we are missing, and a login
wall would drop it. For a signed-in creator we pre-fill email and attach the user
FK, because a named answer is worth more than an anonymous one.

### Fix the `/services/` orphan in the same change

`/services/` is live, allowed in `robots.txt`, and reachable from nothing. Adding
`/pro/` to the nav while leaving its sibling unlinked would repeat the mistake in
the same commit. Both go into nav, footer and `sitemap.xml`.

## Risks / Trade-offs

- **The page may collect nothing.** Marketing traffic is roughly 8 real visits a
  day. Mitigation: the page is not the campaign — direct email to named leads is,
  and the page is what those emails link to. If two weeks produce fewer than ~10
  submissions, the answer is more outreach, not a redesign.
- **Sample skew.** Nav-only entry over-samples people already interested enough
  to browse. The deferred in-editor entry points would skew the other way (only
  existing users). Both ends are needed eventually; this change ships the end
  that can hear from strangers.
- **Announcing capabilities we have not built.** The page is explicit that we are
  deciding what to build, so a ticked box is a question, not a promise. The one
  place to stay careful is EU hosting: it is on the list as a candidate, and the
  page must not state it exists.
- **Positioning wobble.** "We are building Pro" read alongside "not a paywall on
  Mapsurvey" is a contradiction unless the free-stays-free promise is loud. It is
  stated three times by design, and `/services/` copy is left alone.

## Migration Plan

Additive: one new model, one new URL, nav/footer additions. No data migration, no
change to existing behaviour. Rollback is deleting the URL entry; collected rows
are unaffected.

## Open Questions

- Does the page need a German version before the DE municipality outreach, or do
  we send those leads to the English page with a German covering letter?
