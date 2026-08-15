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
CHOICE_BASED_STYLES = {'scale_strip', 'list_pips', 'stars'}

# Types that can render through those partials. The style alone is not enough
# to decide: a text question would be sent through them and blow up on
# field.field.choices. Range is deliberately absent — it always renders as
# the slider, whatever display_style is stored.
SCALE_STYLE_TYPES = {'rating'}


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


@register.inclusion_tag('editor/partials/question_type_picker.html')
def question_type_picker(bound_field):
    """Grouped card grid for the input_type field.

    Renders from the bound field's own choices, so sub-question restrictions
    (QuestionForm filters them out of the field) carry through without the
    picker knowing about them.
    """
    from survey.question_types import picker_groups_for

    choices = list(bound_field.field.choices)
    groups = picker_groups_for(choices)
    current = bound_field.value()
    if not current:
        # The form pre-selects 'text' for new questions; this fallback only
        # covers a re-render where the submitted value was empty. The model's
        # BLANK_CHOICE_DASH entry has no metadata, so take the first real type.
        for _label, types in groups:
            if types:
                current = types[0]['value']
                break
    return {
        'groups': groups,
        'current': current,
    }


@register.filter
def star_icon(field):
    """Font Awesome class a star rating draws, resolved on the widget."""
    return getattr(field.field.widget, 'star_icon', 'fas fa-star')


@register.filter
def star_color(field):
    return getattr(field.field.widget, 'star_color', '#f5b301')


# Types whose subtext is rendered by the section template. Geo types and html
# carry theirs inside their own widget templates, and image renders it as a
# caption, so all four are deliberately absent.
SUBTEXT_IN_TEMPLATE_TYPES = {
    'text', 'text_line', 'number', 'choice', 'multichoice', 'range', 'rating', 'datetime',
}


@register.filter
def question_subtext(field):
    """The helper line shown between a question's text and its input."""
    if getattr(field.field.widget, 'question_type', None) not in SUBTEXT_IN_TEMPLATE_TYPES:
        return ''
    return getattr(field.field.widget, 'question_subtext', '') or ''
