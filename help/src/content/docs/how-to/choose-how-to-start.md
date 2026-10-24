---
title: Choose how to start a survey
description: Pick between the Wizard, an empty survey and your own AI assistant, make one of them your default in Preferences, and understand where the map opens.
sidebar:
  order: 2
---

You end up knowing what each card on the **How do you want to start?** page does, how to skip the page once you have a favourite, and why a new survey's map opens where it does.

## Before you start

- You need the editor role or higher in the workspace; viewers do not see **New Survey**.

## Steps

1. Click **New Survey** on the dashboard. On a workspace with no surveys yet, Mapsurvey opens this page by itself.
2. Click a card. One click is enough; there is nothing to confirm:
   - **Start from scratch** creates an empty survey and opens the editor. The survey is called **Untitled survey** (rename it in the editor header) and runs in your interface language.
   - **Survey wizard** (marked **Best to start**) takes you to the brief: describe what you want to find out in one sentence and the Wizard drafts sections, questions and translations for you to edit. The Wizard is an AI agent: your description goes to an AI provider to build the draft; survey answers never do. **Start another way** on that page brings you back here.
   - **Use your AI assistant** connects Mapsurvey to the assistant you already use — Claude, ChatGPT, Gemini, Le Chat, Perplexity, Cursor, VS Code and others — and then lets you ask it for a survey from the chat. Pick your assistant's tile: Claude, Cursor and VS Code take one button, the others a few steps, and the page notices by itself when you are connected. Then write what you want to find out and open the prompt in your assistant; the survey appears on your dashboard. If your assistant cannot connect to outside tools, the page says so and offers the Survey wizard instead. Step-by-step: [Use the MCP server](/how-to/use-the-mcp-server/).
3. To skip this page in future, open the account menu, click **Preferences**, choose your usual way under **When I click New Survey** and click **Save**. **New Survey** then goes straight to that path. Choose **Ask every time** to get this page back.
4. To see the page once without changing your default, open the ⋯ menu on the dashboard and click **Start another way…**. The page names your current default with a link to **Preferences**.

## Where the map opens

A new survey's map starts as close to you as Mapsurvey can tell without asking anything you have not agreed to, in this order:

| Source | When it applies |
|---|---|
| Your location | Your browser has allowed Mapsurvey to use it. **Start from scratch** asks on the click when it has not asked before; the create page offers **Use my location** under the map instead of asking on load. |
| Your workspace's last survey | The newest survey in the workspace that has a map position. |
| Your country | Read from the connection; a country-wide view at a low zoom. |
| The world | Nothing better is known. |

Whatever the start, you frame the map yourself afterwards: on the create page before generating a draft, or in the editor under **Map Position** and **Survey settings**.

## Result

**New Survey** either asks how you want to start or, once you set a default, opens your preferred path directly, and the map of a new survey opens near you rather than on a fixed city.

## Related

- [Create a survey](/start-here/create-a-survey/)
- [The Wizard couldn't finish your draft](/troubleshooting/ai-draft-failed/)
- [Translate a survey](/how-to/translate-a-survey/)
