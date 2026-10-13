## 1. Fix

- [x] 1.1 `base.html`: `.form-check-terms` label as a flex row; checkbox inline at natural size, overriding the text-field rule
- [x] 1.2 Test: the terms row carries the class the layout hooks on, and the checkbox sits inside its label

## 2. Verify

- [x] 2.1 Browser check at 1280 and 360px: box ~16px, left of the text, same line
- [x] 2.2 Registration tests green
