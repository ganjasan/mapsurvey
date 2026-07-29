## Why

`survey/cohorts.py` hard-codes two lists of real customer email domains: a
curated map of ~25 organisations to segments, and a set of academic domains. The
repository is **public**. Anyone reading it gets a list of who uses Mapsurvey —
consultancies, a city government department, a housing association, universities
— assembled and confirmed by us, at a glance.

No personal data is exposed: these are organisation domains, not individuals.
But a customer list is competitive and reputational information, and publishing
it was not a decision anyone made. It happened because the classification rules
were written as code without asking whether the repository was public.

The design already drew the right line — "cohort vocabulary lives in the
database, classification logic lives in code" — and simply put these on the wrong
side of it. A domain that means "this account belongs to a planning consultancy"
is vocabulary about a specific customer, not logic.

## What Changes

- New `DomainSegmentRule`: a staff-editable mapping of an email domain to a
  cohort, held in the database.
- `survey/cohorts.py` keeps only generic rules that name no customer: the
  freemail set, student-subdomain markers, and TLD suffix rules (`.edu`,
  `.gov.uk`, `.ac.uk`). Both customer-domain lists are removed from the source.
- `classify_segment()` consults the database rules first, then the suffix rules,
  and takes an optional preloaded map so bulk classification stays one query.
- `assign_cohorts` gains `--rules-csv` to load or refresh the domain rules from a
  local file, so the production rule set is reproducible without ever committing
  it.
- Tests use invented domains only. No fixture names a real customer.

## Capabilities

### Modified Capabilities

- **user-cohorts**: domain-to-segment rules become database records rather than
  source code, and classification reads them from there.

## Non-Goals

- No change to how cohorts, assignments or the dashboard work. Only the location
  of the domain rules moves.
- Not a claim that this scrubs history: the domains remain in earlier commits and
  in the pull request that introduced them. Removing them from the published
  history is a separate operation, tracked outside this change.
