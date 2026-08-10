# Link questions to geoinformation after creation

**Type**: feature
**Priority**: high
**Area**: frontend
**Created**: 2026-03-26

## Description

Allow survey creators to link existing questions to a geo-question (point/line/polygon) after the survey has been created. Currently, if you forget to set the parent geo-question when creating questions, you have to delete and recreate all questions from scratch.

## Notes

- Source: Manuel Frost (manu04) — had to consider recreating all 35 questions because he didn't link them to the polygon at the start
- This is a major UX pain point for complex surveys
- Implementation: add a "parent geo-question" dropdown to the question editor that can be changed at any time
- **2026-08-10 — partially shipped.** Copy/paste-as-sub-question clones a question under a geo parent (`survey/editor_views.py:956-1011`, `survey/cloning.py:54-88`). What the item actually asks for — reparenting an *existing* question — is not there: no parent selector in `question_form_modal.html`, no move endpoint, and the Sortable lists have no cross-list group (`survey_detail.html:484-503`).
