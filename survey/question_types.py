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
import re

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
    "budget":      {"group": "plain", "icon": "fa-coins",
                    "label": "Budget",
                    "hint": "Respondent splits a fixed budget between items, or picks projects until it runs out"},
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

# Who a section, group or question is for (change operator-entry, spec
# question-audience). The administrator decides; the visibility engine enforces
# it per surface: the respondent link evaluates `respondent`, the operator entry
# form `operator`. A container's audience narrows its members' (intersection).
AUDIENCE_EVERYONE = "everyone"
AUDIENCE_RESPONDENTS = "respondents"
AUDIENCE_OPERATORS = "operators"
AUDIENCES = (AUDIENCE_EVERYONE, AUDIENCE_RESPONDENTS, AUDIENCE_OPERATORS)
AUDIENCE_CHOICES = (
    (AUDIENCE_EVERYONE, "Everyone"),
    (AUDIENCE_RESPONDENTS, "Respondents only"),
    (AUDIENCE_OPERATORS, "Operators only"),
)
SURFACE_RESPONDENT = "respondent"
SURFACE_OPERATOR = "operator"
_AUDIENCE_SURFACES = {
    AUDIENCE_EVERYONE: {SURFACE_RESPONDENT, SURFACE_OPERATOR},
    AUDIENCE_RESPONDENTS: {SURFACE_RESPONDENT},
    AUDIENCE_OPERATORS: {SURFACE_OPERATOR},
}


def audience_allows(audience, surface):
    """True when an item of ``audience`` is shown on ``surface``. Unknown or
    empty audiences read as `everyone` (fail open, like broken rules)."""
    return surface in _AUDIENCE_SURFACES.get(audience or AUDIENCE_EVERYONE, _AUDIENCE_SURFACES[AUDIENCE_EVERYONE])


def normalise_audience(value):
    """A stored/imported value, or `everyone` when it is not one of AUDIENCES."""
    return value if value in AUDIENCES else AUDIENCE_EVERYONE


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


def section_geo_count(section, with_question=None):
    """Top-level geo questions in a section — the count the tap-to-place rule
    reads. Sub-questions and every non-geo type do not count.

    `with_question` counts that question as present whether or not it is
    saved yet: the editor's live preview renders an unsaved draft."""
    qs = section.question_set.filter(parent_question_id=None, input_type__in=GEO_TYPES)
    if with_question is None:
        return qs.count()
    if with_question.pk:
        qs = qs.exclude(pk=with_question.pk)
    return qs.count() + (1 if with_question.input_type in GEO_TYPES else 0)


def tap_to_place_active(question, geo_count):
    """True when a map click places this question's mark (spec
    point-tap-to-place): a top-level `point` question with the setting on,
    and the only geo question on its section. Static on purpose — a second
    geo question hidden by a visibility rule still counts, so the editor
    badge and the respondent page always agree."""
    return (question.input_type == "point"
            and bool(getattr(question, "tap_to_place", False))
            and question.parent_question_id_id is None
            and geo_count == 1)

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
# `budget` (change budget-question) carries its ITEMS in `choices` — the
# choices table, translations and import treat them as any option list — but
# never writes `selected_choices`: its answer is `Answer.allocation`.
CHOICE_TYPES = ("choice", "multichoice", "range", "rating", "ranking", "thumbs", "budget")
BUDGET_TYPES = ("budget",)

THUMBS_UP, THUMBS_DOWN = 1, 0
THUMBS_CHOICES = [{"code": THUMBS_UP, "name": "up"}, {"code": THUMBS_DOWN, "name": "down"}]

# The display styles each type accepts (spec choice-dropdown-display). ONE table:
# respondent rendering, the editor's save and preview, and ZIP import all read it,
# so the next style is one edit here. A stored value outside its type's tuple is
# unknown and renders the type's plain form. `default` on rating means "inherit
# the survey-wide rating style".
DISPLAY_STYLES_BY_TYPE = {
    "rating": ("default", "scale_strip", "list_pips", "stars"),
    "choice": ("default", "dropdown", "icon_grid"),
    "multichoice": ("default", "icon_grid"),
}


def allowed_display_styles(input_type):
    """The `display_style` values `input_type` accepts; `("default",)` for the rest."""
    return DISPLAY_STYLES_BY_TYPE.get(input_type, ("default",))


# Optional per-option keys the icon grid reads (spec inline-choices). Blank or
# non-string values are dropped so a survey that never uses the grid keeps
# byte-identical choices.
CHOICE_EXTRA_LIMITS = {"icon": 64, "group": 60, "description": 300}
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
# Question.color's model default: every existing question carries it, so on the
# icon grid it means "not set" and the tile keeps its grey glyph.
UNSET_QUESTION_COLOR = "#000000"


