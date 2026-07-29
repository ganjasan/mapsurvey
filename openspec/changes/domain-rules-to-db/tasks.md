# Tasks — domain rules to the database

## 1. Model + migration

- [x] `DomainSegmentRule` in `survey/models.py`: unique `domain`, FK `cohort`,
      `note`, `created_at`; `save()` lowercases and strips the domain.
- [x] Schema migration `0041_domain_segment_rule`.

## 2. Remove customer domains from source

- [x] Delete `CURATED_DOMAIN_SEGMENTS` and `ACADEMIC_EXACT_DOMAINS` from
      `survey/cohorts.py`.
- [x] Keep only rules that name nobody: freemail set, student markers, TLD
      suffixes, academic naming prefixes/keywords.
- [x] Module docstring states why the split exists (public repository).

## 3. Classification

- [x] `load_domain_map()` — `{domain: cohort_slug}` in one query.
- [x] `classify_segment(email, domain_map=None)` — database rule first, then
      student marker, suffix, academic convention; freemail still yields None.
- [x] `assign_cohorts` preloads the map so a bulk run is one query, not one
      per user.

## 4. Rule loading

- [x] `assign_cohorts --rules-csv PATH` upserts `domain,cohort[,note]` rows;
      unknown cohorts reported and skipped; dry run by default.
- [x] Real rule set written to `docs/marketing/cohorts/domain-rules.csv`
      (gitignored), 42 rules extracted from the source that is being removed.
- [x] No data migration carries the domains — that would re-commit them.

## 5. Admin

- [x] `DomainSegmentRule` registered with search and cohort filter.
- [x] `search_fields` on `CohortAdmin` so the rule's autocomplete works.

## 6. Tests (GIVEN/WHEN/THEN)

- [x] Every fixture domain replaced with an `example.*` domain; no real
      customer appears in the test suite.
- [x] Database rule beats the suffix rule; suffix rules still work with no
      rules present; preloaded map is honoured; freemail still yields nothing.
- [x] Rules file: dry run writes nothing, create-then-update, unknown cohort
      skipped, domain lowercased, one rule per domain.
- [x] Loaded rules drive classification end to end.

## 7. Rollout

- [ ] Merge, then on production:
      `assign_cohorts --rules-csv docs/marketing/cohorts/domain-rules.csv --apply`.
- [ ] Re-run `assign_cohorts` and confirm the dashboard breakdown is unchanged
      (77 rule-classified users before the move).

## 8. History scrub (tracked here, executed separately)

- [ ] `git filter-repo --replace-text` over the single commit that carries the
      domains (`ac24b6b`), force-push `master`.
- [x] Checked the PR #44 description: it carries no domains, so nothing to edit
      there.
- [ ] Note what this cannot reach: GitHub keeps `refs/pull/44/head`, so the
      merged PR's diff survives a force-push. Removing that needs GitHub Support.
