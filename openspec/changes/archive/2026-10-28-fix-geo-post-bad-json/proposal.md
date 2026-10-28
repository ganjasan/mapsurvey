## Why

On 2026-09-07 a respondent on an iPhone (iOS 18.7, Safari 26.6) hit HTTP 500 forty-two times in
2.5 minutes while submitting section 11 of a live Berlin survey ("Wahrnehmung des
Wittenbergplatzes"; the section holds a `point` question with a text sub-question and a new
`layer_objects` block). The POST carried, under the point question's code, a pipe-joined string
whose first chunk was not JSON; `geojson.loads()` raised `JSONDecodeError` and the whole section
died. After a full page reload the same respondent submitted the same section successfully, so the
bad value came from accumulated in-page state, not from the answers themselves. PostHog issue
`01a07bec-f23e-7b43-9bba-52892c5430d0`.

The server already tolerates every other malformed thing a section POST can carry (unknown
sub-question codes, unparseable choice ids, excess features); a geometry chunk that does not parse
is the one input that still takes the whole submission down.

## What Changes

- Server: in the respondent section POST, a geometry chunk that is not valid GeoJSON (or parses to
  something without a usable `geometry`) is skipped, not raised on. The remaining chunks of the same
  question and every other answer in the section are stored as before. The skip is logged with the
  question code and a short prefix of the offending chunk so the client-side cause stays visible.
- Client: the `htmx:configRequest` hook that appends drawn features to the POST parameter
  normalises the existing parameter to a string before appending. When htmx 1.9 has collected an
  array for that name (two form controls sharing it), the current `+=` stringifies the array with
  `,` separators, which yields a chunk beginning with `,` — exactly the `Expecting value: line 1
  column 1 (char 0)` seen in production.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `answer-persistence`: a geometry chunk that does not parse is skipped rather than failing the
  submission; the rest of the section persists.

## Impact

- `survey/views.py` — `survey_section` POST branch, the `geojson.loads(geostr)` loop.
- `survey/templates/base_survey_template.html` — geo serialisation in `htmx:configRequest`.
- `survey/tests.py` — regression test for the malformed chunk.
- No migrations, no settings, no kill switch.
