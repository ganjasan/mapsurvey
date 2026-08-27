## 1. Kill switch and model

- [x] 1.1 `FILE_UPLOAD_QUESTIONS` in `settings.py` (env var, default `True`, same idiom as `CONDITIONAL_VISIBILITY`), exposed via the existing context processor; document in `.env.example`
- [x] 1.2 `Upload` model: uuid4 token PK, `session` FK (CASCADE), `question` FK (PROTECT), `file` on `PrivateMediaStorage` with `upload_to='<survey_uuid>/<token>/<name>'`, `original_name`, `content_type`, `size`, `created_at`, `attached` (indexed with `created_at` for the reclaim query)
- [x] 1.3 `Answer.upload` FK (`null=True`, `on_delete=SET_NULL`); `INPUT_TYPE_CHOICES` + `photo`/`audio`/`document`; `FILE_INPUT_TYPES` constant
- [x] 1.4 One migration; **before merge** re-check its number against master leaves (`showmigrations survey | tail`) — parallel worktrees collide on numbering
- [x] 1.5 post-delete signal on `Upload` removes the stored object (survey deletion cascades sessions → uploads; the object must follow the row)
- [x] 1.6 Tests: model round-trip on filesystem storage; deleting an Upload removes its file; cascade from session deletion

## 2. Upload endpoint

