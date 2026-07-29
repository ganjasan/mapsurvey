# Tasks — creator dossiers

## 1. Models + migration

- [x] `CreatorProfile` in `survey/models.py`: OneToOne → user (`related_name='creator_profile'`),
      `organization`, `role`, `country`, `linkedin_url`, `website`, `how_found_us`,
      `summary`, `created_at`, `updated_at`. All optional.
- [x] `CreatorNote`: FK → user (`related_name='creator_notes'`, CASCADE), `author`
      (FK → user, SET_NULL, null), `kind` (research/email/call/signal),
      `body`, `happened_on` (date), `source_path` (blank), `created_at`.
      `Meta.ordering = ('-happened_on', '-id')`.
- [x] Index on `(user, happened_on)`; `source_path` indexed for the import skip check.
- [x] Schema migration.

## 2. Importer

- [x] `survey/management/commands/import_dossiers.py` — walks
      `<root>/<username>/profile.md` + `correspondence/*.md`.
- [x] Header parsing helper in `survey/dossiers.py`: labelled fields
      (`Organization`, `Role`, `Location`, `Web`, `LinkedIn`) tolerant of the
      observed variants (`- **Organization**:`, `## Contact`, `**Role:**`), plus a
      LinkedIn URL regex over the whole body.
- [x] Body → one `research` note; each correspondence file → `email` note dated
      from the filename prefix.
- [x] Skip notes whose `source_path` already exists; update profile columns only
      from non-empty incoming values.
- [x] Do not import `Tier`. Never write to the source tree.
- [x] Dry run by default, `--apply` to write; report matched/unmatched dirs and
      counts.

## 3. Admin

- [x] `CreatorProfile` inline + `CreatorNote` inline on `UserAdmin`, next to the
      cohort inline.
- [x] Standalone `CreatorNote` admin with filters (kind, date) and search over
      body/username, for cross-user reading.
- [x] Organisation column on the user changelist.

## 4. Export

- [x] `survey/management/commands/export_creators.py` — writes `profiles.csv`
      and `notes.csv` to a target directory; `--username` restricts to one person.
- [x] Profiles row carries cohort slugs and the activity figures (surveys,
      published, responses) so the CRM import is self-contained.

## 5. Tests (GIVEN/WHEN/THEN)

- [x] Profile uniqueness; consumers tolerate a missing profile.
- [x] Note ordering newest-first; cascade on user delete; author SET_NULL.
- [x] Import: body → research note, headers → columns, correspondence → dated
      email notes, unmatched dir reported, dry run writes nothing.
- [x] Re-import: no duplicate notes, hand-corrected fields not blanked.
- [x] Tier is not imported.
- [x] Export: both files written, single-user filter, body with commas/quotes/
      newlines survives a parse round trip.
- [x] Admin: staff sees profile and notes; non-staff denied.

- [x] Match users by name variants and by the header email (85 -> 123 of 125
      dossiers matched on the real tree).

## 6. Rollout

- [ ] Dry-run the importer over `docs/marketing/user-outreach/`, review the
      unmatched list.
- [ ] Apply against production.
- [ ] Run the export once to verify the CRM exit path on real data.
- [x] Update `/user-outreach` so research is written to the DB, and record that
      the markdown tree is now a frozen archive.
