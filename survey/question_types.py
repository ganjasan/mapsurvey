"""Picker metadata for question input types.

Single source for how the question editor presents INPUT_TYPE_CHOICES: grouping,
icon, one-line hint, and display-label overrides. The template renders the card
grid from this structure; a parity test keeps it in step with the model, so a
type added to INPUT_TYPE_CHOICES without an entry here fails loudly instead of
silently missing from the dialog.

Display labels are presentation-only: `html` reads "Formatted Text" because
survey creators do not know what HTML means, but the stored input_type value is
untouched.
"""

# Group order is the order the dialog shows them in.
PICKER_GROUPS = (
    ("plain", "Questions"),
    ("geo", "Map questions"),
    ("files", "Files"),
    ("display", "Display blocks — collect nothing"),
)

# input_type value -> presentation. `label` overrides the model's choice label
# where set; icons are Font Awesome 5 classes (the editor loads 5.15.4).
PICKER_TYPES = {
    "text":        {"group": "plain", "icon": "fa-align-left",
                    "hint": "Multi-line free text answer"},
    "text_line":   {"group": "plain", "icon": "fa-i-cursor",
                    "hint": "One short line of text"},
    "number":      {"group": "plain", "icon": "fa-hashtag",
                    "hint": "Numeric answer with min/max validation"},
    "choice":      {"group": "plain", "icon": "fa-dot-circle",
                    "hint": "Pick one option from a list"},
    "multichoice": {"group": "plain", "icon": "fa-check-square",
                    "hint": "Pick any number of options"},
    "range":       {"group": "plain", "icon": "fa-sliders-h",
                    "hint": "Slider over a numbered scale"},
    "rating":      {"group": "plain", "icon": "fa-star",
                    "hint": "One point on a labelled scale — scores each item independently"},
    "ranking":     {"group": "plain", "icon": "fa-sort-amount-down",
                    "hint": "Respondent drags items into order — every rank used once"},
    "datetime":    {"group": "plain", "icon": "fa-calendar-alt",
                    "hint": "Date and time picker"},
    "thumbs":      {"group": "plain", "icon": "fa-thumbs-up",
                    "label": "Thumbs up / down",
                    "hint": "One tap: for or against — counted as up/down"},
    "point":       {"group": "geo", "icon": "fa-map-marker-alt",
                    "hint": "Respondent places a marker on the map"},
    "line":        {"group": "geo", "icon": "fa-route",
                    "hint": "Respondent draws a route or line"},
    "polygon":     {"group": "geo", "icon": "fa-draw-polygon",
                    "hint": "Respondent outlines an area"},
    "spraycan":    {"group": "geo", "icon": "fa-spray-can",
                    "label": "Spray area",
                    "hint": "Respondent sprays a fuzzy area with a brush — density shows confidence"},
    "layer_objects": {"group": "geo", "icon": "fa-map-marked-alt",
                    "label": "Objects on the map",
                    "hint": "Puts a reference layer on this section's map; add sub-questions to ask about each object"},
    "photo":       {"group": "files", "icon": "fa-camera",
                    "hint": "Respondent takes or uploads a photo"},
    "audio":       {"group": "files", "icon": "fa-microphone",
                    "hint": "Respondent records their voice or uploads audio"},
    "document":    {"group": "files", "icon": "fa-file-alt",
                    "hint": "Respondent attaches a document (PDF, Office)"},
    "image":       {"group": "display", "icon": "fa-image",
                    "hint": "Shows a picture to the respondent — collects nothing"},
    "html":        {"group": "display", "icon": "fa-paragraph",
                    "label": "Formatted Text",
                    "hint": "Your own formatted text — headings, bold, links; collects nothing"},
}

# Types whose Color / Icon class settings reach the respondent (map markers).
# `spraycan` (change spraycan-question-type) is the fourth: the respondent
# paints a cloud of dots instead of drawing a shape.
GEO_TYPES = ("point", "line", "polygon", "spraycan")

# The ONE map from a geo input type to the `Answer` column that holds its
# geometry. Before `spraycan` the column was named after the type and a dozen
# call sites relied on it (`getattr(answer, input_type)`,
# `f"{input_type}__isnull"`, `a.point or a.line or a.polygon`); a spray cloud is
# a MultiPoint in `Answer.multipoint`, so the convention is gone. Use
# `geo_column()` / `Answer.geometry`, never a literal.
GEO_COLUMNS = {
    "point": "point",
    "line": "line",
    "polygon": "polygon",
    "spraycan": "multipoint",
}