- [x] 2.1 `POST /surveys/<uuid>/upload/` — requires an active `survey_session` for that survey AND that the named question is a file type belonging to it; 404 when the kill switch is off
- [x] 2.2 Validation per design: type allow-lists (photo: jpeg/png/webp/heic/gif — **no SVG**; audio: webm/ogg/m4a/mp3/wav; document: pdf/doc(x)/xls(x)/odt/ods/txt/csv), magic-byte check for image+pdf families, platform cap 25 MB, per-question creator cap (lower only)
- [x] 2.3 Per-session abuse caps: 30 files / 150 MB (count/sum over the session's uploads); django-ratelimit on the view, fail-open on Redis outage (established posture)
- [x] 2.4 Response `{token, name, size}`; errors are respondent-readable JSON with a stable shape for the widget
- [x] 2.5 Tests: happy path per type; SVG rejected; mislabelled PDF rejected; over-cap rejected; foreign session's token later refused at attach; switch off ⇒ 404; anonymous access without a session ⇒ 403/404

## 3. Section submit: resolving references

- [x] 3.1 Section POST branch for file types: token → `Upload` (must belong to this session AND this question), mark `attached=True`, write `Answer.upload`; unknown/foreign token skips the answer, saves the rest of the section
- [x] 3.2 Geo path: `properties[code] = ["<token>"]` branch beside the existing text/number/choice branches in the GeoJSON sub-answer loop
- [x] 3.3 Resubmission: existing answers for the section are deleted and rewritten (established behaviour) — re-presented tokens re-attach without a new upload; replaced files detach the old Upload (`attached=False`, reclaim collects it)
- [x] 3.4 Prepopulation: a previously attached file renders the widget in `uploaded` state (name + thumbnail via signed URL) with its token in the hidden input
- [x] 3.5 Required file question: validated at section submit (token present), not at upload time
- [x] 3.6 Tests: attach at submit; foreign token skipped; resubmit keeps file; replace detaches old; required enforced; hidden-by-visibility file question never required (visibility engine already guarantees this — regression test)

## 4. Respondent widget (JS + templates)

- [x] 4.1 Upload widget partial + JS: states empty → uploading (progress, cancel) → uploaded (name/size, photo thumbnail via signed URL, replace) → error (message, retry); hidden input carries the token only in `uploaded`
- [x] 4.2 `photo`: `accept="image/*" capture="environment"`; `document`/`audio`: accept lists per design
- [x] 4.3 Voice recording (audio only): feature-detect MediaRecorder + getUserMedia; Record → pulsing indicator + mm:ss → Stop → player + re-record; Blob uploads through the same endpoint (`audio/webm`, Safari `audio/mp4`); any failure degrades silently to the file input
- [x] 4.4 Popup integration: widget renders inside the geo popup form; Apply is disabled while an upload is in flight; token lands in `properties[code]` exactly like a text sub-answer
- [x] 4.5 Template guard test right after editing templates (multi-line `{# #}` lesson); no `|safe` anywhere near filenames
- [x] 4.6 Browser-driven on the worktree dev stand (2026-08-27): section renders all three widgets (camera/record buttons feature-detected), async upload returned a token and flipped the widget to uploaded, point → popup → photo sub-question → Apply → Finish produced TOP photo answer + SUB photo answer under the point, both uploads attached=True in the DB. `capture="environment"` asserted in the editor smoke test. **Real-device recording (iOS Safari / Android Chrome) remains owner-run** — MediaRecorder cannot be exercised from this harness: desktop pick-and-submit; mobile viewport camera attribute present; popup flow point → photo → Apply → submit; recording on a real device (iOS Safari + Android Chrome) — test client cannot see any of this

## 5. Editor

- [x] 5.1 Picker: Files group (photo/audio/document) between Map Questions and Display Blocks, gated by the switch; icons, hints, hover examples per the picker spec; `image` display block stays where it is
- [x] 5.2 Sub-question type choices for geo questions include the file types
- [x] 5.3 Per-question settings: max size (≤ platform cap), required toggle (existing mechanism)
- [x] 5.4 Live preview renders the widget in empty state; autosave (EDIT forms) unaffected — the type change goes through the create dialog which keeps its explicit Create button
- [x] 5.5 Tests: picker markup with switch on/off; metadata-drift guard extended to the three new types (the picker spec's canary); editor smoke for creating each type

## 6. Creator views and export

- [x] 6.1 Responses table: file answers render original name → signed URL (15 min), photo thumbnail inline; filename always inserted as text
- [x] 6.2 Responses geo popup: file sub-answer as server-minted signed link, filename as text (spec delta scenarios), session detail modal likewise
- [x] 6.3 `download_data`: `files/<session_id>/<question_code>__<original_name>` in the ZIP via storage API (works for filesystem and S3); CSV/GeoJSON cells carry that relative path; memory-conscious streaming (read per file, no full-archive buffering beyond the existing BytesIO pattern)
- [x] 6.4 Public results: assert `PublicResultsService` ignores file answers entirely (test, not just absence of code)
- [x] 6.5 Tests: signed link in table for viewer role; 404 posture for outsiders unchanged; ZIP contains files + referencing cells; k-anonymity surfaces never see uploads

## 7. Orphan reclamation

- [x] 7.1 `reclaim_orphan_uploads` command: delete `attached=False` uploads older than 48h (rows + objects); `--dry-run` default, `--delete` to act, mirroring `reclaim_preview_media`
- [x] 7.2 Added via `reclaim.sh` wrapper (dockerCommand has no shell — the predeploy lesson — so chaining lives in a script); cron now runs `sh ./reclaim.sh` service command (chain after preview reclamation) — no new Render service
- [x] 7.3 Tests: old orphan deleted, fresh orphan kept, attached never touched, dry run touches nothing

## 7b. Owner mobile-testing round (2026-08-27, PR preview + screenshots)

- [x] File questions render as cards like every other question; widget-drawn titles removed (they doubled the popup label and printed "None" for unnamed questions)
- [x] Several files per question: creator-set cap in question settings — saved on CREATE too (create dropped every vs_* field platform-wide; file types now parse them through a shared helper on both paths), label "Max files (1–10)" with a type-default placeholder that follows the picker
- [x] Photo: "Take photo" (camera, coarse-pointer devices only) + "Add photo" (gallery) — capture alone locked mobile out of the gallery
- [x] Respondent inspects uploads: photo lightbox, inline audio player, document download (S3 signed URL carries Content-Disposition: attachment — the download attribute is ignored cross-origin)
- [x] Creator previews everywhere: session modal and Responses-map popup show photo thumbnails and audio players, documents as download links (server-typed `kind`, DOM built from server hrefs + textContent only)
- [x] Editor Live Preview uploads work: collaborators get a lazily-created session tagged `editor-preview` (visible in Responses); real respondents get "Please reload the survey page and try again"
- [x] Popup controls aligned (flex row; Bootstrap label margin was skewing the buttons)
- [x] AI generator taught the file types (owner overruled the earlier exclusion): prompt guidance on when photo/audio/document help, geo-sub-question preference, "never require unless pointless without it"; fixed the old `image (upload)` mislabel
- [x] A11y from the audit: aria-labels on icon buttons, 28px remove target, progressbar role, aria-live on the recording timer. Known platform-wide issue NOT touched: Bootstrap #007bff on white is 3.98:1 (needs its own theme change)

## 8. Ship

- [x] 8.1 Full suite green: 1657 tests (36 new), 1 skipped, 0 failures
- [x] 8.2 ZIP export/import (verified: `VALID_INPUT_TYPES` derives from the model, structure ZIPs carry no respondent data; creator size cap does not ride ZIP — same as geo feature limits) of survey **structure** (serialization.py): file questions export like other questions (no respondent data in structure ZIPs — verify, expect no change needed)
- [x] 8.3 `render.yaml` (one line: cron dockerCommand → `sh ./reclaim.sh`): no changes expected (bucket vars already on web+worker); confirm cron command chaining
- [ ] 8.4 PR with the standing checklist: migration number re-checked against master, kill switch documented, browser-driven evidence attached
- [ ] 8.5 After merge: prod smoke — create a photo question on an owned draft, upload from a phone, see it in Responses and in the ZIP; then delete the test question

## 9. Deliberately out (recorded, not forgotten)

- [ ] 9.1 Video questions — own change, needs cost/timeout modelling
- [ ] 9.2 EXIF policy (keep for field GPS vs strip for privacy) — own change with a product decision
- [ ] 9.3 Offline queueing for field collection — belongs to the field epic
- [ ] 9.4 Image thumbnails/transcoding (HEIC preview on Windows) — revisit on first real complaint
- [ ] 9.5 Streaming responses export — the ZIP builds in a BytesIO (pre-existing pattern); a survey with hundreds of 25 MB audio answers would assemble the whole volume in RAM on a 512 MB instance. Fine at current volume; revisit when file-heavy surveys appear
- [x] 9.6 AI generation of file questions — DONE in round 7b (owner overruled the exclusion; prompt guidance added)
