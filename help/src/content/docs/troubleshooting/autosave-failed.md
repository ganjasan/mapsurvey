---
title: Not saved — tap to retry
description: The autosave indicator in the editor turned red and your last edit did not reach the server.
sidebar:
  order: 10
---

While you were editing a question, the survey settings, the thanks page or the public results page, the indicator that normally reads **All changes saved** turned red: **Not saved — tap to retry**, **Not saved (offline?) — tap to retry**, or **Not saved —** followed by a field name and a reason.

## Why it happens

These panels have no Save button: every change is sent to the server a moment after you make it, and the indicator shows the outcome of the last send. It fails in three ways.

- **The server did not accept a value.** The message names the field and the reason, for example **Not saved — Redirect URL: Enter a valid URL.** Retrying would send the same value, so the indicator offers no retry.
- **The request did not get through.** A dropped connection, a laptop that went to sleep, or a session that expired while the tab was open. The message ends in **tap to retry**.
- **The change would alter the structure of a live survey.** On a survey that is collecting responses, adding or removing questions or changing a question's type is done in unpublished changes. The message starts with **Changing …** and says so.

## What to do

1. If the message names a field, correct that value. The indicator returns to **All changes saved** once the corrected value is accepted.
2. If the message ends in **tap to retry**, check that you are online, then click or tap the indicator to re-send the change.
3. If retrying fails again, copy any long text from the field that failed, then reload the page. If the page asks you to sign in, your session had expired; sign in and repeat the edit.
4. If the message says the change would alter the structure of a live survey, click **✎ Edit** in the toolbar and make the edit in the unpublished changes. Respondents keep the current survey until you click **🌐 Publish changes**.

Everything the indicator reported as saved is on the server; only the failed change is not.

## If it keeps happening

[Contact support](https://mapsurvey.org/?support=1) with the exact text of the indicator, which panel you were in (question, survey settings, thanks page or public results), the survey's name, and whether the survey was published at the time. If a field is named, say what value you entered.
