---
title: Make a question conditional
description: Show a question or a whole section only to respondents who picked a given option earlier.
sidebar:
  order: 13
---

You end up with a question (or a section) that respondents see only when their answer to an earlier choice question matches the options you pick.

## Before you start

- The controlling question must be a **Choices** or **Multiple Choices** question that comes *earlier* in the survey: earlier in the same section for a question rule, or in an earlier section for a section rule. Rating, number and text questions cannot control visibility.
- On a published survey that has responses, visibility is changed in unpublished changes; see [Edit a published survey](/how-to/edit-a-published-survey/).

## Steps

1. Make sure the controlling question exists and has its options. In "Safe crossings", for example, a **Choices** question `Do you cross Main Street on foot?` with options `Yes` and `No`.
2. Open the item you want to hide or show:
   - For a question, click its pencil icon to open the question dialog and scroll to **Visibility**.
   - For a section, select it in the left column; **Visibility** sits in the section form.
3. Switch from **Always shown** to **Shown conditionally**.
4. Under **When the answer to**, pick the controlling question. The list offers only choice questions positioned earlier, grouped by section; if it is empty, the controlling question is not earlier than this item.
5. Under **is**, choose how the answer should match:
   - **any of…** — tick one or more options. The item is shown when the respondent's answer includes any of them. For the example, tick `Yes` on the map question `Where do you feel unsafe crossing the street?`.
   - **answered (any option)** — the item is shown as soon as the respondent has picked any option of the controlling question, whichever it is. Options you add later count automatically, so the rule never goes stale. This is the usual choice in a pop-up that opens with a required "Type of place" question followed by questions every type should get.
6. Save with **Save** (question) or let the section form autosave.

<!-- screenshot: the Visibility block with Shown conditionally selected, a controlling question chosen and one option ticked -->

7. Play both branches in the **Live preview**: answer `No` and the map question disappears; answer `Yes` and it appears in place, without a page reload.

## How rules behave

- A hidden question is not disabled, it is absent from the page. Its **Required** never blocks the respondent, and anything they answered in it before changing the controlling answer is deleted when they move on.
- A hidden section is skipped as a unit, including every question in it, whatever those questions' own rules say.
- Rules cascade: if B is shown only when A = Yes, and C only when B = Yes, then answering A = No hides both B and C.
- Within the same section the effect is immediate; across sections it applies when the respondent moves to the next page.
- An item can carry one rule. To combine conditions, put the dependent question in its own section with a section rule, then give the question its own rule.

## Broken rules show to everyone

A rule breaks when its controlling question is deleted, changes to a non-choice type, is moved after the dependent item, or (for an **any of…** rule) loses every option the rule referenced. An **answered (any option)** rule names no options, so changing the options never breaks it. A broken rule fails open: the item is shown to all respondents, and the editor marks it with a **broken rule** badge in the question list or section list. Open the item, fix or remove the rule, and the badge goes away. If only some of the referenced options were deleted, the rule keeps working on the ones that remain.

The editor also warns when sibling sections each depend on one option of the same question and some option leads to no section at all, so a branch of respondents does not end up with an empty survey.

## Result

Questions and sections that carry a rule show a branch badge summarising the condition in the editor (`if Type of place = Park`, or `if Type of place answered`); the controlling question shows how many rules depend on it. Respondents never see hidden items, and the export leaves those cells empty for them. In **Responses › Performance**, a section behind a rule is compared with the respondents the rule let in, not with everyone.

## Related

- [Question types](/reference/question-types/)
- [Designing a map survey](/learn/designing-a-map-survey/)
