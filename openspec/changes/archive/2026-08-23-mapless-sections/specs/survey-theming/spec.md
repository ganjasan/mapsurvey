# survey-theming Specification

## ADDED Requirements

### Requirement: A survey may define an accent color
The creator SHALL be able to set one accent color per survey (settings panel: an on/off
toggle plus a color picker), stored in `style_settings.accent_color` as `#RRGGBB`. When
set, respondent pages SHALL apply it to primary/outline action buttons, the searchable
dropdown's highlight, and the form-layout page tint. Unset SHALL mean the platform's
default styling, byte-identical to pre-change output.

#### Scenario: Accent colors the respondent page
- **WHEN** a survey stores accent `#7a1f2b` and a respondent opens any section
- **THEN** the page's action buttons use `#7a1f2b`

#### Scenario: Turning the toggle off removes the stored value
- **WHEN** the creator unchecks the accent toggle and saves
- **THEN** `style_settings` no longer contains `accent_color`

### Requirement: The accent value is validated at every boundary
Only a strict `#RRGGBB` value SHALL be accepted at form save, at ZIP import
(`_clean_style_settings`), and again at render time — a non-conforming stored value SHALL
produce no style output at all. The accent is interpolated into a `<style>` block, so this
triple validation is the CSS-injection defense.

#### Scenario: A crafted ZIP cannot inject CSS
- **WHEN** an archive carries `style_settings.accent_color = "red;} body{display:none"`
- **THEN** import drops the key and the rendered page contains no trace of the value
