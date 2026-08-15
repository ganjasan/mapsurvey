# Design — ranking question

## Decisions

### D1 — The order is the submission order, not a parsed string

Each item renders with a hidden input carrying its code, all under the question's field name.
Dragging moves the item's markup, so it moves the input with it, and `request.POST.getlist(code)`
returns the codes in the order the respondent left them. No delimiter to parse, no second source
of truth, and the existing save path already speaks `getlist`.

Rejected: one hidden input holding `"3,1,5,2,4"`. It needs parsing on the server and re-splitting
on prepopulation, and it invites a "rank number" input box later — which is the tie problem
walking back in.

### D2 — Uniqueness is a server rule, not just a widget property

The widget makes an invalid answer unrepresentable, so any invalid submission is tampering or a
bug. The server therefore checks the submission **is a permutation** of the question's item codes
— same set, same length, no repeats — and stores nothing when it is not.

Storing nothing rather than raising is deliberate: answers are not validated server-side anywhere
on this platform (the POST handler builds the form with `initial=request.POST`, so it is never
bound), and inventing a rejection path for one type would be a bigger change than the type. An
unanswered ranking and a tampered ranking both produce no answer row, which is the existing
contract for "nothing usable arrived".

### D3 — Export widens from one cell to one column set

`_answer_cell` returns a single value today, and the CSV builder does
`properties[question.name] = cell`. A ranking answer is N numbers that only make sense in separate
columns, so `_answer_cell` may now return a `dict`, which the builder merges into the row with
keys `"<question> — <item>"`. The existing `EXPORT_NO_COLUMN` sentinel already establishes that
this function speaks in more than plain values.

Rejected: one column holding `"apples > bananas > cherries"`. It reads well and analyses badly —
the user asked for columns precisely so he can average ranks per item.

### D4 — Drag, with a keyboard path that is not an afterthought

Pointer drag uses the native HTML5 drag events; keyboard uses Space/Enter to pick an item up and
the arrow keys to move it, announced through `aria-grabbed` and a live region. Without JavaScript
the question cannot be answered — the same trade-off geo questions already make with Leaflet, and
the alternative (typed rank boxes) is the one thing this feature exists to avoid.

### D5 — Analytics falls back for now

`get_question_stats` dispatches by type and falls back to `_stats_other`, which reports the
answer count. A ranking chart wants mean rank per item, which is a different shape from the
existing choices bar chart and would either need a new template branch or a chart that quietly
plots averages under a counts label. Left as a follow-up rather than shipped misleadingly.

## Risks / Trade-offs

- **No-JS respondents cannot answer.** Accepted (D4), and the section still submits — the
  question simply stores nothing, like any unanswered question.
- **Long item lists on a phone** make dragging fiddly; the keyboard path and a generous touch
  target mitigate it, and creators can keep lists short.
- **Analytics shows a count, not an order** until the follow-up lands.

## Migration Plan

None. New `input_type` value, existing `selected_choices` storage.
