# LLM discoverability — being the answer when someone asks an AI for a mapping survey tool

**Type**: idea
**Priority**: high
**Area**: general
**Epic**: growth
**Created**: 2026-09-03

## Description

On 2026-09-03 a creator who ran a real consultation with residents answered "how did you come
across Mapsurvey?" with:

> "ChatGPT! We explored Maptionnaire, but that was going to cost upwards of €4k, and for something
> like this we couldn't justify the cost. We actually used ChatGPT desktop to configure most of it,
> which worked really well"

That is the first recorded acquisition through an LLM recommendation, and it beat the incumbent on
price for a small civic body — exactly the wedge in `competitor_maptionnaire`. It is also a channel
we do not measure, do not optimize for, and cannot currently see: an LLM referral arrives with no
referrer, no UTM, and no Search Console impression. Every top-of-funnel number in
`survey/funnel.py` is blind to it.

Two halves, both open:

**Measure it.** Ask on registration, or in the first-run flow, where the creator heard about us —
today the only way we learned this was by emailing someone. `AcquisitionDaily` has a segment
dimension but no source that can carry "an AI told me".

**Earn it.** What ChatGPT recommends depends on what the crawlable web says about us: our own
pages, and third-party listings, comparisons and forum answers about participatory mapping tools.
`idea-public-results-showcase-seo` and `project_seo_keyword_research` both target Google's index;
this is the same content asset judged by a different reader, one that rewards being explicitly
described ("free, supports points/lines/polygons, GeoJSON export, no per-project licence") rather
than ranking for a keyword.

## Scope sketch

- A "how did you hear about us?" field with an explicit AI-assistant option, feeding a new
  `AcquisitionDaily` source so the funnel dashboard can show it next to GSC and Plausible.
- Periodically ask the major assistants the questions our ICP would ask ("free alternative to
  Maptionnaire", "tool for a parish council to map resident suggestions") and record whether we
  appear — a cheap, repeatable check, not a one-off.
- A comparison/alternatives page written to be quotable: capabilities and price stated plainly,
  in the words a buyer would use.
- Make sure the pages an assistant can actually read say what we do — pricing above all, since
  price is what won this one.

## Related

- `idea-public-results-showcase-seo` — same content asset, Google's reader.
- `idea-ai-survey-creator-chat-agent` — the same creator configured the survey with ChatGPT
  desktop; people are already pairing an LLM with our editor by hand.
- Source: `docs/marketing/user-outreach/julian_thomas/correspondence/2026-09-03_reply-received.md`
