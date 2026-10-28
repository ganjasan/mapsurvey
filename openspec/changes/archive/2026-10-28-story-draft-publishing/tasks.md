## 1. Command
- [x] 1.1 `seed_story`: new → unpublished; re-run keeps state; `--publish` / `--draft` explicit, mutually exclusive
- [x] 1.2 `--from DIR`: read the story outside `survey/story_data/` (unapproved drafts stay out of the public repo)

## 2. Admin
- [x] 2.1 `list_editable = ('is_published',)`, actions publish / unpublish; publish fills an empty `published_date`
## 3. Staff preview
- [x] 3.1 `story_detail`: staff get unpublished stories with `is_draft_preview`; others 404
- [x] 3.2 `story_detail.html`: draft banner + `<meta name="robots" content="noindex">`
## 4. Tests (GIVEN / WHEN / THEN)
- [x] 4.1 seed on empty DB → draft; `--publish` → published; re-run keeps a published story published
- [x] 4.2 admin publish action publishes and stamps the date; unpublish hides it
- [x] 4.4 `--from` installs a draft from a directory outside the repo
- [x] 4.3 staff see a draft with the banner and noindex; anonymous get 404
## 5. Docs
- [x] 5.1 `CLAUDE.md` stories paragraph; `customer-story` skill publish step
