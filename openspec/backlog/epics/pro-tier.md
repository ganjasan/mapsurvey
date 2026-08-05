# Epic: Pro Tier & Monetization

**Created**: 2026-07-29

## Why this epic exists

Monetization changed direction on 2026-07-29. The previous model ("core platform free
forever, revenue from setup/analysis services") was abandoned because **serious buyers do
not trust free tools**. Institutional buyers — municipalities, planning consultancies,
housing associations — want a supplier they can put in a budget, sign a contract with,
and win grant-funded participation projects alongside.

### The grant economy makes "free" a disqualifier, not an advantage

Evidence from the ThINK Jena call prep (German municipal heat planning / climate concepts):

- **Kommunalrichtlinie funds Akteursbeteiligung at 70%, and at 90% in coal regions.**
  A zero-cost tool saves the municipality 30% of a line item the funder already pays —
  a negligible gain against a 100% risk that the supplier disappears.
- A zero cost **cannot be entered into a grant application budget**, so there is no
  budget line, no defined role, and no contractual obligation for us.
- A zero cost **cannot appear in the Verwendungsnachweis** — grant recipients report what
  was spent, not what was saved.
- **10,700 German municipalities must deliver a Wärmeplan by 30.06.2028** — recurring
  pipeline, procured as projects.

**Conclusion**: the unit of sale is a *participation project*, not a seat or a monthly
subscription, because that is the unit a grant funds.

## The split

**Principle**: Free is a fully working tool that produces a real survey and returns all
your data. Pro begins where the survey becomes an **obligation to a third party** —
where you need provable process, representation under your own brand, and controlled
access for a client.

Free is no longer a *plan*; it is a distribution channel (academia, personal projects,
individual civic use). It should not appear on the same page as the professional offer.

### Free — never paywalled

- All question types including point/line/polygon, sub-questions
- Survey multi-language support
- **Full Data Management suite** — attribute table, inline editing, bulk operations,
  session tags/notes, answer linting, auto-validation, validation settings, anomalies
  panel, clean export
- **Export in every format** — CSV, GeoJSON, and Shapefile/GeoPackage
  (deliberate wedge: Open Point charges $15–40K and does not export GeoJSON at all)
- Survey password protection
- Survey versioning (draft copy of a published survey, publish, compatibility check)
- Equal-rights workspace Members (collaboration itself is free)
- Basic response counts and "where are the points" map
- Unlimited surveys, questions, sections, respondents
- Project durability: projects never disappear — this is a baseline promise, not a
  Pro feature

Never gate response volume. Every lead we have gets stuck *collecting* responses; a
respondent cap would punish the one success nobody has achieved yet.

### Pro

| Item | Backlog |
|------|---------|
| Hosting geo-zone (EU / US) as a workspace parameter | [#35](../feature-eu-data-hosting-option.md) |
| DPA / AVV compliance pack (contracts, subprocessors, access register) | [#88](../feature-dpa-compliance-pack.md) |
| Public results pages | [#27](../feature-public-results-map.md), [#21](../feature-live-results-projection.md), [#83](../feature-realtime-public-results.md) |
| Custom domain for survey + results pages | [#89](../feature-custom-domain.md) |
| White-label branding (logo, colors, badge removal) | [#90](../feature-white-label-branding.md), [#42](../improvement-survey-visual-customization.md), [#75](../feature-made-with-mapsurvey-viral-loop.md) |
| Roles & permissions, incl. read-only client access | [#91](../feature-workspace-roles-permissions.md) |
| Audit trail (content edit history) | [#59](../feature-audit-trail.md) |
| AI survey creation | [#15](../idea-ai-survey-creator-chat-agent.md) |
| AI analytics over responses | [#92](../feature-ai-analytics.md) |
| Funnel monitoring (shipped — moves behind the paywall) | [#16](../feature-funnel-monitoring.md) |
| Advanced analytics: cross-filtering, heatmaps, interactive map, comparison sets | [survey-analytics epic](survey-analytics.md) |
| Grant reporting pack | [#94](../feature-grant-reporting-pack.md) |

Enabling infrastructure: [#87 plans & entitlements](../feature-workspace-plans-entitlements.md),
[#93 billing & invoicing](../feature-billing-invoicing.md).

### Analytics is split, not moved wholesale

Free keeps "look at my own data" (counts, points on a map). Pro takes "analyse it and
show it to others" (cross-filtering, heatmaps, comparison sets, interactive analytics
map). Reason: cross-filtering and heatmaps are the strongest demo argument we have
against "Google Forms with a map" — a free user who never sees them will never recommend
us.

### Roles: the purchase trigger is the client, not the team

Members are free and equal, so working as a team costs nothing. Pro sells **read-only
guest access** — the municipality or client watches the collection happen without being
able to break anything. That is exactly the shape a grant project needs.

## Rollout discipline

1. **Grandfather existing accounts.** Live users (Julian Oeser, ibmfph, ThINK and others)
   keep what they already use, on their current projects, indefinitely. The paywall
   applies to new projects and new accounts. Taking away working features from the very
   people we recruited as design partners is the fastest way to lose them.
2. **Make Pro visible before making it billable.** For sales calls it matters more that
   Pro exists as a coherent category with real content than that checkout works.
3. **Fix the copy first.** `for_consultants.html` currently promises "keep the tooling
   cost at zero" — under this model that works against us, since consultancies are the
   target payer. `/services/` and the pricing story must be rewritten together.

## Open structural risk

Invoicing a subsidised German project from a Kyrgyzstan entity: reverse-charge handling,
the grant recipient's obligation to justify supplier choice, and in some programmes
restrictions on procurement outside the EU. An EU legal entity looks less like a nicety
and more like the entry ticket to this model. Tracked in
[#93](../feature-billing-invoicing.md).

## Anchoring

Price against Maptionnaire / Citizen Space (£10.5K–100K per instance per year) and
Open Point ($15–40K per deal) — never against zero. Quote alongside the co-funding rate:
"X €, of which the municipality carries 0.3X under the Kommunalrichtlinie" turns the
price into an argument instead of an objection.
