## 1. Catalog build pipeline

- [x] 1.1 Fetch upstream sources into the scratchpad (not the repo): Font Awesome Free 5.15.4 `metadata/icons.json` + `metadata/categories.yml`, `mapbox/maki` `icons/`, `rapideditor/temaki` `icons/` + `data/icons.json`; record versions/commits for the catalog `version` string
- [x] 1.2 Write `scripts/build_icon_catalog.py`: args for the three source paths; reads FA icons (solid + regular only, skip `fab`), Maki and Temaki names/tags; applies the FA-category → product-category table and the Maki/Temaki name-keyword → category table (D7); merges translation tables (D2); writes `survey/assets/data/icon_catalog.json` in the D1 shape; prints per-set icon counts and per-language translated-term counts; exits non-zero on an empty set
- [x] 1.3 Extend the script to emit `survey/assets/img/maki.svg` and `temaki.svg` symbol sheets (`<symbol id="<set>-<name>" viewBox=…>`, fills stripped) (D5)
- [x] 1.4 Dump the unique English term list (FA `search.terms` ∪ labels ∪ Maki/Temaki names+tags) to the scratchpad; author `scripts/icon_terms.ru.json`, `.de.json`, `.es.json`, `.fr.json`, `.pt.json`, `.pl.json`, `.id.json` (term → list of synonyms, lowercase); category labels in all eight languages inside the script
- [x] 1.5 Run the script, commit the catalog and sprites; check gzipped catalog size against the 350 KB ceiling and trim term lists if over
- [x] 1.6 Tests (GIVEN/WHEN/THEN): catalog file parses, has no `fab ` entry, every entry has `v`/`l`/`c`/`t.en`, every category id used by an icon is declared, every `maki:`/`temaki:` value has a symbol in its sprite, no sprite symbol carries `fill`, gzipped size ≤ 350 KB

## 2. Server-side resolver and validation

- [x] 2.1 `survey/marker_icons.py`: `lru_cache`d catalog loader over the static file (via `finders` in dev, `staticfiles_storage` in prod), `is_known(value)`, `resolve(value)` → `{"kind": "font"|"svg", …}` with the default-pin fallback for unknown `<set>:<name>` (D3, D4)
- [x] 2.2 Template tag `{% marker_icon value color=… css_class=… %}` in `survey/templatetags/` rendering `<i>` or `<svg><use href="{sprite}#{symbol}">`; sprite URLs via `static()`
- [x] 2.3 Context processor or base-template snippet rendering `data-icon-sprites='{"maki": …, "temaki": …}'` on `<body>` in `base_survey_template.html` and `editor_base.html`
- [x] 2.4 `QuestionForm.clean_icon_class` in `survey/editor_forms.py`: empty | FA regex | catalog-known `<set>:<name>`; error text names the accepted forms; help text mentions the picker and both forms
- [x] 2.5 Tests: resolve() for FA / maki / unknown-set / unlisted-FA; template tag markup for both kinds; form accepts `fas fa-anchor`, `fa fa-bus`, `maki:bus`, rejects `maki:benchh` and `garbage`

## 3. Rendering surfaces

- [x] 3.1 `survey/assets/js/marker_icon.js`: `MarkerIcon.resolve(value)` / `.element(value, color, cssClass)` reading sprite URLs from `document.body.dataset.iconSprites`; unknown-set fallback; load it in `base_survey_template.html` and `editor_base.html`
- [x] 3.2 `L.Icon.FontAwesome.js` `_createIcon`: build the glyph with `MarkerIcon.element(options.iconClasses, options.iconColor, 'feature-icon')`; delete the `'fa ' +` prefix at both `L.icon.fontAwesome` call sites in `base_survey_template.html`
- [x] 3.3 `L.Icon.FontAwesome.css` + `main.css` (`#crosshair-overlay .crosshair-pin-icon`): add `svg` sibling rules with the same size/offset and `fill: currentColor`; update the keep-in-sync comment
- [x] 3.4 `showCrosshair` and the popup-edit path in `base_survey_template.html`: replace the icon node via `MarkerIcon.element` instead of assigning `className`
- [x] 3.5 `leaflet_draw_button.html`: draw the card icon with `{% marker_icon %}`; keep `data-icon` as the raw value
- [x] 3.6 `partials/rating_stars.html`: draw each step with `{% marker_icon %}` on `field|star_icon`; verify the fill/selected CSS applies to `svg` as well as `i`
- [x] 3.7 Bump Font Awesome to 5.15.4 in `base.html`, `base_survey_template.html`, `editor_base.html`; drop the 5.8.1 mentions in comments (`question_types.py`)
- [x] 3.8 Tests: respondent section page for a `maki:bench` point question contains the `<use>` markup and no bare `fa ` token; for `fas fa-bus` contains `<i class="fas fa-bus`; stars question with `maki:star` renders five `<svg>`; templates reference 5.15.4 and not 5.8.1

## 4. Picker

- [x] 4.1 `survey/assets/js/icon_picker.js`: `IconPicker.attach(input, {catalogUrl, lang})` — lazy single fetch per page, search (all tokens, `t[lang] + t.en + label + name`), category chips with localised labels, 240-cell cap with "type to narrow", default ordering (current → Map → FA by category), selection writes `v` and dispatches `input` (D6)
- [x] 4.2 Telemetry in the picker: `icon_search_miss` (700 ms debounce, once per distinct query per open) and `icon_picked` (`value`, `set`, `via`), guarded by `window.posthog && posthog.capture`
- [x] 4.3 Replace the inline `FA_ICONS` block in `question_form_modal.html` with the attach call; render `data-icon-catalog="{% static 'data/icon_catalog.json' %}"` and the UI language on the modal body; preview uses `MarkerIcon.element`
- [x] 4.4 Picker CSS in `editor_base.html`: chip row, grid cells sized for both `<i>` and `<svg>`, mobile (≤768px) wrap; the picker dropdown must not overflow the modal on the mobile editor layout
- [x] 4.5 Tests: modal markup carries the catalog URL and language attributes and no longer contains the inline icon array

## 5. Serialization

- [x] 5.1 Confirm `serialization.py` export writes `icon_class` verbatim and import stores it verbatim (80-char cut only, no catalog check); adjust only if a path normalises or drops it
- [x] 5.2 Tests: `maki:bench` round-trips through export → import; `temaki:future-icon` imports unchanged

## 6. Verification

- [x] 6.1 Run `./run_tests.sh survey` before and after; summarise the delta
- [x] 6.2 Browser check on the dev server: pick a Maki icon, a Temaki icon and an FA icon on three point questions; place a marker for each, edit one via the crosshair, screenshot the pins at 1× and 2× DPR side by side; stars with `maki:star`
- [x] 6.3 Browser check of search: "bench", "остановка" (RU cookie), "Fahrrad" (DE cookie), "bus stop", "xyzzy" → confirm `icon_search_miss` and `icon_picked` in the PostHog debug console (or the network tab against the proxy host)
- [x] 6.4 Mobile editor layout (≤768px): picker opens, chips wrap, grid scrolls inside the modal
- [x] 6.5 Update `CLAUDE.md` (marker icon resolver: never build icon markup by hand, both value forms, how to refresh the catalog) and `TODO.md` follow-ups (AI enum widening, title-based suggestions, custom upload)
