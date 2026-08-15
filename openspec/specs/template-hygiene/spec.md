# template-hygiene Specification

## Purpose
TBD - created by archiving change template-comment-leak. Update Purpose after archive.
## Requirements
### Requirement: Templates carry no multi-line `{# #}` comments

Templates SHALL NOT use a `{#` whose closing `#}` is on a later line, because Django parses `{# #}`
as a single-line comment and renders such a block into the page as visible text. Multi-line comments
SHALL use `{% comment %}/{% endcomment %}`. The test suite SHALL fail when a template breaks this,
naming the file and line.

#### Scenario: A multi-line hash comment fails the suite

- **WHEN** a template contains a `{#` with no `#}` on the same line
- **THEN** the test suite fails and names that file and line

#### Scenario: Single-line hash comments stay allowed

- **WHEN** a template contains a `{# ... #}` opened and closed on one line
- **THEN** the test suite passes

#### Scenario: No comment text reaches a rendered page

- **WHEN** the editor navbar of a draft copy, an account-activation page, or a landing page with an
  FAQ is rendered
- **THEN** no template comment text appears in the response

