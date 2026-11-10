"""Budget questions (change budget-question, issue #447): the settings record,
the items and the amounts.

Two things live here. The `budget` question (mode `split` or `projects`)
stores one `Answer` row per respondent with the allocation in
`Answer.allocation`. A BUDGET GROUP (`QuestionGroup.budget`) puts a budget over
the ordinary geo questions it contains: each of them carries a PRICE
(`validation_settings['price']`, per mark, per metre or per square metre) and
the respondent places marks until the budget is spent — geo questions keep
every behaviour they have, the budget only bounds how much goes down.

Everything that reads or validates a budget record goes through
`normalise_budget_settings()`, every price through `normalise_price()`, every
amount shown through `format_amount()`, and the cost of a stored geometry
through `feature_cost()` — the respondent bar, the section POST, Responses, the
export and the paper form all agree because they share these.
"""
import math
from decimal import Decimal, InvalidOperation

from django.utils.translation import gettext as _

MODE_SPLIT = "split"
MODE_PROJECTS = "projects"
MODES = (MODE_SPLIT, MODE_PROJECTS)
MODE_CHOICES = (
    (MODE_SPLIT, "Split a budget"),
    (MODE_PROJECTS, "Choose projects within a budget"),
)

UNIT_CURRENCY = "currency"
UNIT_POINTS = "points"
UNIT_PERCENT = "percent"
UNITS = (UNIT_CURRENCY, UNIT_POINTS, UNIT_PERCENT)
UNIT_CHOICES = (
    (UNIT_CURRENCY, "Currency"),
    (UNIT_POINTS, "Points"),
    (UNIT_PERCENT, "Per cent"),
)

RULE_ALL = "all"      # the whole budget must be allocated (split only)
RULE_UPTO = "upto"    # up to the budget
RULES = (RULE_ALL, RULE_UPTO)
RULE_CHOICES = (
    (RULE_ALL, "Must allocate the whole budget"),
    (RULE_UPTO, "Can allocate up to the budget"),
)

SOURCE_LIST = "list"
SOURCE_LAYER = "layer"
SOURCES = (SOURCE_LIST, SOURCE_LAYER)

# What a geo question's price is per (change budget-question): one mark, one
# metre of a line, one square metre of an area.
PER_FEATURE = "feature"
PER_LENGTH = "length"
PER_AREA = "area"
PERS = (PER_FEATURE, PER_LENGTH, PER_AREA)
PER_CHOICES = (
    (PER_FEATURE, "per mark"),
    (PER_LENGTH, "per metre"),
    (PER_AREA, "per square metre"),
)
# Which pricing a type can carry: a line has a length, an area an area, a
# point or a cloud only a count.
PERS_BY_TYPE = {
    "point": (PER_FEATURE,),
    "line": (PER_FEATURE, PER_LENGTH),
    "polygon": (PER_FEATURE, PER_AREA),
    "spraycan": (PER_FEATURE, PER_AREA),
}
GROUP = "group"   # the `input_type` argument that means a group's budget

# Items without a colour of their own take turns on this palette — the SAME
# list as budget_question.js, so the row, the bar and the results agree.
PALETTE = ("#4f46e5", "#0891b2", "#16a34a", "#ca8a04", "#db2777", "#9333ea", "#ea580c", "#64748b")


def palette_color(index):
    return PALETTE[index % len(PALETTE)]

SYMBOL_MAX = 4
PROPERTY_MAX = 80
DEFAULT_STEP_DIVISOR = 20   # no step given: a twentieth of the total
PERCENT_TOTAL = 100
PERCENT_DEFAULT_STEP = 5

# Keys the record may carry, in the order the editor shows them.
KEYS = ("mode", "total", "unit", "symbol", "step", "rule", "min_items", "show_shares",
        "source", "cost_property")


class BudgetSettingsError(ValueError):
    """A settings record that cannot be made valid; `field` names the key."""

    def __init__(self, field, message):
        super().__init__(message)
        self.field = field


