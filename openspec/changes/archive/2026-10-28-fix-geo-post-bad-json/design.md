## Context

`survey_section` (POST) splits the value posted under a geo question's code on `|`, drops empty
chunks, clamps to `max_features`, then runs `geojson.loads(geostr)` → `GEOSGeometry(...)` →
`Answer.save()` per chunk, followed by the sub-answer properties loop. Nothing guards the decode.
Sub-answers, choice ids and excess features are already handled leniently ("the section POST has no
error-render path", see `geo-multi-feature-input`), so a parse failure here is the last hard crash
on the respondent path.

On the client, `htmx:configRequest` in `base_survey_template.html` walks `editableLayers` and does
`parameters[qid] += JSON.stringify(feature) + "|"`, guarded only by `if (!parameters[qid])
parameters[qid] = ''`. htmx 1.9.10's `getInputValues` turns a repeated form-control name into an
array; an array passes the guard, and `Array + String` in JS joins the array with `,` first.

The production event: one iPhone respondent, 42 × 500 on the same section in 2.5 min, a reload
fixed it. The exact client trigger (which second control shared the name) was not reproduced; the
server hardening does not depend on knowing it.

## Goals / Non-Goals

**Goals:**
- A malformed geometry chunk never fails the section submission.
- Whatever else the respondent answered in that section is stored.
- The malformed chunk remains observable (a logged warning with question code + chunk prefix).
- The client cannot produce the `,`-prefixed chunk through the array path.

**Non-Goals:**
- Reproducing the iPhone trigger on a device; that is follow-up work if the warning keeps firing.
- Returning a validation error to the respondent — the section POST has no error-render path by
  design.
- Changing how valid features are stored.

## Decisions

- **Skip the chunk, keep the rest.** Mirrors `_save_object_answers` and the sub-answer loop: "foreign
  or stale tokens skip their answer, never the feature". Dropping one unreadable chunk loses at most
  what was already unreadable; dropping the section loses everything the respondent typed.
- **Catch narrowly.** `ValueError` (covers `json.JSONDecodeError`), plus `KeyError`/`TypeError` from
  `gj['geometry']` when the chunk is JSON but not a Feature, and `GEOSException` from a geometry
  that GEOS rejects. Not a bare `except`: a database error in `answer.save()` must still surface.
- **Log at WARNING** via the module logger with the question code and the first 40 characters of
  the chunk. PostHog's Django integration captures exceptions, not warnings, so this is a Render-log
  signal; enough to see whether the client fix closed the door.
- **Client: coerce before append.** `if (Array.isArray(v)) v = v.join('')`. Two empty hidden inputs
  become `''`, two prefilled ones become their concatenation, which the `|` split handles. This is
  the minimal change that removes the `,`.

## Risks / Trade-offs

- A respondent whose every chunk is malformed silently loses that answer. Accepted: today they lose
  the whole section and cannot proceed at all.
- If the client trigger is something other than the array path, the server skip masks it. Mitigated
  by the warning log; revisit if it fires after deploy.
