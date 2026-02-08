---
name: new-resource
description: Analyze a web resource and save it to docs/resources/ as an Obsidian-compatible markdown file. Use when the user provides a URL to add to the knowledge base.
license: MIT
metadata:
  author: mapsurvey
  version: "1.0"
arguments:
  - name: url
    description: URL of the resource to analyze and save
    required: true
---

Fetch, analyze, and save a web resource to the knowledge base.

**Output location**: `docs/resources/<generated-slug>.md`

## Steps

### 1. Validate URL

Check that the `$ARGUMENTS` contains a valid URL. If not provided or invalid, ask the user:
> "Please provide a URL to analyze (e.g., https://example.com/article)"

### 2. Fetch and analyze content

Use **WebFetch** to retrieve the page content with this prompt:
> "Extract all main content from this page. Include: title, description/summary, all tools/software/datasets/resources mentioned with their descriptions and links, any categories or sections, key concepts. Preserve all URLs. Identify the main topic and subtopics."

### 3. Determine filename

Generate a slug from the page title or main topic:
- Convert to lowercase
- Replace spaces with hyphens
- Remove special characters
- Keep it concise (max 50 chars)

Example: "Open Source GIS Resources" → `open-source-gis-resources.md`

### 4. Generate tags

Based on the content, generate 4-8 relevant tags. Common tag categories:
- **Type**: `datasets`, `tools`, `methodology`, `tutorial`, `reference`, `case-study`
- **Domain**: `ppgis`, `gis`, `participatory-mapping`, `urban-research`, `ecosystem-services`
- **Tech**: `open-source`, `python`, `web-platform`, `mobile`
- **Geography**: `european-cities`, `finland-research`, `global`

### 5. Create markdown file

Write to `docs/resources/<slug>.md` with this structure:

```markdown
---
title: <Page Title>
source: <Original URL>
date_added: <Current date YYYY-MM-DD>
tags:
  - tag1
  - tag2
  - tag3
---

# <Page Title>

> <Brief summary/description of the resource - 1-2 sentences>

**Source:** [<Domain or Site Name>](<Original URL>)

---

## <Main Section 1>

### <Item Name>
<Description of the item/tool/dataset>

- **Link:** [<Link Text>](<URL>)
- **Type:** <Category if applicable>
- **Related:** [[potential-related-topic]], [[another-topic]]

### <Item Name 2>
...

---

## <Main Section 2>
...

---

## See Also

- [[related-resource-1]]
- [[related-resource-2]]
- [[related-resource-3]]
```

### 6. Format guidelines

**YAML Frontmatter:**
- `title`: Clean page title
- `source`: Original URL (verbatim)
- `date_added`: Current date in YYYY-MM-DD format
- `tags`: List of lowercase, hyphenated tags

**Content Structure:**
- Start with blockquote summary
- Source link with domain name as text
- Organize content into logical sections with `##` headers
- Use `###` for individual items/resources
- Include tables for lists of similar items
- Add metadata (Link, Type, Language, etc.) as bullet points

**Obsidian Links:**
- Use `[[topic-name]]` format for potential cross-references
- Add to "Related" field for each item where applicable
- Include "See Also" section at bottom with 2-5 related topics
- Link names should be lowercase, hyphenated, descriptive

**Tables:**
Use markdown tables when listing multiple similar items:
```markdown
| Name | Year | Link |
|------|------|------|
| Item 1 | 2023 | [Source](url) |
```

### 7. Check for existing file

Before writing, check if `docs/resources/<slug>.md` exists:
- If exists, ask user: "A file with this name already exists. Overwrite it?"
- If user declines, ask for alternative filename

### 8. Confirm creation

After writing the file, output:
```
Created: docs/resources/<filename>.md

Tags: #tag1, #tag2, #tag3

Summary:
- <Number> datasets/tools/resources documented
- <Key topics covered>

Obsidian links added for: [[topic1]], [[topic2]], ...
```

## Example Session

```
User: /new-resource https://example.org/gis-tools

Claude: Fetching https://example.org/gis-tools...

Created: docs/resources/gis-tools-collection.md

Tags: #gis, #tools, #open-source, #mapping

Summary:
- 8 tools documented
- Topics: desktop GIS, web mapping, data processing

Obsidian links added for: [[qgis]], [[leaflet]], [[postgis]]
```

## Guardrails

- Always fetch the URL before generating content - never make up information
- Preserve all original URLs from the source
- Keep descriptions factual, based on source content
- Generate meaningful tags based on actual content
- Use consistent Obsidian link naming: lowercase, hyphenated
- If WebFetch fails, inform user and ask for alternative URL
- Never include paywalled/login-required content warnings as main content
- Ensure `docs/resources/` directory exists before writing
