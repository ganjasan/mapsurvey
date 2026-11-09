## ADDED Requirements

### Requirement: Sites carry the workspace brand
The workspace owner SHALL be able to set, in workspace settings, a public name, a logo (a raster image up to 1 MB, verified by its bytes) and an accent colour (`#rrggbb`); anything else SHALL be refused. Every site of the workspace, public and in the builder, SHALL show the logo and the public name (the workspace name when empty) in its head, use the public name in the footer and the event consent line, and use the accent for buttons and links. An accent with less than 4.5:1 contrast against white SHALL be darkened on the site until it reaches it, and the settings SHALL say so; the stored colour SHALL stay unchanged.

#### Scenario: Brand on the site
- **WHEN** the owner sets "Riverside Parks Dept.", a logo and `#1b5e20` and the site is opened
- **THEN** the site shows the logo and that name and uses `#1b5e20`

#### Scenario: Light colour darkened
- **WHEN** the accent is `#ffeb3b`
- **THEN** the site uses a darker shade with at least 4.5:1 against white and the settings explain it

#### Scenario: Bad input refused
- **WHEN** an HTML file is sent as the logo or `red` as the colour
- **THEN** the form is refused and nothing is stored

#### Scenario: Owner only
- **WHEN** an editor posts the branding form
- **THEN** it is refused with 403
