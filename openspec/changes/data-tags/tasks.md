## 1. Model

- [x] 1.1 `Tag` (+ `datasets`, `surveys`), migration; `data/tags.py` (`set_tags`, `tags_of`, `workspace_tags`)

## 2. UI

- [x] 2.1 dataset page tags; catalogue chips and `?tag=`
- [x] 2.2 survey settings panel tags (endpoint); dashboard chips, `?tag=`, search

## 3. API / MCP

- [x] 3.1 `tags` on survey out; `?tag=` on the list; `PUT /surveys/{uuid}/tags`
- [x] 3.2 MCP `list_surveys(tag)`, `set_survey_tags`; regenerate references

## 4. Ship

- [x] 4.1 tests `survey/tests/test_data_tags.py`
- [x] 4.2 translations, help, CLAUDE.md, full suite, /verify, PR
