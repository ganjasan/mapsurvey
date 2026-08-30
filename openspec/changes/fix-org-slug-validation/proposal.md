# Proposal: fix-org-slug-validation

## Why

Two production organizations hold a slug that cannot appear in a URL:

```
 id  |          name          |              slug
  74 | Mount Vernon Studio    | Mount Vernon Studio Spring 2026
 352 | MochiMargo's workspace | CBPR Summer 26' PM
```

`survey/urls.py` routes organization pages as `^org/(?P<slug>[-.\w]+)/settings/$`. A slug with
spaces and an apostrophe matches nothing, so `{% url 'org_settings' active_org.slug %}` — rendered
in the account dropdown of **both** `base.html` and `editor_base.html` — raises `NoReverseMatch`.
For the owner of such an organization every page of the editor returns 500. There is no way out
from inside the product: the settings page that would let them fix the slug is itself one of the
pages that crashes.

PostHog error tracking recorded exactly one `NoReverseMatch` event (2026-08-24, issue
`01a0355c-3f5a-7793-9490-416aa696967d`). One event, not a flood, because the person tried once and
left. The low count is the symptom, not the reassurance.

Root cause is `org_settings` in `survey/org_views.py`: the POST handler reads `slug` straight from
the form and checks only uniqueness.

```python
new_slug = request.POST.get('slug', '').strip()
if new_slug and new_slug != org.slug:
    if Organization.objects.filter(slug=new_slug).exclude(pk=org.pk).exists():
        ...
    else:
        org.slug = new_slug
org.save()
```

`Organization.slug` is a `SlugField`, and `SlugField` does carry `validate_slug` — but Django runs
field validators only from `full_clean()`, which a hand-rolled view never calls. The validation
looks present in the model and is inert at runtime. The form field is a bare `<input type="text">`
with no `pattern`, labelled "Slug", so a creator reading it as a second name field is an ordinary
mistake, not misuse.

## What Changes

- **`org_settings` validates before it saves.** The POST handler moves to an `OrganizationSettingsForm`
  (a `ModelForm` over `name` + `slug`), so `SlugField`'s validator and the uniqueness check both run
  and produce field errors instead of a stored value. The template renders those errors.
- **`Organization.save()` refuses to persist an unusable slug.** Any slug that does not match the URL
  pattern is re-slugified (with the existing uniqueness suffix loop) rather than written as typed.
  The view gives the human a readable error; this guard closes every other path — Django admin, a
  management command, `shell`, a future import — the same way `coerce_creator_html` backstops the
  rich-text editors.
- **Data migration repairs the rows already stored**, re-slugifying any organization whose slug does
  not match the URL pattern, keeping uniqueness. The two production owners get their editor back
  without touching the database by hand.
- **The slug input gets a `pattern` attribute and help text**, so the mistake is caught before the
  round trip.

## Capabilities

### New Capabilities

- `organization-identity`: what an organization's URL identifier is allowed to be, who may change it,
  and what happens to a value that would break routing.

### Modified Capabilities

_None._

## Impact

- **Code**: `survey/org_views.py` (`org_settings`), `survey/forms.py` (new `OrganizationSettingsForm`),
  `survey/models.py` (`Organization.save`), `survey/templates/org/org_settings.html`, new migration
  `0065_repair_organization_slugs`, tests in `survey/tests.py`.
- **Migration number**: 0065. 0064 is taken by an unmerged branch (`feature/session-geo-map-modal`,
  `0064_creatorpreferences`); picking 0065 avoids the collision documented in
  `feedback_parallel_migration_conflicts`.
- **Two organizations change slug on deploy**, so any bookmarked `/org/<old-slug>/` link breaks. Those
  URLs already 404 today — the old values are unroutable — so nothing that currently works is lost.
- **No behavior change** for organizations whose slug is already valid, which is every other row.
