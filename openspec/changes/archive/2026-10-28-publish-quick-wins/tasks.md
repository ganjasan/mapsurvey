## 1. Implementation

- [x] 1.1 P3: `public_results_block_add` redirects to `?block=<new_id>` (both standalone and question branches)
- [x] 1.2 P8: `chart_viz_options`/`map_viz_options` become (value, label) pairs; template loops updated
- [x] 1.3 P4: page-settings toggle → "Page is live · public at /r/<slug>/"; widget → "Draft — not live yet · Open" when page exists unpublished; editor titles "Publish – …" / "Results – …"
- [x] 1.4 P6: switch rows wrapped in `<label class="pr-switch">` (+ cursor/margin CSS)
- [x] 1.5 P9: k-anon note conditional on `page.k_anonymity_threshold > 1`
- [x] 1.6 P12: "Slug" → "Page address" (label + slug-taken message)

## 2. Verification

- [x] 2.1 New tests: add-block redirect carries `?block=`; k-anon note hidden at k=1, shown at k=3
- [x] 2.2 Full `./run_tests.sh survey` green
- [x] 2.3 Browser sanity on :8010 (add block lands in its config; labels/toggles read right)

## 3. Explicit publish action (follow-on to P4, from user feedback)

- [x] 3.1 New endpoint `editor_public_results_set_published` (POST, owner) + URL; draft-survey guard; JSON/redirect
- [x] 3.2 Publish state removed from the settings autosave form; save endpoint only touches `is_published` when the field is present (no unpublish-on-autosave trap)
- [x] 3.3 Prominent action in the Page-settings bar: "Publish page" (disabled on draft survey) / "Unpublish" + live banner; the buried checkbox is gone
- [x] 3.4 Tests: publish/unpublish toggles state, draft survey blocked, autosave doesn't unpublish
