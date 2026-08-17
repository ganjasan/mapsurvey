## 1. View

- [x] 1.1 Add `EXPECTED_QUESTIONS = 8` near the status endpoint with a comment naming it a display calibration from recorded drafts, revisitable against `AIGenerationEvent.questions_drafted`
- [x] 1.2 Compute `fill = min(90, round(questions * 90 / EXPECTED_QUESTIONS))` in the pending branch and pass it to the fragment context

## 2. Templates

- [x] 2.1 Replace the quip line in `generation_status.html` with the bar: indeterminate stripe markup in the placeholder, title and leave-the-page note kept, quip rotator script removed
- [x] 2.2 Extend `generation_progress.html` to carry the determinate fill (inline width from context) above the existing counts caption
- [x] 2.3 Bar styles in `_generation_overlay_css.html`: track, determinate fill with width transition, indeterminate animation, `prefers-reduced-motion` fallback

## 3. Production streaming

- [x] 3.1 Flip `AI_STREAMING_ENABLED` production `value` to `"true"` in `render.yaml` (both services), updating the comment to record that the stand proof happened on 2026-08-17
- [x] 3.2 Update the `.env.example` wording accordingly

## 4. Tests

- [x] 4.1 Fragment carries the computed fill; fill is capped at 90 when questions meet or exceed the expectation
- [x] 4.2 Placeholder state (no counts yet) renders the indeterminate bar and no numbers
- [x] 4.3 Existing polling tests still pass unchanged (204 discipline, access control)
- [x] 4.4 GIVEN/WHEN/THEN docstrings

## 5. Verification

- [x] 5.1 Full `./run_tests.sh survey` against baseline
- [x] 5.2 Live check on the local dev stand: stripe during reasoning, fill advancing with the counter, redirect at the end
