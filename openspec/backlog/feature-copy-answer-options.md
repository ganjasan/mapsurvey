# Copy answer options between questions

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-03-26

## Description

Allow copying answer choices (e.g. a Likert scale) from one question to another. Currently users have to manually re-enter the same options for every question that uses the same scale.

## Notes

- Source: Manuel Frost (manu04) — his survey has ~25 questions with the same 5-point Likert scale
- Could be: "copy from previous question" button, or reusable answer templates
- **2026-08-10 — partially shipped.** Duplicating a question carries its `choices` (`survey/cloning.py:62`), so a Likert question can be cloned. The asked-for control — copy options *from another question* inside the choices editor — does not exist (`question_form_modal.html:82-104`).
