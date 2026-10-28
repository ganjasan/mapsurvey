# Tasks — fix-question-modal-error-retarget

## 1. Code

- [x] 1.1 `_render_question_modal(request, context)` helper with `HX-Retarget` /
      `HX-Reswap` on HTMX requests
- [x] 1.2 Route all `question_form_modal.html` renders in `editor_views.py` through it

- [x] 1.3 `_visibility_block.html`: id → class, bind per instance

## 2. Tests

- [x] 2.1 Reproduction test (GIVEN/WHEN/THEN): create POST, conditional mode, no
      answers, `HX-Request` header → modal with error, retarget headers, no question
- [x] 2.2 Template test: survey page with section panel + question modal renders no
      duplicate `id="fg-visibility"` (block is class-addressed)
- [x] 2.3 Baseline + after-changes run of the visibility editor tests

## 3. Ship

- [ ] 3.1 Offer commit / push / PR
