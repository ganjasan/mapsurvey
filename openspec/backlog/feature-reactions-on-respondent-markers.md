# Reactions on other respondents' map markers (upvote / downvote)

**Type**: feature
**Priority**: medium
**Area**: backend
**Epic**: community-engagement
**Created**: 2026-08-31

## Description

Once respondents can see what others marked (`#153`), the next question every incumbent
answers is "do you agree?". Ideenkarte has like/dislike on every public pin; Maptionnaire
lists "Upvoting and downvoting on the responses of others" in its base tier; Open Point
has five reaction modes. ThINK Jena (replacing Ideenkarte) will measure us on this.

Distinct from `#152`, which asks questions about the *creator's* features. This is about
the *respondents'* features: a marker placed by one respondent collects 👍/👎 from later
ones, and the tally becomes a sortable attribute in Responses and on the results page.

## Scope Sketch

- `AnswerReaction` (answer, session, value ±1), one per session per answer, toggleable.
- Shown only for geo questions the creator marks "public inside the survey"; respects the
  same clean-sessions definition as `PublicResultsService`.
- Abuse: session-scoped, rate-limited per IP through the existing `django-ratelimit`
  setup; no accounts.
- Export: `reactions_up` / `reactions_down` as GeoJSON properties and CSV columns.

## Depends on

`#153` inline results step (the surface where other markers become visible).

## Field evidence — 2026-09-03

First unprompted request from a creator who actually ran the survey with residents.
Cllr Julian Thomas (Whitehouse Community Council, Milton Keynes), dog-bin siting consultation
distributed via the council website and Facebook, asked for exactly this when invited to name
what was missing:

> "The ability for respondents to see previous submissions and 'up vote' them instead of adding a
> new pin would have been great"

Note the framing: upvoting is not a nice-to-have engagement metric for him, it is a *substitute
for a duplicate pin*. Ten residents wanting a bin at the same corner currently produce ten pins
the council then has to de-duplicate by hand. That reframes the value: data quality first,
engagement second — and it strengthens the case for `#153` (inline results step) as the
prerequisite rather than a parallel feature.

Source: `docs/marketing/user-outreach/julian_thomas/correspondence/2026-09-03_reply-received.md`
