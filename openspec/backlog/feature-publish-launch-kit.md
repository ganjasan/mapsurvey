# Publish launch kit — ready-made distribution artifacts at publish time

**Type**: feature
**Priority**: high
**Area**: backend
**Epic**: growth
**Created**: 2026-08-21
**Related**: [Embed widget](feature-survey-embed-widget.md) (#131), [AI audience plan](feature-ai-audience-plan.md) (#129), [Share flow dead-ends](improvement-share-flow-private-dead-end.md) (#128), [UTM link generator](../changes/archive/2026-07-04-utm-link-generator) (shipped)

## Description

When a survey is published, hand the creator concrete artifacts to carry into their
channels — not advice: a QR poster/flyer (auto-generated PDF), the embed snippet
(#131), and copy-paste texts (social post, mailing paragraph, press-release blurb) each
pre-wired with its own `TrackedLink` so channels become measurable. Deterministic and
Free-tier: this is the mechanical layer under the AI audience plan (#129), which
personalises *who and where*; the kit covers *what to hand out*, works without AI, and
is the fallback when the AI plan is not available.

The gap is proven: only 20 of 61 published surveys ever created a TrackedLink, 22 of
1934 respondent sessions carry UTM — creators stop at "published" because there is
nothing to physically take to their audience. For our municipal/participation ICP the
offline channel (poster in a town hall, flyer at an event) is often the primary one.

## Notes

- QR poster: survey title + short URL + QR, A4 PDF, in the survey's primary language;
  the QR link is its own TrackedLink (`source=qr`) so offline finally shows up in
  Traffic Sources.
- Fold into the existing Share page rather than a new surface — #128 shows creators
  already go there and leave empty-handed; the kit is what they should leave with.
- Copy texts must respect survey language (75-language content system), not UI locale.
