# Conditional question visibility

**Type**: feature
**Priority**: high
**Area**: frontend
**Created**: 2026-03-30

## Description

Allow survey creators to define skip/branching logic so that questions are shown or hidden based on previous answers. For example, show question 7 only if the respondent answered "yes" to question 6. This is a core survey feature commonly known as conditional logic or skip logic.

## Notes

- Requested by: bisq (geography student)
- The existing sub-question (parent_question / parent_answer) model may serve as a partial foundation, but full conditional visibility across arbitrary questions is a new capability
- Should work within the same section and ideally across sections
- **Real case (Lyon transit survey, bisqunours, 561 sessions):** Question "SI HABITANT DU 8E SEULEMENT: improvement suggestions for 8th arrondissement" is visible to all 98 respondents, but only ~16 selected arrondissement 8. Need: show question X only if answer to question Y = value Z