def normalise_choice_extras(choices):
    """Trim/cap/drop the `icon`, `group` and `color` keys on each choice. Mutates and returns.

    Every other key and the order are kept; non-dict entries pass through for the
    callers' own validation to judge.
    """
    for choice in choices or []:
        if not isinstance(choice, dict):
            continue
        for key, cap in CHOICE_EXTRA_LIMITS.items():
            if key not in choice:
                continue
            value = choice[key]
            value = value.strip()[:cap].strip() if isinstance(value, str) else ""
            if value:
                choice[key] = value
            else:
                del choice[key]
        # Icon colour (change icon-grid-color-picker): a #RRGGBB or nothing,
        # because it is written into an inline style on every respondent tile.
        if "color" in choice:
            value = choice["color"]
            value = value.strip() if isinstance(value, str) else ""
            if HEX_COLOR_RE.match(value):
                choice["color"] = value.lower()
            else:
                del choice["color"]
        # Budget item extras (change budget-question): a non-negative cost;
        # anything else is dropped, never refused here — whether a cost is
        # REQUIRED is the question form's call by mode.
        if "cost" in choice:
            cost = _number(choice["cost"])
            if cost is not None and cost >= 0:
                choice["cost"] = cost
            else:
                del choice["cost"]
        choice.pop("max_count", None)
        # Translated descriptions: {lang: text}, written only by the
        # Translations tab; the primary text stays in `description`.
        if "description_i18n" in choice:
            raw = choice["description_i18n"]
            clean = {}
            if isinstance(raw, dict):
                for lang, text in raw.items():
                    if isinstance(lang, str) and 0 < len(lang) <= 10 and isinstance(text, str) and text.strip():
                        clean[lang] = text.strip()[:CHOICE_EXTRA_LIMITS["description"]].strip()
            if clean:
                choice["description_i18n"] = clean
            else:
                del choice["description_i18n"]
    return choices


def _number(value):
    """A finite number from an int, float or numeric string; None otherwise.
    Booleans are not numbers here (`True` would read as a cost of 1)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip().replace(",", "").replace(" ", ""))
        except ValueError:
            return None
    else:
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return int(number) if number.is_integer() else number


# Types the picker marks with a Pro badge: the feature key `{% pro_badge %}`
# renders. None today: the map-side budget is a group setting (change budget-question).
PRO_FEATURE_BY_TYPE = {}

# Picker cards that are NOT input types (change budget-question): a budget
# group is a QuestionGroup with a budget, but creators look for it where the
# map questions are, so the "New question" picker offers it there and the card
# creates the group instead of a question (`action`). Offered only where the
# map questions are (a map section, top level); never in the type-switch
# picker of an existing question. Separate from PICKER_TYPES so the
# model/picker parity test stays about input types.
PICKER_ACTIONS = {
    "budget_group": {"group": "geo", "icon": "fa-coins", "label": "Budget group",
                     "hint": "A group of map questions with a budget: each gets a price, respondents place marks until the total is spent"},
}


def picker_groups_for(choices, unavailable=None, actions=False):
    """Group `choices` (an input_type choices iterable, e.g. the form field's —
    already filtered for sub-questions) for the picker template.

    Returns [(group_label, [{value, label, icon, hint}, ...]), ...] with empty
    groups dropped. Within a group, types follow PICKER_TYPES order — the
    model's choice order has drifted (text_line sits after image) and this is
    where it gets fixed for display. Unknown values are skipped rather than
    crashing the dialog; the parity test is what guards completeness.

    `unavailable` maps types left out of `choices` to `(model_label, reason)`
    — why they cannot be picked here; those come back with `disabled` and `reason` so the picker
    shows them greyed out instead of dropping them (a Form section's map types).
    `actions` adds PICKER_ACTIONS to their groups (the create picker only), disabled with the
    same reason when every input type of that group is.
    """
    allowed = {value: model_label for value, model_label in choices}
    unavailable = unavailable or {}
    by_group = {key: [] for key, _ in PICKER_GROUPS}
    for value, meta in PICKER_TYPES.items():
        if value in allowed:
            label, reason = meta.get("label", allowed[value]), None
        elif value in unavailable:
            model_label, reason = unavailable[value]
            label = meta.get("label", model_label)
        else:
            continue
        by_group[meta["group"]].append({
            "value": value,
            "label": label,
            "icon": meta["icon"],
            "hint": meta["hint"],
            "disabled": reason is not None,
            "reason": reason,
            "pro": PRO_FEATURE_BY_TYPE.get(value),
        })
    if actions:
        for value, meta in PICKER_ACTIONS.items():
            cards = by_group[meta["group"]]
            if not cards:
                continue   # the group is not offered here at all (a sub-question picker)
            reason = cards[0]["reason"] if all(c["disabled"] for c in cards) else None
            cards.append({
                "value": value, "label": meta["label"], "icon": meta["icon"], "hint": meta["hint"],
                "disabled": reason is not None, "reason": reason, "pro": meta.get("pro"),
                "action": value,
            })
    return [(label, by_group[key]) for key, label in PICKER_GROUPS if by_group[key]]
