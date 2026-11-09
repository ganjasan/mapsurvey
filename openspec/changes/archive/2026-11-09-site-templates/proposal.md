## Why

Issue #620 (epic #348, Sites v1.1 wave B, story S8 second half). A consultancy runs the same kind of engagement again and again; a new creator faces an empty page. Duplicate (wave A) copies one particular site; there was no reusable starting point and no guidance for a first site.

## What Changes

- **From a template** next to *New site*: Mapsurvey starters — *Consultation* and *Master plan* — built from code through the sites service (headings, a starter text, phases, FAQ questions; blocks that need the creator's material are added empty), plus the workspace's own templates.
- **Save as template** in Site settings: a copy of the site with `is_template`, without survey links (cards and results blocks stay, empty) and without registrations; listed under *Templates* on the Sites list.
- A template is never published (the service refuses, the builder hides Publish and shows a banner) and never opens publicly; members open it like a draft.
- Starting from a starter or a template is a Sites use like *New site*; saving a template is not.

## Capabilities

### Modified Capabilities
- `survey-sites`: sites can start from templates.

## Impact

Migration `0127_site_templates` (`Site.is_template`, additive); `site_templates.py`; `services/sites.py` (`save_as_template`, `create_from_template`, publish refusal); `site_views.py`; URL; `list.html`, `builder.html`, `_page_panel.html`; help; catalogs.
