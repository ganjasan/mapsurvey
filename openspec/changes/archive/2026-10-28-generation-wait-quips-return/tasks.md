## 1. Templates and styles

- [x] 1.1 `generation_status.html`: remove the bar markup; restore the quip line and rotator from history; add the inline elapsed counter ticking client-side
- [x] 1.2 `generation_progress.html`: caption only — no fill, no bar
- [x] 1.3 `_generation_overlay_css.html`: drop `gen-bar*` styles, restore quip styles, style the elapsed counter

## 2. View

- [x] 2.1 Remove `EXPECTED_QUESTIONS` and the `fill` context value

## 3. Tests

- [x] 3.1 Waiting card: quips and elapsed counter present, no bar markup
- [x] 3.2 Progress fragment: caption present, no fill/percentage; keep the no-visible-percentage guard
- [x] 3.3 Drop the fill-proportion and 90%-cap tests with the feature they tested
- [x] 3.4 GIVEN/WHEN/THEN docstrings

## 4. Verification

- [x] 4.1 Full `./run_tests.sh survey`
- [x] 4.2 Dev stand look: spinner + quip + `(Ns)` ticking; counts caption appears on streamed preview path
