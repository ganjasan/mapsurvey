# Tasks: fix-org-slug-validation

## 1. Model guard

- [x] 1.1 `survey/models.py`: extract the slug-uniqueness loop from `Organization.save()` into a reusable helper so the migration and the model share one implementation
- [x] 1.2 `Organization.save()`: when a slug is present but does not match the routable pattern, re-slugify it (falling back to the name, then `org`) instead of persisting it as typed

## 2. Form + view

- [x] 2.1 `survey/forms.py`: `OrganizationSettingsForm` (`ModelForm` over `name`, `slug`) — `SlugField` validation and the unique check run through `full_clean()`, with a help message naming the allowed characters
- [x] 2.2 `survey/org_views.py`: `org_settings` POST goes through the form; invalid input re-renders the page with errors and saves nothing; valid input saves and redirects as before
- [x] 2.3 `survey/templates/org/org_settings.html`: render field errors; add `pattern` and help text to the slug input so the mistake is caught client-side too

## 3. Data repair

- [x] 3.1 Migration `0065_repair_organization_slugs`: re-slugify every organization whose slug does not match the URL pattern, keeping uniqueness; reverse is a no-op. The slug logic is duplicated inside the migration on purpose — importing the model helper by name would break `migrate` on a fresh database after any future rename
- [x] 3.2 Verify against the two known production rows (ids 74, 352) with `migrate --plan` and a dry-run over a local copy of the values

## 4. Tests

- [x] 4.1 Form/view: posting a slug with spaces re-renders with an error and leaves the organization unchanged; posting a valid slug stores it verbatim; posting a duplicate slug errors
- [x] 4.2 Model guard: `Organization(slug='Not A Slug').save()` stores a routable slug; a second organization with the same name gets a distinct slug
- [x] 4.3 Regression: an organization whose slug was non-routable renders the editor dashboard without `NoReverseMatch` (drive the actual template, per `lesson_test_client_misses_html5_validation`)
- [x] 4.4 Migration test: a pre-existing non-routable row is repaired, a routable row is untouched

## 5. Verification

- [x] 5.1 `./run_tests.sh survey` — compare against the pre-change baseline
- [ ] 5.2 After merge + deploy: confirm rows 74 and 352 in production, then mark PostHog issue `01a0355c-3f5a-7793-9490-416aa696967d` resolved
