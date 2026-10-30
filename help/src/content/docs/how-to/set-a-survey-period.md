---
title: Set a survey period
description: Open a survey on a set date and close it by itself on another, without anyone remembering the day.
sidebar:
  order: 16
---

You end up with a survey that respondents can answer only between two moments you chose: before
the start they see a page that says when it opens, after the end they see the closed page, and the
survey closes on its own.

## Before you start

- You are the **owner** of the survey (the period is a Settings control).
- You know the time zone the dates are meant in. The Settings block names the zone it uses:
  the one in your browser the first time you set a period, kept afterwards so a colleague in
  another zone does not shift the times.

## Steps

1. Open the survey and choose **Settings** in the sidebar.
2. In **Survey period**, fill **Opens on**, **Closes on**, or both. Leave a box empty for no limit.
3. The block saves by itself. The status chip at the top now reads **Open · Opens 3 Nov, 09:00**
   or **Open · Closes 1 Nov, 23:59**.
4. **Publish** the survey as usual if it is not published yet. The period does nothing for a draft
   or a testing survey.

## What respondents see

- **Before the start**: a page with the survey's name and "It opens on 3 Nov 2026, 09:00
  (Europe/Berlin)". No answer is recorded, and search engines are told not to index the page.
- **Between the two**: the survey, as always.
- **After the end**: the closed page, from the first minute. Within five minutes the survey's
  status changes to **Closed** too, and the change is recorded in the survey's history like a
  manual close.

## Reopening

Pressing **Reopen** after an automatic close clears the past closing time, so the survey stays
open until you set a new one. If you closed the survey early by hand while the closing time was
still ahead, that time is kept and the survey closes then.

## Notes

- The end must be after the start, and a new end must be in the future.
- The period belongs to the live survey. Unpublished changes do not have one of their own, and
  publishing them does not change it.
- **Duplicate** and the backup file leave the period behind: a copy starts with none.
- Over the [REST API](/how-to/use-the-rest-api/) and the MCP server the fields are `opens_at`,
  `closes_at` and `schedule_timezone` on the survey.
