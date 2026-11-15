## 1. Model and rules

- [x] 1.1 `DatasetLink` + migration
- [x] 1.2 `data/links.py`: `link_refusal`, `link_survey`, `unlink_survey`, `used_by`, `sync_site_block`, `card_field_names`

## 2. Surveys

- [x] 2.1 `layers_for` owned ∪ linked public; gated endpoint through it; object card per-link fields
- [x] 2.2 settings card: linked rows read-only (Open in Data, Unlink, card fields), "From Data" picker; endpoints

## 3. Sites

- [x] 3.1 map block `dataset` (cleaner, form, save_block keeps the link)
- [x] 3.2 `/p/<slug>/blocks/<id>/dataset.geojson`; public page and canvas fetch it

## 4. Data

- [x] 4.1 dataset page "Used by"; privacy switch refuses private while linked; catalogue count
- [x] 4.2 delete page + POST for workspace uploads

## 5. Ship

- [x] 5.1 tests `survey/tests/test_data_links.py`
- [x] 5.2 translations, help, CLAUDE.md
- [x] 5.3 full suite, /verify, PR into epic/data
