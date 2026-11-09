## Why

Issue #619 (epic #348, Sites v1.1 wave B, story S3). A consultancy delivers the site to its client as its own work; a council needs its identity on it. A site showed the workspace name in plain text and a fixed blue.

## What Changes

- Workspace settings → **Branding** (owner only): a public name (empty = the workspace name), a logo (PNG, JPEG, WebP or GIF up to 1 MB, checked by its bytes, stored under a random public key) and an accent colour (`#rrggbb`).
- Every site of the workspace — public page and builder canvas — shows the logo and the public name in its head (and the name in the footer and the event consent line) and uses the colour for buttons and links. A colour too light for white text or for text on white is darkened on the site to 4.5:1 (WCAG AA) and the settings say so; the stored colour stays what the owner chose.
- One brand per workspace (owner decision default, plan §5 Q3). The "Made with Mapsurvey" rule on sites is unchanged (Pro sites show none). The respondent panel and the flyer (#220) read the same fields later.

## Capabilities

### Modified Capabilities
- `survey-sites`: sites carry the workspace brand.

## Impact

Migration `0126_workspace_branding` (three additive columns); new `survey/branding.py`; `OrganizationBrandingForm`; `org_views.org_settings`; `org/org_settings.html`; site templates and CSS; help; catalogs.
