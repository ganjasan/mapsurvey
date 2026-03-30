# Disable choices on number-type questions in editor

**Type**: improvement
**Priority**: medium
**Area**: frontend
**Created**: 2026-03-30

## Description

The editor currently allows adding choices to number-type questions. This causes the submitted value to be stored in `selected_choices` instead of `numeric`, leading to blank columns in CSV exports. The editor should either hide/disable the choices UI when `input_type` is `number`, or show a warning suggesting the user switch to the `choice` type instead.

## Notes

- Root cause of the "number field blank in CSV export" bug reported by bisq
- The save logic fix (saving to `numeric` regardless of choices) is a safety net, but preventing the misconfiguration in the editor is the proper long-term solution
- Affected editor component: question settings panel where choices are managed