def geo_column(input_type):
    """`Answer` field name holding the geometry of a geo question, or None."""
    return GEO_COLUMNS.get(input_type)


# Geo types a shared-map (`question`-sourced) reference layer may materialise
# from. Spray clouds are deliberately NOT a source: a layer object per cloud
# makes no sense and the sync keys objects per single-part geometry.
SHARED_MAP_SOURCE_TYPES = ("point", "line", "polygon")

# Geo types where a respondent may place several features (min/max_features
# in validation_settings). A spray cloud is one feature per respondent.
MULTI_FEATURE_TYPES = ("point", "line", "polygon")

# `spraycan` brush: a screen-pixel radius chosen by the creator in three sizes.
# Pixels, not metres, so zooming in paints finer (spec spraycan-question).
SPRAY_BRUSH_CHOICES = (
    ("small", "Small"),
    ("medium", "Medium"),
    ("large", "Large"),
)
SPRAY_BRUSH_DEFAULT = "medium"
SPRAY_BRUSH_PX = {"small": 20, "medium": 40, "large": 70}

# Dots per spray cloud: NO product limit by default (owner decision
# 2026-10-04). A creator may set `validation_settings['max_dots']` on the
# question; the widget then stops emitting at it and the section POST keeps the
# first `max_dots`. SPRAY_HARD_CEILING is an abuse backstop for scripted POSTs
# only — a human cannot reach it (ten minutes of continuous spraying).
SPRAY_HARD_CEILING = 100000

# Types that put objects on the map and therefore own sub-questions: the
# respondent's own geometry (geo types) and the creator's layer objects. One
# mechanism, two entry points — see spec survey-editor "Sub-question management".
PARENT_TYPES = GEO_TYPES + ("layer_objects",)

# Types that need a map-layout section to mean anything.
MAP_ONLY_TYPES = PARENT_TYPES

# Types that render content but collect no answer, so cannot be required.
# `layer_objects` collects nothing itself either — its sub-questions do — and
# replaces `required` with its own minimum-objects rule.
DISPLAY_BLOCK_TYPES = ("image", "html")
NOT_REQUIRABLE_TYPES = DISPLAY_BLOCK_TYPES + ("layer_objects",)

# Types whose `choices` JSON is meaningful. Every other type must persist with
# choices=None; the editor, ZIP import and migration 0060 all enforce this
# together, because stale choices on e.g. a point question once rerouted its
# GeoJSON payload into the choice parser (int()) — a 500 on every submit.
# `thumbs` carries a FIXED two-choice list (THUMBS_CHOICES) written by the
# editor and never edited: that is what lets the whole choice-based stack
# (storage, export, analytics, visibility rules, public results) treat 👍/👎
# as a choice with two codes without a second aggregation path.
CHOICE_TYPES = ("choice", "multichoice", "range", "rating", "ranking", "thumbs")

THUMBS_UP, THUMBS_DOWN = 1, 0
THUMBS_CHOICES = [{"code": THUMBS_UP, "name": "up"}, {"code": THUMBS_DOWN, "name": "down"}]


def picker_groups_for(choices):
    """Group `choices` (an input_type choices iterable, e.g. the form field's —
    already filtered for sub-questions) for the picker template.

    Returns [(group_label, [{value, label, icon, hint}, ...]), ...] with empty
    groups dropped. Within a group, types follow PICKER_TYPES order — the
    model's choice order has drifted (text_line sits after image) and this is
    where it gets fixed for display. Unknown values are skipped rather than
    crashing the dialog; the parity test is what guards completeness.
    """
    allowed = {value: model_label for value, model_label in choices}
    by_group = {key: [] for key, _ in PICKER_GROUPS}
    for value, meta in PICKER_TYPES.items():
        if value not in allowed:
            continue
        by_group[meta["group"]].append({
            "value": value,
            "label": meta.get("label", allowed[value]),
            "icon": meta["icon"],
            "hint": meta["hint"],
        })
    return [(label, by_group[key]) for key, label in PICKER_GROUPS if by_group[key]]
