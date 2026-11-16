"""The Reports module (Platform Vision v0.4, epic #712): a report is a workspace object whose blocks
read datasets of the Data module. It owns no answers; every number goes through `data.aggregate`.

    models.py        Report, ReportBlock
    sources.py       which dataset and question a block reads
    render.py        per-block payloads, live cache, freeze / unfreeze, the survey's first draft
    services.py      every write, with an Actor
    editor_views.py  the configuration screens (until the story editor, #704)
    views.py         /r/<slug>/ and the Reports list
"""
