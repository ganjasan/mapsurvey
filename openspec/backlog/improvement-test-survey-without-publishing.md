# Authors publish and close repeatedly because there is no way to try a survey

**Type**: improvement
**Priority**: high
**Area**: frontend
**Created**: 2026-08-05

## Description

To see a survey as a respondent sees it, an author has to publish it. A `draft` is not
reachable by public URL, and a `published` survey is locked against editing, so fixing
anything means creating a new version. The loop that follows is publish, walk through, spot a
defect, close, new version, publish again.

The `testing` status with its `test_token` exists precisely to avoid this. Authors do not
find it.

## The case that surfaced it

`angele.trolliet@vaucluse.chambagri.fr`, 2026-08-04. Ten versions of the same survey between
12:52 and 15:17, one afternoon:

| Version | Sessions | Window |
|---|---|---|
| 1 | 0 | ~12:50 |
| 2 | 4 | 12:52–12:54 |
| 3 | 1 | 12:59 |
| 4 | 1 | 13:03 |
| 5 | 3 | 13:05–13:22 |
| 6 | 4 | 13:24–14:11 |
| 7–8 | 3 | 14:15–14:27 |
| 9 | 5 | 14:31–14:46 |
| 10 | 1 | 15:17, still published |

All 22 sessions are hers: text answers read `Test 1`, `test un`, `TEST 1`, then invented
names of the `Jean Dubois` kind. Not one of her surveys was ever in `testing` status.

She was doing the right thing, thoroughly: she walked her own survey more than twenty times
before letting a single farmer near it. The product made her burn nine versions to do it.

## Costs

- **Version history becomes noise.** Nine closed versions holding only test data, and the
  cross-version analytics problem in
  [Versioning: cross-version analytics](improvement-versioning-cross-version-analytics.md)
  now has junk to aggregate over.
- **Test data sits in the production tables** and counts as responses everywhere we count
  responses. Our own funnel reads her as an active collector; she has zero real respondents.
  Our GTM read of this account was wrong for a day because of exactly this.
- If she had published to farmers first and iterated after, respondents would have met a
  changing survey.

## Proposed fix

**Make `testing` the default path out of `draft`, not a status buried in a menu.** The editor
should offer "Try it as a respondent" as the obvious action next to Publish, and that action
should put the survey in `testing` and open the tokenised URL.

**Say what testing means** where the author decides: responses collected in `testing` are test
data, and they can be discarded when publishing for real.

**On publish, offer to clear test sessions.** She is going to want a clean dataset for the
prefecture file, and right now that is manual.

## Also observed on the same account

Her survey has **two sections of 53 questions each**, identical in shape: 13 polygons, 37
choice questions. The second is titled `Nom et prénom` and differs only in its first text
question. It reads as a section cloned to reword the header, with the original never deleted.
A respondent would be asked everything twice.

Whether the editor makes that easy to do by accident is worth checking before assuming it was
just her mistake. Not filed separately because the mechanism is unconfirmed.

## Notes

- Raised from the production DB review of 2026-08-05, not reported by the user. She has been
  asked in the first-contact email why the survey was rebuilt so many times; her own answer
  may narrow this further.
- **2026-08-10 — CLOSED.** The publishing widget (`_publishing_widget.html`, shipped in PR #54)
  puts the lifecycle controls behind the status chip that is present in every editor space, and a
  `draft` survey now offers **Move to Testing** beside **Publish — open for responses**. The
  `testing` status is no longer something an author has to know about in advance.
- Still unaddressed, and not tracked separately: the transition does not open the tokenised URL,
  publishing does not offer to clear test sessions, and nothing on screen says that responses
  collected in `testing` are test data.
- Related: [Versioning: cross-version analytics](improvement-versioning-cross-version-analytics.md).
