# reports-import-export Specification

## Purpose
The report as a file: a ZIP with `report.json` and pictures, exported from a report and imported into a workspace — unpublished, workspace-only, sanitised, question blocks bound again by survey and question code. Implementation: `reports/files.py`; tests `survey/tests/test_reports_import_export.py`.
## Requirements
### Requirement: A report is exported as a file
The system SHALL give an editor of a report one ZIP holding `report.json` — the opening, the
settings and every block in order — and the pictures of its Image blocks. A block that shows a
question SHALL be recorded by its survey's id and the question's code, never by a row id.

#### Scenario: Exporting
- **WHEN** an editor exports a report with a heading, a text, a picture, key numbers, quotes and a chart
- **THEN** the file's `report.json` lists the six blocks in order, the chart by survey and question code, and the ZIP holds the picture

#### Scenario: Someone who may not edit
- **WHEN** a member of another workspace asks for the export
- **THEN** the answer is 404

### Requirement: A report file is imported into a workspace
The system SHALL create a report from a report file in the importing member's workspace:
unpublished, visible to the workspace only, with its text sanitised like text typed in the editor.
A block that shows a question SHALL be bound again when the workspace has that survey and question
code, and left out with a message naming it otherwise. A file that is not a report file SHALL be
refused with a message and SHALL create nothing.

#### Scenario: Round trip in the same workspace
- **WHEN** an editor exports a report and imports the file
- **THEN** a second report exists with the same opening and the same blocks in order, the chart still showing its question, unpublished and workspace-only

#### Scenario: Into a workspace without the survey
- **WHEN** the file is imported into another workspace
- **THEN** the story blocks and the picture arrive, the chart is left out, and the member is told which block was left out

#### Scenario: A report made by hand
- **WHEN** a file holding an opening, key numbers, headings, text with a numbered list, pictures with captions, two half-width blocks and quotes is imported
- **THEN** the report's page shows them in that order, and every one of them can be edited

#### Scenario: Script in an imported text
- **WHEN** a file's text block carries a script element
- **THEN** the imported report's page carries no script

#### Scenario: Not a report file
- **WHEN** an editor uploads a ZIP without `report.json`, or a file that is not a ZIP
- **THEN** the upload is refused with a message and no report is created

#### Scenario: A viewer
- **WHEN** a viewer posts a report file
- **THEN** the answer is 404 and no report is created

