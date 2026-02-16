## 1. Backend — pass version history to template

- [x] 1.1 In `editor` view (`survey/views.py`), prefetch archived versions for all surveys using `Prefetch` on the queryset, and annotate each survey object with its version history list
- [x] 1.2 Write tests: survey with single version has empty history; survey with multiple versions has correct history list in template context

## 2. Template — version-aware download dropdown

- [x] 2.1 In `editor.html`, replace the plain "Download Data" link with a conditional: if survey has archived versions, render a dropdown (matching the existing Export dropdown pattern); otherwise keep the plain link
- [x] 2.2 Dropdown options: "All Versions" (`?version=all`), "Current (vN)" (`?version=latest`), and one entry per archived version in descending order (`?version=vM`)
- [x] 2.3 Write tests: rendered HTML contains dropdown with correct version links for multi-version survey; plain link for single-version survey
