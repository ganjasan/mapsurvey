---
title: Ask how to spend a budget
description: Let respondents split a budget between priorities, pick projects that fit it, or place priced items on the map until the money runs out.
sidebar:
  order: 12
---

You end up with a question where every choice costs something and the money is limited, so respondents show you trade-offs instead of ticking everything as important.

There are three ways to ask:

| Way | The respondent… | You get |
|---|---|---|
| **Split a budget** | shares a fixed amount between your items (parks, safety, youth…) | the average share of the budget per item |
| **Choose projects within a budget** | ticks projects, each with a cost, until the budget is spent | the share of respondents who funded each project, and the most supported set that fits |
| **A budget on a group** | places marks on ordinary map questions, each with a price (bench £2k each, path £50 a metre, bed £30 a m²), until the group's total is spent | marks, metres or m² per question, what they cost, where they went |

## Before you start

- A budget on a group needs map questions in a map section. The other two work in any section.
- Projects can also be the objects of a reference layer, so each project sits on the map where it would be built. Set a numeric property such as `cost` on every object first; see [Add a reference layer](/how-to/add-a-reference-layer/).
- Everything here is free except projects taken from a reference layer, which is part of Pro.

## Split a budget

1. Add a question and pick **Budget**.
2. Under **Budget**, keep **Split a budget** selected.
3. Enter the **Total budget** and pick the **Unit**: **Currency** (type the symbol, e.g. `£`), **Points**, or **%** (the total is then 100).
4. Set the **Step**: amounts move in steps of this size. For £20M, a step of 500000 gives forty steps; leave it empty for a twentieth of the total.
5. Choose the **Rule**: **Must allocate the whole budget**, or **Can allocate up to the budget**.
6. Under **Items**, add one row per priority. A **Description** shows under the item for respondents; a **Cost** here is only a guide. Give each item a **Colour**: the budget bar is stacked in the items' colours, so respondents see what went where (for a budget group, it is each map question's marker colour).
7. Check it in the **Live preview**: the bar at the top shows what is left, and Next stays blocked until the rule is met.

<!-- screenshot: the Budget block with Split selected, £20M total and five items -->

## Choose projects within a budget

1. Pick **Budget**, then **Choose projects within a budget**.
2. Enter the total and the unit.
3. Under **Items**, give every project a **Cost** — a project without one cannot be saved. Or switch **Items** to **Objects of a layer**, pick the layer and name the property that holds the cost. Objects without a number there are shown but cannot be picked.
4. **Minimum items** asks respondents to pick at least that many.

Respondents tick projects; a project dearer than what is left greys out and says by how much.

## A budget on a group

1. In a map section, click **New Question** and pick **Budget group** under *Map questions*. (Or add an ordinary group and give it a total under **Budget**.) Under **Budget**, set the **Total** and the unit (currency with a symbol, or points).
2. Add the map questions that share the budget to the group — a point question for benches, another for lamp posts, a line question for paths, an area question for flower beds — with **Add question to group**, or drag existing ones in. Add sub-questions to any of them as usual.
3. Open each map question in the group. Under **Places per respondent** there is now a **Price**: the amount, and what it is **per** — a mark; for a line, a metre of the line; for an area or a spray, a square metre.
4. A question without a price places marks for free; the group dialog says how many of its questions are priced.

Respondents see the price on each button ("£50 / m") and the bar in the group header. A button whose next mark would not fit is greyed out with the reason; a line or area drawn too long or too large is refused with what it would have cost. Everything else about the map questions — sub-questions, minimum and maximum places, tap to place — is unchanged.

## Changing a budget on a live survey

Renaming items, descriptions, icons, the rule, the minimum and a group's title change in place. The total, the unit, the step, the mode, an item's cost, a group's total and a map question's price change what the stored answers mean, so they go to [unpublished changes](/how-to/edit-a-published-survey/).

## Result

**Responses** shows a bar per item: the average share (split), the share of respondents who funded each project with the set that fits the budget in green (projects), and, for a budget group, one block with the marks, metres or m² per question, what they cost and the share of spend — the marks themselves are on the **Map** as always. Every export has one column per item and a total; a priced mark carries `cost` in the GeoJSON and GIS files, and each respondent's row has a `spent` column per budget group. You can add the question to [public results](/how-to/share-results-publicly/); items with fewer respondents than the privacy threshold are masked.