def _num(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = value
    elif isinstance(value, str):
        try:
            number = float(value.strip().replace(",", "").replace(" ", ""))
        except ValueError:
            return None
    else:
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return int(number) if float(number).is_integer() else float(number)


def normalise_budget_settings(raw, input_type="budget"):
    """The one validator of `validation_settings['budget']`.

    Returns a clean dict or raises `BudgetSettingsError(field, message)`. The
    form, the ZIP import and the API all call it, so a record that saves is a
    record the respondent page can render. `input_type` decides whether `mode`,
    `rule` and `source` belong: `budget_items` has a catalogue and a total only.
    """
    raw = dict(raw or {})
    clean = {}
    is_group = input_type == GROUP

    if not is_group:
        mode = raw.get("mode") or MODE_SPLIT
        if mode not in MODES:
            raise BudgetSettingsError("mode", "Pick how the budget is used: split or projects.")
        clean["mode"] = mode

    unit = raw.get("unit") or UNIT_CURRENCY
    if unit not in UNITS:
        raise BudgetSettingsError("unit", "Unit must be currency, points or per cent.")
    clean["unit"] = unit

    total = _num(raw.get("total"))
    if unit == UNIT_PERCENT:
        total = PERCENT_TOTAL
    if total is None or total <= 0:
        raise BudgetSettingsError("total", "Enter the total budget as a positive number.")
    clean["total"] = total

    symbol = raw.get("symbol") or ""
    symbol = symbol.strip()[:SYMBOL_MAX] if isinstance(symbol, str) else ""
    clean["symbol"] = "" if unit != UNIT_CURRENCY else symbol

    if is_group:
        # A group's budget has no step: marks cost what their price says.
        return clean

    step = _num(raw.get("step"))
    if step is None:
        step = PERCENT_DEFAULT_STEP if unit == UNIT_PERCENT else _default_step(total)
    if step <= 0:
        raise BudgetSettingsError("step", "The step must be a positive number.")
    if step > total:
        raise BudgetSettingsError("step", "The step cannot be larger than the total budget.")
    clean["step"] = step

    if True:
        rule = raw.get("rule") or RULE_ALL
        if rule not in RULES:
            raise BudgetSettingsError("rule", "The rule must be all or upto.")
        # Projects have no "spend it all": costs rarely sum to the total exactly.
        clean["rule"] = rule if clean["mode"] == MODE_SPLIT else RULE_UPTO

        source = raw.get("source") or SOURCE_LIST
        if source not in SOURCES:
            raise BudgetSettingsError("source", "Items come from a list or from a layer.")
        clean["source"] = source
        prop = raw.get("cost_property") or ""
        prop = prop.strip()[:PROPERTY_MAX] if isinstance(prop, str) else ""
        if source == SOURCE_LAYER and not prop:
            raise BudgetSettingsError("cost_property", "Name the object property that holds the cost.")
        clean["cost_property"] = prop if source == SOURCE_LAYER else ""

    min_items = _num(raw.get("min_items"))
    if min_items is None:
        min_items = 0
    if not float(min_items).is_integer() or min_items < 0:
        raise BudgetSettingsError("min_items", "Minimum items must be a whole number, 0 or more.")
    clean["min_items"] = int(min_items)

    clean["show_shares"] = bool(raw.get("show_shares", False))
    return clean


def _default_step(total):
    step = total / DEFAULT_STEP_DIVISOR
    return int(step) if float(step).is_integer() else step


def settings_of(question):
    """The question's normalised record, or None for a non-budget question or a
    record that fails validation (an old row edited by hand)."""
    if question.input_type != "budget":
        return None
    raw = (question.validation_settings or {}).get("budget")
    try:
        return normalise_budget_settings(raw, question.input_type)
    except BudgetSettingsError:
        return None


def group_settings(group):
    """A budget group's normalised record, or None for an ordinary group."""
    if group is None or not group.budget:
        return None
    try:
        return normalise_budget_settings(group.budget, GROUP)
    except BudgetSettingsError:
        return None


# ── Prices on geo questions ───────────────────────────────────────────────────

def normalise_price(raw, input_type):
    """`{"amount", "per"}` for a geo question, None when there is no price.
    An amount of zero or less, a non-number, or a `per` the type cannot
    measure (a point priced per metre) is no price."""
    if not isinstance(raw, dict):
        return None
    amount = _num(raw.get("amount"))
    if amount is None or amount <= 0:
        return None
    per = raw.get("per") or PER_FEATURE
    if per not in PERS_BY_TYPE.get(input_type, ()):
        return None
    return {"amount": amount, "per": per}


def price_of(question):
    """The question's price, or None."""
    return normalise_price((question.validation_settings or {}).get("price"), question.input_type)


def format_price(price, settings):
    """"£2k each", "£50 / m", "£30 / m²" — the caption under a draw button."""
    if not price:
        return ""
    amount = format_amount(price["amount"], settings)
    if price["per"] == PER_LENGTH:
        return _("%(amount)s / m") % {"amount": amount}
    if price["per"] == PER_AREA:
        return _("%(amount)s / m²") % {"amount": amount}
    return _("%(amount)s each") % {"amount": amount}


def measure(geometry, per):
    """How much of a stored geometry a price applies to: 1 per feature,
    metres along a line, square metres of an area. Web Mercator corrected
    by cos(lat) (lengths) or cos²(lat) (areas), the way spray.cloud_area_m2
    does — exact enough for a park, and no extra projection library."""
    if per == PER_FEATURE:
        return 1
    if geometry is None or geometry.empty:
        return 0.0
    g = geometry.clone()
    if g.srid is None:
        g.srid = 4326
    lat = g.centroid.y
    g.transform(3857)
    if per == PER_LENGTH:
        return g.length * math.cos(math.radians(lat))
    if per == PER_AREA:
        if g.geom_type == "MultiPoint":
            g = g.convex_hull
        if g.geom_type != "Polygon":
            return 0.0
        return g.area * math.cos(math.radians(lat)) ** 2
    return 0.0


def feature_cost(price, geometry):
    """What one stored mark costs under `price` (0 without a price)."""
    if not price:
        return 0
    return price["amount"] * measure(geometry, price["per"])


class GroupSpend:
    """Running tally of a budget group during a section POST (design D6): the
    member questions' marks are judged in the order they were stored and the
    ones that do not fit are dropped — a clamp like `max_features`, because
    the widget never posts them and the POST has no error path."""

    def __init__(self, group):
        self.settings = group_settings(group) or {}
        self.left = self.settings.get("total") or 0
        self.prices = {q.id: price_of(q) for q in group.members()}

    def admit(self, question_id, geometry):
        cost = feature_cost(self.prices.get(question_id), geometry)
        if cost > self.left + 1e-9:
            return False
        self.left -= cost
        return True


def is_multiple(amount, step):
    """`amount` is a whole number of `step`s (float-safe)."""
    try:
        ratio = Decimal(str(amount)) / Decimal(str(step))
    except (InvalidOperation, ZeroDivisionError):
        return False
    return ratio == ratio.to_integral_value()


def round_to_step(amount, step):
    """`amount` rounded to the nearest multiple of `step`."""
    if step <= 0:
        return amount
    q = Decimal(str(amount)) / Decimal(str(step))
    value = q.to_integral_value() * Decimal(str(step))
    return int(value) if value == value.to_integral_value() else float(value)


def items_of(question, language=None):
    """The items the respondent allocates to, in order, as dicts
    `{code, name, description, cost, max_count, selectable}` with codes as strings.

    List source: the question's `choices` with the budget extras. Layer source
    (`budget` only): the bound layer's objects — key, title, description and the
    numeric value under `cost_property`; an object without one is listed but not
    selectable. Costs are None where not set.
    """
    settings = settings_of(question) or {}
    if question.input_type == "budget" and settings.get("source") == SOURCE_LAYER:
        return _layer_items(question, settings.get("cost_property") or "")
    items = []
    for index, choice in enumerate(question.choices or []):
        if not isinstance(choice, dict) or "code" not in choice:
            continue
        code = str(choice["code"])
        name = question.get_choice_name(choice["code"], language) or code
        cost = choice.get("cost")
        translated = choice.get("description_i18n") or {}
        items.append({
            "code": code,
            "name": name,
            "description": (translated.get(language) if language else "") or choice.get("description") or "",
            "icon": choice.get("icon") or "",
            # Every item has a colour: the creator's, else the palette's — it is
            # how the respondent reads the stacked bar (owner, 2026-11-10).
            "color": choice.get("color") or palette_color(index),
            "cost": cost,
            "selectable": True,
        })
    return items


def _layer_items(question, cost_property):
    if not question.layer_id:
        return []
    from survey.models import LayerObject
    items = []
    objects = LayerObject.objects.filter(layer_id=question.layer_id).order_by("position", "id")
    for index, obj in enumerate(objects):
        props = obj.properties if isinstance(obj.properties, dict) else {}
        cost = _num(props.get(cost_property)) if cost_property else None
        if cost is not None and cost < 0:
            cost = None
        items.append({
            "code": obj.key,
            "name": obj.title or obj.key,
            # Sanitised creator HTML (object editor); the respondent list renders it as markup.
            "description": obj.description or "",
            "icon": "",
            "color": palette_color(index),
            "cost": cost,
            "selectable": cost is not None,
            "object_id": obj.id,
        })
    return items


def items_by_code(question, language=None):
    return {item["code"]: item for item in items_of(question, language)}


def amount_field(question_code, item_code):
    """Name of the Split amount input of one item: `<question>__<item>`."""
    return f"{question_code}__{item_code}"


def parse_submission(question, post):
    """The `Answer.allocation` a section POST asks to store for a `budget`
    question, or None to store nothing.

    The section POST has no error-render path (the client blocks Next and says
    why); a submission the widget cannot produce — over the budget, off the
    step, short of the whole budget under `all`, an item that is not
    selectable — is tampering or a bug and is stored as nothing, the way an
    invalid ranking is. Unknown items are ignored: only the question's own
    items are read.
    """
    settings = settings_of(question)
    if settings is None:
        return None
    items = items_of(question)
    total = settings["total"]
    if settings["mode"] == MODE_SPLIT:
        chosen = {}
        for item in items:
            raw = post.get(amount_field(question.code, item["code"]))
            if raw is None or str(raw).strip() == "":
                continue
            amount = _num(raw)
            if amount is None or amount < 0 or not is_multiple(amount, settings["step"]):
                return None
            if amount > 0:
                chosen[item["code"]] = amount
        if not chosen:
            return None
        used = sum(chosen.values())
        if used > total or (settings["rule"] == RULE_ALL and used != total):
            return None
        return {"total": total, "items": chosen}

    picked = []
    for value in post.getlist(question.code):
        value = str(value).strip()
        if value and value not in picked:
            picked.append(value)
    by_code = {item["code"]: item for item in items}
    chosen = {}
    for code in picked:
        item = by_code.get(code)
        if item is None:
            continue
        if not item["selectable"] or item["cost"] is None:
            return None
        chosen[code] = item["cost"]
    if not chosen or sum(chosen.values()) > total:
        return None
    return {"total": total, "items": chosen}


def spent(allocation):
    """Sum of an `Answer.allocation` record's items."""
    items = (allocation or {}).get("items") or {}
    total = 0
    for value in items.values():
        number = _num(value)
        if number is not None:
            total += number
    return total


def format_amount(amount, settings, compact=True):
    """"£20M", "£2.5M", "£500k", "£250", "35 pts", "40%" — one spelling everywhere.

    `compact` shortens millions and thousands (the respondent bar, headers);
    the export writes raw numbers and does not call this.
    """
    if amount is None:
        return ""
    settings = settings or {}
    unit = settings.get("unit", UNIT_CURRENCY)
    symbol = settings.get("symbol", "") or ""
    number = _num(amount)
    if number is None:
        return str(amount)
    if unit == UNIT_PERCENT:
        return f"{_trim(number)}%"
    body = _compact(number) if compact else _group(number)
    if unit == UNIT_POINTS:
        return f"{body} pts"
    return f"{symbol}{body}"


def _trim(number):
    if float(number).is_integer():
        return str(int(number))
    text = f"{number:.2f}".rstrip("0").rstrip(".")
    return text


def _compact(number):
    sign = "-" if number < 0 else ""
    value = abs(number)
    if value >= 1_000_000:
        return f"{sign}{_trim(value / 1_000_000)}M"
    if value >= 10_000:
        return f"{sign}{_trim(value / 1_000)}k"
    # Whole units: a price per metre gives fractions nobody wants to read.
    return f"{sign}{_group(round(value))}"


def _group(number):
    if float(number).is_integer():
        return f"{int(number):,}".replace(",", " ")
    whole, frac = f"{number:.2f}".split(".")
    return f"{int(whole):,}".replace(",", " ") + "." + frac.rstrip("0")
