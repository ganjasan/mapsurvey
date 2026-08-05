# Grant reporting pack (Verwendungsnachweis support)

**Type**: feature
**Priority**: medium
**Area**: backend
**Epic**: pro-tier
**Created**: 2026-07-29

## Description

A publicly-funded participation project has to be *proven*, not just run. The grant
recipient files a Verwendungsnachweis showing that the funded activity happened, at what
scale, and with what result. Today that evidence exists scattered across our analytics —
this packages it as something a consultancy can attach to a report.

Note the boundary: **data durability itself is a baseline promise, not a Pro feature** —
projects never disappear for anyone. What Pro sells is the *documentation and contractual
commitment* around it.

## Scope Sketch

- **Project evidence export** (PDF + data bundle): participation period, number of
  participants and contributions, channels used, map of contributions, per-section
  completion, language breakdown.
- **Written retention commitment**: data kept for the applicable Aufbewahrungsfrist, with
  a stated retrieval procedure. This is contract text plus a UI surface showing the
  guaranteed-until date.
- **Exit guarantee**: complete, documented project archive the customer can hold
  themselves — the direct answer to "what if you disappear", which is the real fear
  behind "we don't trust free tools".
- Ties in [funnel monitoring](feature-funnel-monitoring.md) numbers (which channel
  produced participation) and [audit trail](feature-audit-trail.md) (#59) evidence
  (nothing was tampered with after the fact).

## Why this sells

- Kommunalrichtlinie funds Akteursbeteiligung at 70%, 90% in coal regions — the money is
  reimbursed against proof, so proof is what the customer is buying.
- §13 WPG mandates early public participation for municipal heat planning but does **not**
  prescribe its form: a PDF plus an email is legally sufficient. So never sell this as
  compliance — sell it as the evidence that makes reporting painless and the process
  defensible in a council meeting.
- 10,700 German municipalities must deliver a Wärmeplan by 30.06.2028; every one of them
  files paperwork.

## Dependencies / Related

- [DPA / AVV compliance pack](feature-dpa-compliance-pack.md) (#88) — the other half of
  the "we are a real supplier" package
- [Billing & invoicing](feature-billing-invoicing.md) (#93) — receipts belong in the same
  bundle
