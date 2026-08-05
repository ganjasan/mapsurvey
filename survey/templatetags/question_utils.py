from django import template

register = template.Library()

CARD_INPUT_TYPES = {'text', 'text_line', 'number', 'choice', 'multichoice', 'range', 'rating', 'datetime'}


@register.filter
def is_card_question(field):
    question_type = getattr(field.field.widget, 'question_type', None)
    return question_type in CARD_INPUT_TYPES


@register.filter
def question_type(field):
    return getattr(field.field.widget, 'question_type', '')


@register.filter
def rating_display_style(field):
    return getattr(field.field.widget, 'display_style', 'scale_strip')


# Styles that lay out one element per choice, and so share the scale partials.
CHOICE_BASED_STYLES = {'scale_strip', 'list_pips'}

# Types that can render through those partials. The style alone is not enough
# to decide: a text question would be sent through them and blow up on
# field.field.choices.
SCALE_STYLE_TYPES = {'rating', 'range'}


@register.filter
def uses_scale_style(field):
    """True when the question renders through the shared scale partials.

    `rating` always resolves to one of these. `range` only does so when its
    creator picked one — `default` keeps the slider, which renders as an
    ordinary card question.
    """
    if getattr(field.field.widget, 'question_type', None) not in SCALE_STYLE_TYPES:
        return False
    return getattr(field.field.widget, 'display_style', None) in CHOICE_BASED_STYLES


@register.filter
def get_range(count):
    return range(int(count))
