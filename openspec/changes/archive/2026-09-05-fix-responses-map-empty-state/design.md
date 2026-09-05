# Design: fix-responses-map-empty-state

One boolean in the dashboard context, `has_geo_questions = survey.geo_questions().exists()`,
branches the existing empty block. No new template, no JS: the block is server-rendered and
the pane's map only mounts when features or layers exist, which is unchanged. The legacy
dashboard gets the same branch so the two never disagree.
