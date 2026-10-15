---
title: The Wizard couldn't finish your draft
description: The Wizard (Mapsurvey's AI agent) ended with an error instead of opening the editor.
sidebar:
  order: 20
---

You clicked **Generate draft**, waited on **Building your survey…**, and got one of: **The Wizard couldn't be reached. Try again, or create an empty survey.**, **The draft came back malformed. Try rephrasing your brief, or create an empty survey.**, **The Wizard isn't available right now — create an empty survey instead.**, or **Something went wrong generating the draft.**

## Why it happens

The Wizard is an AI agent: your brief goes to an AI provider, which writes the sections and questions. Mapsurvey checks the result before saving anything; only a draft that passes becomes a survey. Each message points at a different stage.

- **The Wizard couldn't be reached.** The provider timed out, refused the request or returned an error. It also appears when the answer was cut off twice in a row because the brief asks for more survey than fits in one answer.
- **The draft came back malformed.** The provider answered, but the draft failed Mapsurvey's checks twice. A corrected draft is requested once automatically; a second failure is reported instead of saved.
- **The Wizard isn't available right now.** No AI provider is configured on this installation. On a self-hosted instance the provider key is not set.
- **Something went wrong.** An unexpected error, already reported to the team.

There is no limit on drafts on any plan, so running out of allowance is never the cause.

## What to do

1. Close the message. Your brief is still in the form.
2. Click **Generate draft** again; a provider error is usually temporary.
3. If it fails a second time, shorten the brief: say what you want to learn and from whom, and ask for fewer sections. Keep the list of survey languages short on the first attempt; you can [add translations later](/how-to/translate-a-survey/).
4. If you left the page while it was generating, open your dashboard. The draft is created even when the tab is closed, and a finished survey is waiting there.
5. If you need the survey now, build it by hand: click **Start another way** (or **Create empty**, when the page shows it) and choose **Start from scratch**; [Start here](/start-here/) walks through the first survey.
6. On a self-hosted instance, set the provider credentials described in the project README and restart.

## If it keeps happening

[Contact support](https://mapsurvey.org/?support=1) with the exact message, the time of the attempt, the languages you selected and the brief. Failed attempts are logged, so the time lets us find yours.
