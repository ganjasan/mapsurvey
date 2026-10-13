## Context

`base.html` styles every `.auth-card .form-group input` as `display: block; width: 100%`, which is right for text fields. The terms checkbox lives in a `.form-group`, so it inherits a full-width block. The browser draws the native box centred inside it, on its own line above the label text.

## Decisions

- **Scope the fix to the terms row, not to every checkbox.** The rule is `.auth-card .form-check-terms label { display: flex; gap: 0.6rem; align-items: flex-start }`. The input gets `.auth-card .form-check-terms input[type="checkbox"] { display: inline-block; width: 1rem; height: 1rem; flex: none; margin-top: 0.2rem; padding: 0; accent-color: #2a7f6f }`. The higher specificity beats the generic text-field rule. Other auth forms have no checkboxes today, and a global `input[type=checkbox]` override would be a wider change than the bug.
- The label keeps normal weight (400), so it reads as a sentence, not a field title.
