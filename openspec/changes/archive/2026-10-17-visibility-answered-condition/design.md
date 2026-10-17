## Context

`survey/visibility.py` is the one engine: `_rule_verdict(rule, host_kind, …)` classifies a rule
against the structure and returns `(controller_entry, matchable_codes, broken_reason)`; four
call sites then test `any(code in answered for code in matchable)` (section walk, pop-up walk,
the funnel's `_eligible_sessions`, and — through `describe_rule` — the badge label). The
respondent and preview pages hand same-section and pop-up rules to
`conditional_visibility.js`, which runs the same any-of test in the browser. The editor posts
`visibility_mode` / `visibility_question` / `visibility_choices`.

## Goals / Non-Goals

**Goals**
- "Controller answered, whichever option" as a first-class rule, on every host, with the
  server and the client agreeing by construction.
- Adding an option to the controller never changes such a rule.
- Both rule shapes round-trip through ZIP; nothing stored changes.

**Non-Goals**
- No "not answered" / negation, no "all of", no rules on non-choice controllers.
- No change to the pop-up mechanics of #338, duplication or publishing (they copy the dict).
- The sub-question modal and the question groups of #340 are out of scope.

## Decisions

### D1. The mode lives in the rule dict, read in one place
`{"question_code": c, "answered": true}`; `choice_codes` absent. `visibility.rule_mode(rule)`
returns `'answered'` when `answered is True`, else `'any_of'`; `answered` wins if a stray
`choice_codes` is also present (import normalises to one shape). Nothing outside
`visibility.py` inspects `choice_codes` or `answered` to decide a match.

### D2. `_rule_verdict` keeps its tuple; `matchable` becomes a sentinel for "answered"
Rather than a fifth return value at four call sites, an answered rule returns
`matchable = ANY_ANSWER` (a module constant). The option-code checks ("no option codes
referenced", "every referenced answer option is gone") are skipped for it; the controller-type
and position checks still apply. A new `rule_matches(matchable, answered_codes)` is the one
match function: `bool(answered_codes)` for the sentinel, any-of otherwise. The walks, the
pop-up walk and the funnel call it instead of their inline `any(...)`.

### D3. One client shape for both modes
`visibility.client_rule(rule)` returns `{"question_code", "answered": true}` or
`{"question_code", "choice_codes": [...]}`; `views._build_section_context`,
`editor_section_preview` and `popup_rules_for_client` all use it. `conditional_visibility.js`
tests `rule.answered ? values.length > 0 : rule.choice_codes.some(...)`. The disabled-input and
hidden-controller handling is unchanged, so a hidden controller still satisfies nothing.

### D4. Editor: a match select, not a third radio
The block keeps *Always shown* / *Shown conditionally*. Under the controller select, the
"is any of" label becomes `<select name="visibility_match">` with `any_of` / `answered`; the
checkbox lists are shown only for `any_of`, a one-line help for `answered`. `_parse_visibility_rule`
reads `visibility_match` (absent = `any_of`, so a stale form posts as before) and stores the
answered shape without requiring codes. The block script toggles the list and the help on change.

### D5. Lint and funnel
`lint_rules`: a section ruled "answered" covers every defined option of its controller, so it
never produces an uncovered-option hint and never counts as broken for option loss. The
funnel's `_section_rules` passes the sentinel through; `_eligible_sessions` treats it as "any
non-empty selection". `describe_rule` labels it `if <controller> answered` — the modal pill
slices off `if ` and the funnel its own prefix, as today.

### D6. ZIP import
`_apply_visibility_rules.resolve()` resolves the controller as before; for an answered rule it
returns the answered shape without the option check. Export writes `visibility_rule` as stored,
so an archive written before this change reads back unchanged.

## Risks / Trade-offs

- A sentinel in a tuple is less explicit than a dataclass; the trade is zero signature churn
  across `analytics.py` and the tests. `rule_matches` is the only place that knows about it.
- `help_text` on the two JSONFields is updated without a migration: Django records help_text
  in migrations, so `makemigrations --check` would flag it. The project has no such check and
  help_text is admin-only; the migration is generated if the check ever lands.
