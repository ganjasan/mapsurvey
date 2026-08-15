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
    ("display", "Display blocks — collect nothing"),
)

# input_type value -> presentation. `label` overrides the model's choice label
# where set; icons are Font Awesome 5 classes (the version the editor loads).
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
    "point":       {"group": "geo", "icon": "fa-map-marker-alt",
                    "hint": "Respondent places a marker on the map"},
    "line":        {"group": "geo", "icon": "fa-route",
                    "hint": "Respondent draws a route or line"},
    "polygon":     {"group": "geo", "icon": "fa-draw-polygon",
                    "hint": "Respondent outlines an area"},
    "image":       {"group": "display", "icon": "fa-image",
                    "hint": "Shows a picture to the respondent — collects nothing"},
    "html":        {"group": "display", "icon": "fa-paragraph",
                    "label": "Formatted Text",
                    "hint": "Your own formatted text — headings, bold, links; collects nothing"},
}

# Types whose Color / Icon class settings reach the respondent (map markers).
GEO_TYPES = ("point", "line", "polygon")

# Types that render content but collect no answer, so cannot be required.
DISPLAY_BLOCK_TYPES = ("image", "html")


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
